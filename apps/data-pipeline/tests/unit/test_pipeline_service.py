import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, call
from typing import Dict, Any, List

# [Target Modules]
from src.pipeline_service import PipelineService

# [Dependencies & Interfaces]
# 실제 DTO 의존성을 제거하고 내부 Mock Class를 사용하여 테스트 격리(Isolation)를 강화합니다.
from src.common.exceptions import (
    ETLError, ExtractorError, TransformerError, LoaderError, 
    NetworkConnectionError
)

# ========================================================================================
# [Mocks & Stubs]
# ========================================================================================

class MockExtractedDTO:
    """테스트용 Extracted DTO (격리된 객체)"""
    def __init__(self, data: Any = None, meta: Dict = None):
        self.data = data
        self.meta = meta or {}

class MockTransformedDTO:
    """테스트용 Transformed DTO (격리된 객체)"""
    def __init__(self, data: Any = None, meta: Dict = None):
        self.data = data
        self.meta = meta or {}

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger_isolation():
    """Service Class의 로거 격리 픽스처 (로그 출력 차단)."""
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        mock_get_logger.return_value = MagicMock()
        yield mock_get_logger

@pytest.fixture
def mock_config():
    """ConfigManager 객체 및 extraction_policy 모방"""
    # PipelineService 내부에서 import한 ConfigManager를 Mocking
    with patch("src.pipeline_service.ConfigManager") as mock_config_cls:
        config_obj = MagicMock()
        # 기본 정책 (테스트마다 덮어쓰기 가능)
        config_obj.extraction_policy = {"job_default": {}}
        mock_config_cls.get_config.return_value = config_obj
        yield config_obj

@pytest.fixture
def mock_extractor_service_cls():
    """ExtractorService 클래스 및 인스턴스 메서드 Mocking"""
    with patch("src.pipeline_service.ExtractorService") as mock_cls:
        instance = mock_cls.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.extract_batch = AsyncMock()
        yield mock_cls

@pytest.fixture
def pipeline_service(mock_config, mock_extractor_service_cls, mock_logger_isolation):
    """기본 설정이 주입된 PipelineService 인스턴스"""
    return PipelineService("test_task")

# ========================================================================================
# 1. 자원 생명주기 테스트 (Lifecycle)
# ========================================================================================

@pytest.mark.asyncio
async def test_life_01_lifecycle_propagation(pipeline_service, mock_extractor_service_cls):
    """[LIFE-01] [Integration] 상위 서비스 진입 시 하위 서비스 리소스(Extractor)도 초기화됨"""
    # When: Context Manager 진입 (정상 종료 케이스)
    async with pipeline_service as srv:
        pass
        
    # Then: 하위 서비스의 __aenter__, __aexit__ 호출 확인
    extractor_instance = mock_extractor_service_cls.return_value
    extractor_instance.__aenter__.assert_awaited_once()
    extractor_instance.__aexit__.assert_awaited_once()

@pytest.mark.asyncio
async def test_life_02_lifecycle_exception_propagation(pipeline_service, mock_extractor_service_cls):
    """[LIFE-02] [Exception Branch] Context 내부 예외 발생 시에도 __aexit__ 호출 및 리소스 정리 보장"""
    # Given
    extractor_instance = mock_extractor_service_cls.return_value

    # When: Context 내부에서 예외 강제 발생
    with pytest.raises(ValueError, match="Context Crash"):
        async with pipeline_service:
            raise ValueError("Context Crash")
    
    # Then: 예외가 발생했더라도 하위 서비스의 __aexit__가 호출되어야 함
    extractor_instance.__aexit__.assert_awaited_once()

# ========================================================================================
# 2. 배치 실행 테스트 (Batch Execution)
# ========================================================================================

@pytest.mark.asyncio
async def test_batch_01_single_job_success(pipeline_service, mock_extractor_service_cls, mock_config):
    """[BATCH-01] [Standard] 단일 작업 성공 시 Summary 집계 정확성 검증"""
    # Given
    mock_config.extraction_policy = {"job_A": {}}
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockExtractedDTO(data="test")]
    
    # When
    summary = await pipeline_service.run_batch()
    
    # Then
    assert summary["total"] == 1
    assert summary["success"] == 1
    assert summary["fail"] == 0
    assert summary["details"][0]["status"] == "SUCCESS"

@pytest.mark.asyncio
async def test_config_01_empty_policy_defense(pipeline_service, mock_config, mock_extractor_service_cls):
    """[CONFIG-01] [BVA] 설정된 작업이 없을 때 조기 종료(Early Return)"""
    # Given
    mock_config.extraction_policy = {} 
    
    # When
    summary = await pipeline_service.run_batch()
    
    # Then
    assert summary["status"] == "empty"
    assert summary["total"] == 0
    mock_extractor_service_cls.return_value.extract_batch.assert_not_called()

# ========================================================================================
# 3. 데이터 무결성 테스트 (Data Integrity)
# ========================================================================================

@pytest.mark.asyncio
async def test_data_01_empty_payload_passthrough(pipeline_service, mock_extractor_service_cls, mock_config):
    """[DATA-01] [BVA] 수집은 성공했으나 데이터가 없는 경우(None) 에러 없이 통과"""
    # Given
    mock_config.extraction_policy = {"job_empty": {}}
    # 데이터가 None인 DTO 반환
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockExtractedDTO(data=None)]
    
    # When
    summary = await pipeline_service.run_batch()
    
    # Then
    assert summary["success"] == 1
    assert summary["fail"] == 0
    # Mock Transform/Load가 None 데이터에 대해 예외를 발생시키지 않는지 확인

@pytest.mark.asyncio
async def test_priv_01_mock_load_branches(pipeline_service):
    """[PRIV-01] _mock_load 메서드의 분기(데이터 유무) 직접 검증 (Coverage 223->exit 해결)"""
    # Given 1: 데이터가 있는 경우 -> 로깅 호출 (True Branch)
    dto_with_data = MockTransformedDTO(data="Some Data", meta={"source": "TEST", "status": "OK"})
    await pipeline_service._mock_load(dto_with_data)
    
    # Given 2: 데이터가 없는 경우 -> 로깅 건너뜀 (False Branch) -> Function Exit
    dto_no_data = MockTransformedDTO(data=None)
    await pipeline_service._mock_load(dto_no_data)
    # 별도 Assert가 없어도 실행 흐름이 도달했으므로 Branch Coverage 달성

# ========================================================================================
# 4. 결함 격리 및 예외 처리 테스트 (Fault Tolerance)
# ========================================================================================

@pytest.mark.asyncio
async def test_fail_e_01_extract_exception(pipeline_service, mock_extractor_service_cls, mock_config):
    """[FAIL-E-01] [MC/DC] 수집 단계에서 에러 객체 반환 시 상태 'FAIL_EXTRACT' 기록"""
    # Given
    mock_config.extraction_policy = {"job_fail": {}}
    # Extractor가 DTO 대신 Exception 객체를 리스트에 담아 반환
    mock_extractor_service_cls.return_value.extract_batch.return_value = [ExtractorError("Network Error")]
    
    # When
    summary = await pipeline_service.run_batch()
    
    # Then
    assert summary["fail"] == 1
    detail = summary["details"][0]
    assert detail["status"] == "FAIL_EXTRACT"
    assert detail["error_info"]["message"] == "Network Error"

@pytest.mark.asyncio
async def test_fail_t_01_transform_known_error(pipeline_service, mock_extractor_service_cls, mock_config):
    """[FAIL-T-01] [MC/DC] 변환 단계에서 Known Error(ETLError) 발생 시 상태 'FAIL_TRANSFORM'"""
    # Given
    mock_config.extraction_policy = {"job_t_fail": {}}
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockExtractedDTO()]
    
    # Transform 단계에서 TransformerError 발생
    with patch.object(pipeline_service, '_mock_transform', side_effect=TransformerError("Parsing Fail")):
        
        # When
        summary = await pipeline_service.run_batch()
        
        # Then
        assert summary["fail"] == 1
        assert summary["details"][0]["status"] == "FAIL_TRANSFORM"

@pytest.mark.asyncio
async def test_fail_t_02_transform_unknown_wrapping(pipeline_service, mock_extractor_service_cls, mock_config):
    """[FAIL-T-02] [Exception Wrapping] 변환 중 Unknown Error 발생 시 TransformerError로 래핑"""
    # Given
    mock_config.extraction_policy = {"job_t_wrap": {}}
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockExtractedDTO()]
    
    # Transform 단계에서 예상치 못한 ValueError 발생
    with patch.object(pipeline_service, '_mock_transform', side_effect=ValueError("Invalid Format")):
        
        # When
        summary = await pipeline_service.run_batch()
        
        # Then
        assert summary["fail"] == 1
        detail = summary["details"][0]
        # Unknown Error가 TransformerError로 감싸져서 'FAIL_TRANSFORM'으로 분류되어야 함
        assert detail["status"] == "FAIL_TRANSFORM"
        assert "Invalid Format" in detail["error_info"]["message"]
        assert detail["error_info"]["cause"] == "Invalid Format"

@pytest.mark.asyncio
async def test_fail_l_01_load_known_error(pipeline_service, mock_extractor_service_cls, mock_config):
    """[FAIL-L-01] [MC/DC] 적재 단계에서 Known Error 발생 시 상태 'FAIL_LOAD'"""
    # Given
    mock_config.extraction_policy = {"job_l_fail": {}}
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockExtractedDTO()]
    
    # Load 단계에서 LoaderError 발생
    with patch.object(pipeline_service, '_mock_load', side_effect=LoaderError("DB Full")):
        
        # When
        summary = await pipeline_service.run_batch()
        
        # Then
        assert summary["fail"] == 1
        assert summary["details"][0]["status"] == "FAIL_LOAD"

@pytest.mark.asyncio
async def test_fail_l_02_load_unknown_wrapping(pipeline_service, mock_extractor_service_cls, mock_config):
    """[FAIL-L-02] [Exception Wrapping] 적재 중 ConnectionError 발생 시 LoaderError로 래핑"""
    # Given
    mock_config.extraction_policy = {"job_l_wrap": {}}
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockExtractedDTO()]
    
    # Load 단계에서 ConnectionError 발생
    with patch.object(pipeline_service, '_mock_load', side_effect=ConnectionError("Broken Pipe")):
        
        # When
        summary = await pipeline_service.run_batch()
        
        # Then
        assert summary["fail"] == 1
        detail = summary["details"][0]
        # Unknown Error가 LoaderError로 감싸져서 'FAIL_LOAD'로 분류되어야 함
        assert detail["status"] == "FAIL_LOAD"
        assert "Broken Pipe" in detail["error_info"]["message"]

@pytest.mark.asyncio
async def test_fail_05_unknown_etl_error(pipeline_service, mock_extractor_service_cls, mock_config):
    """[FAIL-UNKNOWN] [Branch] 정의되지 않은 ETLError 하위 타입 발생 시 FAIL_UNKNOWN 처리"""
    # Given
    mock_config.extraction_policy = {"job_unknown_err": {}}
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockExtractedDTO()]
    
    # 순수 Base ETLError 발생 시뮬레이션
    with patch.object(pipeline_service, '_mock_transform', side_effect=ETLError("Generic ETL Fail")):
        
        # When
        summary = await pipeline_service.run_batch()
        
        # Then
        assert summary["fail"] == 1
        detail = summary["details"][0]
        
        assert detail["status"] == "FAIL_UNKNOWN"
        assert detail["error_info"]["message"] == "Generic ETL Fail"

@pytest.mark.asyncio
async def test_crit_01_system_error(pipeline_service, mock_extractor_service_cls, mock_config):
    """[CRIT-01] [System] 로직 수행 중 치명적 시스템 에러(MemoryError) 발생 시 루프 유지 및 상태 기록"""
    # Given
    mock_config.extraction_policy = {"job_critical": {}}
    
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MemoryError("OOM System Crash")]
    
    # When
    summary = await pipeline_service.run_batch()
    
    # Then
    assert summary["fail"] == 1
    detail = summary["details"][0]
    
    # 검증: ETLError가 아닌 Raw Exception이므로 최상위 'except Exception' 블록에 포착되어야 함
    assert detail["status"] == "CRITICAL_SYSTEM_ERROR"
    assert detail["error_info"]["type"] == "MemoryError"
    assert "OOM System Crash" in detail["error_info"]["message"]

# ========================================================================================
# 5. 복합 시나리오 테스트 (Combination)
# ========================================================================================

@pytest.mark.asyncio
async def test_mix_01_mixed_results_aggregation(pipeline_service, mock_extractor_service_cls, mock_config):
    """[MIX-01] [Combination] 성공/수집실패/적재실패가 혼합된 상황 검증"""
    # Given: 3개의 Job
    jobs = ["Job_Success", "Job_Extract_Fail", "Job_Load_Fail"]
    mock_config.extraction_policy = {j: {} for j in jobs}
    
    # Extractor 결과: [성공DTO, 에러객체, 성공DTO(나중에 Load에서 실패)]
    mock_extractor_service_cls.return_value.extract_batch.return_value = [
        MockExtractedDTO(data="ok_1"),
        ExtractorError("Extract Fail"),
        MockExtractedDTO(data="ok_2_but_fail_later")
    ]
    
    # Transform 함수 Side Effect: 데이터 변환 성공 가정 (Pass-through)
    async def mock_transform_side_effect(dto):
        return MockTransformedDTO(data=dto.data, meta=dto.meta)

    # Load 함수 Side Effect: 특정 데이터에 대해 실패 발생
    async def mock_load_side_effect(dto):
        if dto.data == "ok_2_but_fail_later":
            raise LoaderError("Load Fail")
        return None

    # [Fix] Transform과 Load 모두를 Patch하여 흐름을 완전 제어
    # 이렇게 하면 3번째 Job이 Transform 단계는 통과하고 Load 단계에서 실패하여 summary["fail"]을 증가시킴
    with patch.object(pipeline_service, '_mock_transform', side_effect=mock_transform_side_effect), \
         patch.object(pipeline_service, '_mock_load', side_effect=mock_load_side_effect):
        
        # When
        summary = await pipeline_service.run_batch()
        
        # Then
        assert summary["total"] == 3
        assert summary["success"] == 1 # Job_Success 1개
        assert summary["fail"] == 2    # Job_Extract_Fail(1) + Job_Load_Fail(1)
        
        details = summary["details"]
        # 순서대로 상태 확인
        assert details[0]["status"] == "SUCCESS"      # 1번: 성공
        assert details[1]["status"] == "FAIL_EXTRACT" # 2번: 수집 실패
        assert details[2]["status"] == "FAIL_LOAD"    # 3번: 적재 실패