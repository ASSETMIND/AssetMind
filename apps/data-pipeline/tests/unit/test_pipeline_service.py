"""
[테스트 모듈] test_pipeline_service.py
대상: src.pipeline_service.PipelineService
목적: PipelineService의 100% Branch Coverage 달성 및 BDD 기반 결함 격리 검증.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

# [Target Modules]
from src.pipeline_service import PipelineService, STATUS_SUCCESS, STATUS_EMPTY, STATUS_FAIL_EXTRACT, STATUS_FAIL_LOAD, STATUS_SYSTEM_ERROR
from src.common.exceptions import ConfigurationError, ETLError, LoaderError
from src.common.dtos import ExtractedDTO

# ========================================================================================
# [Mocks & Stubs]
# ========================================================================================

class MockExtractedDTO(ExtractedDTO):
    """테스트용 DTO Stub"""
    def __init__(self, data="dummy"):
        self.data = data

class MockETLError(ETLError):
    """테스트용 ETLError Stub (to_dict 검증용)"""
    def __init__(self, msg="dummy etl error"):
        super().__init__(msg)
    def to_dict(self):
        return {"type": "MockETLError", "message": str(self)}

class MockLoaderError(LoaderError):
    """테스트용 LoaderError Stub"""
    def __init__(self, msg="dummy loader error"):
        super().__init__(msg)
    def to_dict(self):
        return {"type": "MockLoaderError", "message": str(self)}

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger_isolation():
    """Service Class의 로거 격리 픽스처 (로그 출력 차단)"""
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        mock_get_logger.return_value = MagicMock()
        yield mock_get_logger

@pytest.fixture
def mock_config_manager():
    """ConfigManager 전역 의존성 모킹"""
    with patch("src.pipeline_service.ConfigManager") as mock_cm:
        mock_config = MagicMock()
        # 기본 정책 구성
        mock_policy = MagicMock()
        mock_policy.extract_jobs = ["job_1"]
        mock_policy.target_loader = "s3"
        
        mock_config.get_pipeline.return_value = mock_policy
        mock_cm.load.return_value = mock_config
        yield mock_cm

@pytest.fixture
def mock_extractor_service_cls():
    """ExtractorService 모킹"""
    with patch("src.pipeline_service.ExtractorService") as mock_cls:
        instance = mock_cls.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.extract_batch = AsyncMock()
        yield mock_cls

@pytest.fixture
def mock_loader_service_cls():
    """LoaderService 모킹"""
    with patch("src.pipeline_service.LoaderService") as mock_cls:
        instance = mock_cls.return_value
        instance.execute_load = MagicMock()
        yield mock_cls

@pytest.fixture
def pipeline_service(mock_config_manager, mock_extractor_service_cls, mock_loader_service_cls):
    """기본 의존성이 주입된 PipelineService 인스턴스"""
    return PipelineService("test_task")

# ========================================================================================
# 1. 초기화 및 검증 (Initialization)
# ========================================================================================

def test_init_01_invalid_task_name(mock_config_manager):
    """[INIT-01] task_name이 빈 문자열인 경우 Assertion 예외 발생 (조기 차단)"""
    # GIVEN: 유효하지 않은 (빈 문자열) 작업 이름
    invalid_task_name = "   "
    
    # WHEN & THEN: PipelineService 초기화 시도 시 AssertionError 발생
    with pytest.raises(AssertionError, match="비어있을 수 없는 문자열이어야 합니다."):
        PipelineService(invalid_task_name)

def test_init_02_configuration_error(mock_config_manager):
    """[INIT-02] 설정 파일에서 task를 찾을 수 없을 때 ConfigurationError 발생"""
    # GIVEN: ConfigManager가 설정 로드 중 ConfigurationError를 발생시키도록 모킹
    mock_config = mock_config_manager.load.return_value
    mock_config.get_pipeline.side_effect = ConfigurationError("Not Found")
    
    # WHEN & THEN: 초기화 시도 시 에러가 래핑되어 상위로 전파됨
    with pytest.raises(ConfigurationError, match="파이프라인 설정을 로드할 수 없습니다."):
        PipelineService("missing_task")

# ========================================================================================
# 2. 자원 생명주기 (Lifecycle)
# ========================================================================================

@pytest.mark.asyncio
async def test_life_01_context_manager_propagation(pipeline_service, mock_extractor_service_cls):
    """[LIFE-01] PipelineService의 Context Manager 진입/종료가 ExtractorService로 전파됨"""
    # GIVEN: PipelineService 인스턴스 (fixture)
    extractor_instance = mock_extractor_service_cls.return_value
    
    # WHEN: Context Manager 실행
    async with pipeline_service as srv:
        assert srv is pipeline_service
        
    # THEN: 하위 서비스의 aenter, aexit가 정확히 1회 호출됨을 검증
    extractor_instance.__aenter__.assert_awaited_once()
    extractor_instance.__aexit__.assert_awaited_once()

# ========================================================================================
# 3. 배치 실행 (Batch Execution)
# ========================================================================================

@pytest.mark.asyncio
async def test_batch_01_empty_jobs_early_return(pipeline_service, mock_config_manager, mock_extractor_service_cls):
    """[BATCH-01] 할당된 작업이 없으면 통신 없이 STATUS_EMPTY 상태로 조기 종료"""
    # GIVEN: extract_jobs 리스트가 비어있음
    mock_config = mock_config_manager.load.return_value
    mock_config.get_pipeline.return_value.extract_jobs = []
    
    # WHEN: run_batch 호출
    summary = await pipeline_service.run_batch()
    
    # THEN: 조기 반환 구조체 검증 및 하위 호출 발생 안함
    assert summary["status"] == STATUS_EMPTY
    assert summary["total"] == 0
    mock_extractor_service_cls.return_value.extract_batch.assert_not_called()

@pytest.mark.asyncio
async def test_batch_02_success_pipeline(pipeline_service, mock_extractor_service_cls, mock_loader_service_cls):
    """[BATCH-02] 정상 데이터 수집 및 적재 완료 시 SUCCESS 통계 반환"""
    # GIVEN: 1개의 Job 정상 처리 세팅
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockExtractedDTO()]
    mock_loader_service_cls.return_value.execute_load.return_value = True
    
    # WHEN: run_batch 호출
    summary = await pipeline_service.run_batch()
    
    # THEN: 성공 카운트 1, 실패 0 확인
    assert summary["success"] == 1
    assert summary["fail"] == 0
    assert summary["details"][0]["status"] == STATUS_SUCCESS

# ========================================================================================
# 4. 수집 결함 격리 (Extract Fault Tolerance)
# ========================================================================================

@pytest.mark.asyncio
async def test_fail_e_01_extract_known_error(pipeline_service, mock_extractor_service_cls):
    """[FAIL-E-01] 수집 결과가 ETLError 인스턴스일 경우 to_dict 기반으로 에러 포맷팅"""
    # GIVEN: Extractor가 알려진 ETLError 도메인 예외 객체를 반환
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockETLError("Network Timeout")]
    
    # WHEN: run_batch 호출
    summary = await pipeline_service.run_batch()
    
    # THEN: 적재로 안 넘어가고 FAIL_EXTRACT 처리됨
    assert summary["fail"] == 1
    detail = summary["details"][0]
    assert detail["status"] == STATUS_FAIL_EXTRACT
    assert detail["error_info"]["type"] == "MockETLError"

@pytest.mark.asyncio
async def test_fail_e_02_extract_unknown_error(pipeline_service, mock_extractor_service_cls):
    """[FAIL-E-02] 수집 결과가 일반 Exception 객체일 경우 범용 str 기반으로 에러 포맷팅"""
    # GIVEN: Extractor가 도메인 예외가 아닌 시스템 예외 반환
    mock_extractor_service_cls.return_value.extract_batch.return_value = [ValueError("Invalid JSON")]
    
    # WHEN: run_batch 호출
    summary = await pipeline_service.run_batch()
    
    # THEN: FAIL_EXTRACT 처리되며 일반 딕셔너리로 에러가 매핑됨
    assert summary["fail"] == 1
    detail = summary["details"][0]
    assert detail["status"] == STATUS_FAIL_EXTRACT
    assert detail["error_info"]["message"] == "Invalid JSON"

# ========================================================================================
# 5. 적재 결함 격리 (Load Fault Tolerance)
# ========================================================================================

@pytest.mark.asyncio
async def test_fail_l_01_load_returns_false(pipeline_service, mock_extractor_service_cls, mock_loader_service_cls):
    """[FAIL-L-01] 적재 메서드가 에러 없이 False를 반환할 경우 FAIL_LOAD로 처리"""
    # GIVEN: 수집은 성공, 그러나 적재 모듈이 비정상 응답(False) 반환
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockExtractedDTO()]
    mock_loader_service_cls.return_value.execute_load.return_value = False
    
    # WHEN: run_batch 호출
    summary = await pipeline_service.run_batch()
    
    # THEN: FAIL_LOAD 상태 반영
    assert summary["fail"] == 1
    detail = summary["details"][0]
    assert detail["status"] == STATUS_FAIL_LOAD
    assert "Loader returned False" in detail["error_info"]["message"]

@pytest.mark.asyncio
async def test_fail_l_02_load_raises_loader_error(pipeline_service, mock_extractor_service_cls, mock_loader_service_cls):
    """[FAIL-L-02] 적재 중 LoaderError 발생 시 격리 및 FAIL_LOAD 처리"""
    # GIVEN: 수집 성공, 적재 시 LoaderError 강제 발생
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockExtractedDTO()]
    mock_loader_service_cls.return_value.execute_load.side_effect = MockLoaderError("S3 Upload Failed")
    
    # WHEN: run_batch 호출
    summary = await pipeline_service.run_batch()
    
    # THEN: 전체 프로세스 중단 없이 FAIL_LOAD로 개별 격리됨
    assert summary["fail"] == 1
    detail = summary["details"][0]
    assert detail["status"] == STATUS_FAIL_LOAD
    assert detail["error_info"]["type"] == "MockLoaderError"

@pytest.mark.asyncio
async def test_fail_l_03_load_critical_system_error(pipeline_service, mock_extractor_service_cls, mock_loader_service_cls):
    """[FAIL-L-03] 적재 중 예측하지 못한 Exception 발생 시 ETLError로 래핑 및 CRITICAL 기록"""
    # GIVEN: 적재 도중 치명적 메모리 에러 발생 (방어적 프로그래밍 테스트)
    mock_extractor_service_cls.return_value.extract_batch.return_value = [MockExtractedDTO()]
    mock_loader_service_cls.return_value.execute_load.side_effect = MemoryError("Out of Memory")
    
    # WHEN: run_batch 호출
    summary = await pipeline_service.run_batch()
    
    # THEN: CRITICAL_SYSTEM_ERROR 상태 반영 및 안전하게 종료
    assert summary["fail"] == 1
    detail = summary["details"][0]
    assert detail["status"] == STATUS_SYSTEM_ERROR
    assert "Out of Memory" in detail["error_info"]["message"]