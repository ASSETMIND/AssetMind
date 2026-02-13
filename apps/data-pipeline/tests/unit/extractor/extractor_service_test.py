import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, call
from typing import Dict, Any, List, Union

# [Target Modules]
from src.extractor.extractor_service import ExtractorService
from src.extractor.domain.dtos import RequestDTO, ResponseDTO
from src.extractor.domain.exceptions import ExtractorError
from src.common.config import AppConfig

# [Dependencies & Interfaces]
from src.extractor.adapters.http_client import AsyncHttpAdapter
from src.extractor.extractor_factory import ExtractorFactory

# ========================================================================================
# [Mocks & Stubs] 실제 객체와 동일한 인터페이스를 갖도록 설계 (Test Doubles)
# ========================================================================================

class MockPolicy:
    """AppConfig.extraction_policy의 Value 객체 모방"""
    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}

class MockConfig:
    """AppConfig 객체 모방 (프로덕션 환경과 동일한 속성 구조 제공)"""
    def __init__(self, policies: Dict[str, MockPolicy] = None):
        self.extraction_policy = policies or {}

# ========================================================================================
# [Fixtures] 테스트 환경 설정 및 격리 (Isolation)
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger_isolation():
    """
    [Core Fix] Service Class의 로거 격리 픽스처.
    LogManager.get_logger를 Mocking하여 불필요한 I/O 및 Side-effect 방지.
    """
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        mock_get_logger.return_value = MagicMock()
        yield mock_get_logger

@pytest.fixture
def mock_http_adapter_cls():
    """내부에서 생성되는 AsyncHttpAdapter 클래스를 Mocking"""
    with patch("src.extractor.extractor_service.AsyncHttpAdapter") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.close = AsyncMock()
        mock_cls.return_value = mock_instance
        yield mock_cls

@pytest.fixture
def mock_factory():
    """ExtractorFactory.create_extractor 메서드 Mocking"""
    with patch("src.extractor.extractor_service.ExtractorFactory") as mock_factory:
        yield mock_factory

@pytest.fixture
def config_with_jobs():
    """표준적인 Job 정책이 포함된 설정 객체"""
    policies = {
        "job_normal": MockPolicy({"p1": "default"}),
        "job_error_domain": MockPolicy({}),
        "job_error_system": MockPolicy({}),
    }
    return MockConfig(policies)

# ========================================================================================
# 1. 자원 생명주기 테스트 (Lifecycle Management)
# ========================================================================================

@pytest.mark.asyncio
async def test_life_01_internal_lifecycle(mock_http_adapter_cls, config_with_jobs):
    """[LIFE-01] 내부 생성 시: 진입 시 생성, 종료 시 close() 호출 확인"""
    # Given
    service = ExtractorService(config_with_jobs, http_client=None)
    
    # When
    async with service as srv:
        # Then 1: Adapter 생성 확인
        mock_http_adapter_cls.assert_called_once()
    
    # Then 2: Context Exit 시 close() 호출 확인
    internal_client = mock_http_adapter_cls.return_value
    internal_client.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_life_02_external_lifecycle(config_with_jobs):
    """[LIFE-02] 외부 주입 시: 종료 시 close() 호출되지 않음 (자원 보존)"""
    # Given
    external_client = MagicMock()
    external_client.close = AsyncMock()
    service = ExtractorService(config_with_jobs, http_client=external_client)
    
    # When
    async with service as srv:
        pass
    
    # Then
    external_client.close.assert_not_called()

@pytest.mark.asyncio
async def test_life_03_guard_clause_no_init(config_with_jobs):
    """[LIFE-03] async with 없이 직접 호출 시 RuntimeError 발생"""
    # Given
    service = ExtractorService(config_with_jobs)
    
    # When & Then
    with pytest.raises(RuntimeError, match="HTTP Client is not initialized"):
        await service.extract_job("job_normal")

@pytest.mark.asyncio
async def test_life_04_safe_close_on_exception(mock_http_adapter_cls, config_with_jobs):
    """[LIFE-04] 내부 로직 예외 발생 시에도 자원 해제(close) 보장"""
    # Given
    service = ExtractorService(config_with_jobs)
    internal_client = mock_http_adapter_cls.return_value
    
    # When: Context 진입 후 강제 예외 발생 상황 시뮬레이션
    try:
        async with service:
            raise ValueError("Unexpected Crash")
    except ValueError:
        pass
    
    # Then: 예외에도 불구하고 close()가 호출되어야 함
    internal_client.close.assert_awaited_once()

# ========================================================================================
# 2. 응답 정규화 테스트 (Response Normalization)
# ========================================================================================

def test_norm_01_fast_path_optimization(config_with_jobs):
    """[NORM-01] [Optimization] 이미 status='success'인 경우 로직 건너뜀"""
    # Given
    service = ExtractorService(config_with_jobs)
    response = ResponseDTO(data=[], meta={"status": "success", "status_code": "000"})
    
    # When
    result = service._normalize_response(response)
    
    # Then: status_code가 "000"임에도 "success"가 유지됨 (변경 로직 안탐)
    assert result.meta["status"] == "success"
    assert result.meta["status_code"] == "000"

def test_norm_02_standard_code_mapping(config_with_jobs):
    """[NORM-02] [BVA] 다양한 성공 코드(200, OK, 0)가 success로 변환됨"""
    # Given
    service = ExtractorService(config_with_jobs)
    cases = ["200", "OK", "ok", "Success", "0", " 200 "]
    
    for code in cases:
        response = ResponseDTO(data=[], meta={"status_code": code})
        
        # When
        result = service._normalize_response(response)
        
        # Then
        assert result.meta["status"] == "success", f"Failed for code: {code}"

def test_norm_03_robustness_empty_code(config_with_jobs):
    """[NORM-03] [Robustness] status_code 결측 시 성공 및 200으로 보정"""
    # Given
    service = ExtractorService(config_with_jobs)
    cases = [None, ""]
    
    for code in cases:
        response = ResponseDTO(data=[], meta={"status_code": code})
        
        # When
        result = service._normalize_response(response)
        
        # Then
        assert result.meta["status"] == "success"
        assert result.meta["status_code"] == 200

def test_norm_04_safety_failure_preservation(config_with_jobs):
    """[NORM-04] [Safety] 실패 코드(404, Error)는 status를 변경하지 않음"""
    # Given
    service = ExtractorService(config_with_jobs)
    cases = ["404", "500", "ERROR", "fail"]
    
    for code in cases:
        response = ResponseDTO(data=[], meta={"status_code": code})
        
        # When
        result = service._normalize_response(response)
        
        # Then: status 키가 생성되지 않거나 success가 아니어야 함
        assert result.meta.get("status") != "success"

# ========================================================================================
# 3. 단건 수집 및 에러 핸들링 테스트 (Single Job & Error)
# ========================================================================================

@pytest.mark.asyncio
async def test_job_01_policy_not_found(config_with_jobs):
    """[JOB-01] 설정에 없는 Job ID 요청 시 ExtractorError 발생"""
    # Given
    service = ExtractorService(config_with_jobs, http_client=MagicMock())
    
    # When & Then
    with pytest.raises(ExtractorError, match="Job ID 'GHOST_JOB' not found"):
        await service.extract_job("GHOST_JOB")

@pytest.mark.asyncio
async def test_job_02_param_merging_priority(mock_factory, config_with_jobs):
    """[JOB-02] [DataFlow] Override 파라미터가 Config 파라미터보다 우선 적용"""
    # Given
    service = ExtractorService(config_with_jobs, http_client=MagicMock())
    mock_extractor = AsyncMock()
    mock_extractor.extract.return_value = ResponseDTO(data=[], meta={"status": "success"})
    mock_factory.create_extractor.return_value = mock_extractor
    
    override = {"p1": "overridden", "p2": "new"}
    
    # When
    await service.extract_job("job_normal", override_params=override)
    
    # Then: Factory 생성 후 호출된 extract의 인자 확인 (RequestDTO)
    call_args = mock_extractor.extract.call_args[0][0] # RequestDTO
    assert call_args.params["p1"] == "overridden"
    assert call_args.params["p2"] == "new"

@pytest.mark.asyncio
async def test_job_03_domain_exception_propagation(mock_factory, config_with_jobs):
    """[JOB-03] [Hierarchy] 도메인 에러(ExtractorError)는 그대로 전파"""
    # Given
    service = ExtractorService(config_with_jobs, http_client=MagicMock())
    mock_extractor = AsyncMock()
    mock_extractor.extract.side_effect = ExtractorError("Domain Logic Fail")
    mock_factory.create_extractor.return_value = mock_extractor
    
    # When & Then
    with pytest.raises(ExtractorError, match="Domain Logic Fail"):
        await service.extract_job("job_error_domain")

@pytest.mark.asyncio
async def test_job_04_system_exception_wrapping(mock_factory, config_with_jobs):
    """[JOB-04] [Hierarchy] 시스템 에러(KeyError)는 ExtractorError로 래핑"""
    # Given
    service = ExtractorService(config_with_jobs, http_client=MagicMock())
    mock_extractor = AsyncMock()
    mock_extractor.extract.side_effect = KeyError("Unexpected Key")
    mock_factory.create_extractor.return_value = mock_extractor
    
    # When & Then
    with pytest.raises(ExtractorError, match="Unexpected failure in job_error_system"):
        await service.extract_job("job_error_system")

# ========================================================================================
# 4. 배치 및 동시성 테스트 (Batch & Concurrency)
# ========================================================================================

@pytest.mark.asyncio
async def test_batch_01_mixed_input_structure(config_with_jobs):
    """[BATCH-01] [Structure] str과 tuple이 혼합된 입력 처리"""
    # Given
    service = ExtractorService(config_with_jobs, http_client=MagicMock())
    
    # Mock extract_job using patch.object to avoid real logic
    with patch.object(service, 'extract_job', new=AsyncMock()) as mock_extract:
        mock_extract.return_value = ResponseDTO(data=[], meta={"status": "success"})
        
        requests = ["job_normal", ("job_normal", {"p": "v"})]
        
        # When
        await service.extract_batch(requests)
        
        # Then: 총 2번 호출되어야 함
        assert mock_extract.call_count == 2
        # 첫 번째 호출 확인 (str -> extract_job(id))
        mock_extract.assert_any_call("job_normal")
        # 두 번째 호출 확인 (tuple -> extract_job(id, params))
        mock_extract.assert_any_call("job_normal", {"p": "v"})

@pytest.mark.asyncio
async def test_batch_02_defensive_invalid_type(config_with_jobs, mock_logger_isolation):
    """[BATCH-02] [Defensive] 잘못된 타입(int)은 무시하고 로깅 후 진행"""
    # Given
    service = ExtractorService(config_with_jobs, http_client=MagicMock())
    
    with patch.object(service, 'extract_job', new=AsyncMock()) as mock_extract:
        requests = ["job_normal", 12345]  # Invalid int included
        
        # When
        await service.extract_batch(requests)
        
        # Then
        assert mock_extract.call_count == 1  # 유효한 문자열 1개만 실행
        # 로거에 경고 메시지 기록 확인
        mock_logger_isolation.return_value.warning.assert_called()

@pytest.mark.asyncio
async def test_batch_03_isolation_partial_success(config_with_jobs):
    """[BATCH-03] [Isolation] 부분 성공 검증 (예외가 전체를 중단시키지 않음)"""
    # Given
    service = ExtractorService(config_with_jobs, http_client=MagicMock())
    
    # Mock extract_job to return [Success, Error, Success]
    success_dto = ResponseDTO(data="ok", meta={"status": "success"})
    fail_exc = ExtractorError("Fail")
    
    with patch.object(service, 'extract_job', side_effect=[success_dto, fail_exc, success_dto]):
        requests = ["job_1", "job_fail", "job_2"]
        
        # When
        results = await service.extract_batch(requests)
        
        # Then
        assert len(results) == 3
        assert isinstance(results[0], ResponseDTO)
        assert isinstance(results[1], ExtractorError) # Exception 객체 존재 확인
        assert isinstance(results[2], ResponseDTO)

@pytest.mark.asyncio
async def test_batch_04_bva_empty_list(config_with_jobs):
    """[BATCH-04] [BVA] 빈 리스트 요청 시 즉시 빈 리스트 반환"""
    # Given
    service = ExtractorService(config_with_jobs, http_client=MagicMock())
    
    # When
    results = await service.extract_batch([])
    
    # Then
    assert results == []

# ========================================================================================
# 5. 팩토리 협력 테스트 (Factory Interaction)
# ========================================================================================

@pytest.mark.asyncio
async def test_fact_01_factory_delegation(mock_factory, config_with_jobs):
    """[FACT-01] [Interaction] Factory.create_extractor 올바른 위임 검증"""
    # Given
    mock_client = MagicMock()
    service = ExtractorService(config_with_jobs, http_client=mock_client)
    
    mock_extractor = AsyncMock()
    mock_extractor.extract.return_value = ResponseDTO(data=[], meta={"status": "success"})
    mock_factory.create_extractor.return_value = mock_extractor
    
    # When
    await service.extract_job("job_normal")
    
    # Then
    mock_factory.create_extractor.assert_called_once_with(
        job_id="job_normal",
        http_client=mock_client,
        config=config_with_jobs
    )