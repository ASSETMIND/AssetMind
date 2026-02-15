import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, call
from typing import Dict, Any, List

# [Target Modules]
from src.pipeline_service import PipelineService

# [Dependencies & Interfaces]
from src.common.dtos import ExtractedDTO, TransformedDTO

# ========================================================================================
# [Mocks & Stubs]
# ========================================================================================

class MockExtractedDTO:
    def __init__(self, data: Any = None, meta: Dict = None):
        self.data = data or []
        self.meta = meta or {}

class MockTransformedDTO:
    def __init__(self, data: Any = None, meta: Dict = None):
        self.data = data or []
        self.meta = meta or {}

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger_isolation():
    """Service Class의 로거 격리 픽스처."""
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        mock_get_logger.return_value = MagicMock()
        yield mock_get_logger

@pytest.fixture
def mock_config():
    """ConfigManager 객체 및 extraction_policy 모방"""
    # [핵심 수정] 정의된 곳(src.common.config)이 아닌, 사용되는 곳(src.pipeline_service)을 패치해야 함
    with patch("src.pipeline_service.get_config") as mock_get_config:
        config_obj = MagicMock()
        # 기본 정책 설정
        config_obj.extraction_policy = {"job_A": {}, "job_B": {}}
        mock_get_config.return_value = config_obj
        yield config_obj

@pytest.fixture
def mock_extractor_service_cls():
    """ExtractorService 클래스 및 인스턴스 메서드 Mocking"""
    # 사용되는 모듈 내의 클래스명을 패치
    with patch("src.pipeline_service.ExtractorService") as mock_cls:
        instance = mock_cls.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.extract_batch = AsyncMock()
        yield mock_cls

@pytest.fixture
def pipeline_service(mock_config, mock_extractor_service_cls, mock_logger_isolation):
    """기본 설정이 주입된 PipelineService 인스턴스"""
    # mock_config 픽스처가 먼저 실행되어 get_config가 Mocking된 상태에서 인스턴스 생성
    return PipelineService("test_task")

# ========================================================================================
# 1. 자원 생명주기 테스트 (Lifecycle Management)
# ========================================================================================

@pytest.mark.asyncio
async def test_life_01_lifecycle_propagation(pipeline_service, mock_extractor_service_cls):
    """[LIFE-01] [Integration] 상위 서비스 진입 시 하위 서비스 리소스(Extractor)도 초기화됨"""
    async with pipeline_service as srv:
        pass
        
    extractor_instance = mock_extractor_service_cls.return_value
    extractor_instance.__aenter__.assert_awaited_once()
    extractor_instance.__aexit__.assert_awaited_once()

@pytest.mark.asyncio
async def test_life_02_idempotency_reuse(pipeline_service, mock_extractor_service_cls):
    """[LIFE-02] [Idempotency] 서비스 재실행 시 상태 꼬임 없이 독립 수행 (재사용성)"""
    extractor_instance = mock_extractor_service_cls.return_value
    extractor_instance.extract_batch.return_value = [MockExtractedDTO(), MockExtractedDTO()]
    
    result1 = await pipeline_service.run_batch()
    result2 = await pipeline_service.run_batch()
    
    assert result1["success"] == 2
    assert result2["success"] == 2
    assert extractor_instance.extract_batch.call_count == 2

# ========================================================================================
# 2. 배치 실행 테스트 (Batch Execution)
# ========================================================================================

@pytest.mark.asyncio
async def test_batch_01_single_job_success(pipeline_service, mock_extractor_service_cls, mock_config):
    """[BATCH-01] [Standard] 단일 작업 성공 시 Summary 집계 정확성 검증"""
    # Given: Mock Config 객체의 속성을 직접 수정
    mock_config.extraction_policy = {"job_single": {}}
    
    extractor_instance = mock_extractor_service_cls.return_value
    extractor_instance.extract_batch.return_value = [MockExtractedDTO(data="test")]
    
    # When
    summary = await pipeline_service.run_batch()
    
    # Then
    assert summary["total"] == 1
    assert summary["success"] == 1
    assert summary["fail"] == 0
    assert summary["details"][0]["status"] == "SUCCESS"

@pytest.mark.asyncio
async def test_batch_02_multi_job_success(pipeline_service, mock_extractor_service_cls, mock_config):
    """[BATCH-02] [Standard] 다중 작업 병렬 수집 후 전량 성공 처리"""
    # Given
    jobs = ["A", "B", "C"]
    mock_config.extraction_policy = {job: {} for job in jobs}
    
    extractor_instance = mock_extractor_service_cls.return_value
    extractor_instance.extract_batch.return_value = [MockExtractedDTO() for _ in range(3)]
    
    # When
    summary = await pipeline_service.run_batch()
    
    # Then
    assert summary["total"] == 3
    assert summary["success"] == 3
    assert summary["fail"] == 0

@pytest.mark.asyncio
async def test_batch_03_empty_policy_defense(pipeline_service, mock_config, mock_extractor_service_cls):
    """[BATCH-03] [Defensive] 설정된 작업이 없을 때 조기 종료(Early Return)"""
    # Given
    mock_config.extraction_policy = {} 
    
    # When
    summary = await pipeline_service.run_batch()
    
    # Then
    assert summary["status"] == "empty"
    assert summary["total"] == 0
    mock_extractor_service_cls.return_value.extract_batch.assert_not_called()

# ========================================================================================
# 3. 결함 격리 테스트 (Fault Tolerance & MC/DC)
# ========================================================================================

@pytest.mark.asyncio
async def test_fault_01_mcdc_extract_fail(pipeline_service, mock_extractor_service_cls, mock_config):
    """[FAULT-01] [MC/DC] 수집 단계 실패 시 변환/적재 미실행 및 상태 'FAIL_EXTRACT' 검증"""
    # Given
    mock_config.extraction_policy = {"job_fail": {}}
    extractor_instance = mock_extractor_service_cls.return_value
    extractor_instance.extract_batch.return_value = [RuntimeError("Network Error")]
    
    with patch.object(pipeline_service, '_mock_transform') as spy_transform, \
         patch.object(pipeline_service, '_mock_load') as spy_load:
        
        # When
        summary = await pipeline_service.run_batch()
        
        # Then
        assert summary["fail"] == 1
        assert summary["details"][0]["status"] == "FAIL_EXTRACT"
        assert "Network Error" in summary["details"][0]["error"]
        
        spy_transform.assert_not_called()
        spy_load.assert_not_called()

@pytest.mark.asyncio
async def test_fault_02_mcdc_transform_fail(pipeline_service, mock_extractor_service_cls, mock_config):
    """[FAULT-02] [MC/DC] 변환 단계 실패 시 적재 미실행 및 상태 'FAIL_TRANSFORM_LOAD' 검증"""
    # Given
    mock_config.extraction_policy = {"job_trans_fail": {}}
    extractor_instance = mock_extractor_service_cls.return_value
    extractor_instance.extract_batch.return_value = [MockExtractedDTO()]
    
    with patch.object(pipeline_service, '_mock_transform', side_effect=ValueError("Transform Fail")) as mock_trans, \
         patch.object(pipeline_service, '_mock_load') as mock_load:
        
        # When
        summary = await pipeline_service.run_batch()
        
        # Then
        assert summary["fail"] == 1
        assert summary["details"][0]["status"] == "FAIL_TRANSFORM_LOAD"
        assert "Transform Fail" in summary["details"][0]["error"]
        
        mock_trans.assert_called_once()
        mock_load.assert_not_called()

@pytest.mark.asyncio
async def test_fault_03_mcdc_load_fail(pipeline_service, mock_extractor_service_cls, mock_config):
    """[FAULT-03] [MC/DC] 적재 단계 실패 시 상태 'FAIL_TRANSFORM_LOAD' 검증"""
    # Given
    mock_config.extraction_policy = {"job_load_fail": {}}
    extractor_instance = mock_extractor_service_cls.return_value
    extractor_instance.extract_batch.return_value = [MockExtractedDTO()]
    
    with patch.object(pipeline_service, '_mock_load', side_effect=IOError("DB Fail")) as mock_load:
        
        # When
        summary = await pipeline_service.run_batch()
        
        # Then
        assert summary["fail"] == 1
        assert summary["details"][0]["status"] == "FAIL_TRANSFORM_LOAD"
        assert "DB Fail" in summary["details"][0]["error"]
        
        mock_load.assert_called_once()

@pytest.mark.asyncio
async def test_fault_04_isolation_mixed_results(pipeline_service, mock_extractor_service_cls, mock_config):
    """[FAULT-04] [Isolation] 성공/수집실패/적재실패가 혼합된 상황에서 전체 중단 없이 완료"""
    # Given
    jobs = ["Job_Success", "Job_Extract_Fail", "Job_Load_Fail"]
    mock_config.extraction_policy = {j: {} for j in jobs}
    
    extractor_instance = mock_extractor_service_cls.return_value
    extractor_instance.extract_batch.return_value = [
        MockExtractedDTO(data="ok"),
        RuntimeError("Extract Fail"),
        MockExtractedDTO(data="ok_but_load_fail")
    ]
    
    async def mock_load_side_effect(dto):
        if dto.data == "ok_but_load_fail":
            raise IOError("Load Fail")
        return None

    with patch.object(pipeline_service, '_mock_load', side_effect=mock_load_side_effect):
        
        # When
        summary = await pipeline_service.run_batch()
        
        # Then
        assert summary["total"] == 3
        assert summary["success"] == 1
        assert summary["fail"] == 2
        
        details = summary["details"]
        assert details[0]["status"] == "SUCCESS"
        assert details[1]["status"] == "FAIL_EXTRACT"
        assert details[2]["status"] == "FAIL_TRANSFORM_LOAD"

# ========================================================================================
# 4. 데이터 흐름 테스트 (Data Flow)
# ========================================================================================

@pytest.mark.asyncio
async def test_int_01_data_flow_integrity(pipeline_service, mock_extractor_service_cls, mock_config):
    """[INT-01] [DataFlow] 수집된 데이터가 변환 및 적재 메서드로 정확히 전달되는지 검증"""
    # Given
    mock_config.extraction_policy = {"job_flow": {}}
    test_data = {"id": 123, "val": "test"}
    test_meta = {"source": "api"}
    
    extractor_instance = mock_extractor_service_cls.return_value
    extractor_instance.extract_batch.return_value = [MockExtractedDTO(data=test_data, meta=test_meta)]
    
    with patch.object(pipeline_service, '_mock_transform', side_effect=pipeline_service._mock_transform) as spy_transform, \
         patch.object(pipeline_service, '_mock_load', side_effect=pipeline_service._mock_load) as spy_load:
        
        # When
        await pipeline_service.run_batch()
        
        # Then
        args_transform, _ = spy_transform.call_args
        input_dto = args_transform[0]
        assert input_dto.data == test_data
        assert input_dto.meta == test_meta
        
        args_load, _ = spy_load.call_args
        output_dto = args_load[0]
        assert output_dto.data == test_data
        assert output_dto.meta == test_meta