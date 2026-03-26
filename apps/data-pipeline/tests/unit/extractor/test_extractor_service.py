import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, Any

# [Target Modules]
from src.extractor.extractor_service import ExtractorService
from src.common.exceptions import ConfigurationError, ExtractorError, ETLError

# ========================================================================================
# [Mocks & Stubs] 격리된 환경을 위한 경량화 모의 객체
# ========================================================================================

class DummyPolicy:
    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}

class DummyConfig:
    def __init__(self, policies: Dict[str, DummyPolicy]):
        self.policies = policies
    
    def get_extractor(self, job_id: str):
        return self.policies.get(job_id)

class DummyDTO:
    def __init__(self, data: Any = None, meta: Dict = None):
        self.data = data or []
        self.meta = meta or {}

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger():
    """로그 출력을 차단하여 테스트 결과를 깔끔하게 유지합니다."""
    with patch("src.common.log.LogManager.get_logger") as mock:
        yield mock.return_value

@pytest.fixture
def mock_config():
    """ConfigManager가 반환할 가짜 정책 설정 객체"""
    policies = {
        "job_normal": DummyPolicy({"base_param": "default"}),
        "job_override": DummyPolicy({"target": "A"}),
        "job_domain_err": DummyPolicy({}),
        "job_sys_err": DummyPolicy({}),
        "job_batch_1": DummyPolicy({}),
        "job_batch_2": DummyPolicy({}),
        "job_batch_fail": DummyPolicy({})
    }
    with patch("src.extractor.extractor_service.ConfigManager.load") as mock_load:
        mock_load.return_value = DummyConfig(policies)
        yield mock_load.return_value

@pytest.fixture
def mock_http_adapter_cls():
    """내부 생명주기 제어 테스트를 위한 AsyncHttpAdapter Mock"""
    with patch("src.extractor.extractor_service.AsyncHttpAdapter") as mock_cls:
        instance = MagicMock()
        instance.close = AsyncMock()
        mock_cls.return_value = instance
        yield mock_cls

@pytest.fixture
def mock_factory():
    """실제 수집 로직(Network I/O) 방어를 위한 Factory Mock"""
    with patch("src.extractor.extractor_service.ExtractorFactory") as mock_fac:
        yield mock_fac

@pytest.fixture
def mock_request_dto():
    """RequestDTO 생성 방어"""
    with patch("src.extractor.extractor_service.RequestDTO") as mock_req:
        yield mock_req

# ========================================================================================
# 1. 자원 생명주기 관리 (Lifecycle Management)
# ========================================================================================

@pytest.mark.asyncio
async def test_life_01_internal_lifecycle(mock_http_adapter_cls, mock_config):
    """[LIFE-01] 외부 주입 없이 생성 시 내부에서 HTTP 클라이언트를 관리 및 소멸시킵니다."""
    # Given: 의존성 주입 없이 생성
    service = ExtractorService(http_client=None)
    
    # When: Context 진입 및 이탈
    async with service as srv:
        # Then 1: 어댑터 인스턴스화 수행
        mock_http_adapter_cls.assert_called_once()
        assert srv._owns_client is True
    
    # Then 2: 이탈 시 반드시 close() 대기
    mock_http_adapter_cls.return_value.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_life_02_external_lifecycle(mock_config):
    """[LIFE-02] 외부에서 주입된 클라이언트의 소유권은 서비스가 함부로 종료하지 않습니다."""
    # Given: 외부 생성 클라이언트
    mock_external_client = MagicMock()
    mock_external_client.close = AsyncMock()
    
    service = ExtractorService(http_client=mock_external_client)
    
    # When: Context 진입 및 이탈
    async with service as srv:
        assert srv._owns_client is False
        assert srv._http_client == mock_external_client
        
    # Then: 외부 자원이므로 close 호출 안 됨
    mock_external_client.close.assert_not_called()

@pytest.mark.asyncio
async def test_life_03_guard_clause(mock_config):
    """[LIFE-03] async with 블록 없이 메서드를 호출하면 즉시 차단합니다."""
    # Given: 초기화되지 않은 서비스
    service = ExtractorService()
    
    # When & Then: RuntimeError 발생
    with pytest.raises(RuntimeError, match="HTTP Client is not initialized"):
        await service.extract_job("job_normal")

@pytest.mark.asyncio
async def test_life_04_safe_close_on_exception(mock_http_adapter_cls, mock_config):
    """[LIFE-04] 파이프라인 중단 등 치명적 예외 시에도 자원은 안전하게 릴리즈됩니다."""
    # Given
    service = ExtractorService()
    
    # When: Context 안에서 예외 강제 발생
    with pytest.raises(ValueError):
        async with service:
            raise ValueError("Unexpected Crash")
            
    # Then: 오류와 무관하게 자원 해제 보장
    mock_http_adapter_cls.return_value.close.assert_awaited_once()

# ========================================================================================
# 2. 응답 정규화 (Response Normalization)
# ========================================================================================

def test_norm_01_fast_path(mock_config):
    """[NORM-01] 이미 성공 처리된 상태라면 추가 연산을 건너뜁니다."""
    # Given
    service = ExtractorService()
    dto = DummyDTO(meta={"status": "success"})
    
    # When
    res = service._normalize_response(dto)
    
    # Then
    assert res.meta["status"] == "success"

@pytest.mark.parametrize("status_code", ["200", "0", "OK", "SUCCESS", " ok "])
def test_norm_02_standard_codes(mock_config, status_code):
    """[NORM-02] 다양한 API 제공자의 성공 코드를 시스템 표준으로 매핑합니다."""
    # Given
    service = ExtractorService()
    dto = DummyDTO(meta={"status_code": status_code})
    
    # When
    res = service._normalize_response(dto)
    
    # Then
    assert res.meta["status"] == "success"

@pytest.mark.parametrize("empty_val", [None, ""])
def test_norm_03_robustness_empty_code(mock_config, empty_val):
    """[NORM-03] 상태 코드가 비어있는 결측치 응답도 성공으로 자가 보정합니다."""
    # Given
    service = ExtractorService()
    dto = DummyDTO(meta={"status_code": empty_val})
    
    # When
    res = service._normalize_response(dto)
    
    # Then
    assert res.meta["status"] == "success"
    assert res.meta["status_code"] == 200

@pytest.mark.parametrize("error_code", ["404", "500", "ERROR"])
def test_norm_04_safety_failure(mock_config, error_code):
    """[NORM-04] 실패 코드는 상태를 success로 변환하지 않고 유지합니다."""
    # Given
    service = ExtractorService()
    dto = DummyDTO(meta={"status_code": error_code})
    
    # When
    res = service._normalize_response(dto)
    
    # Then
    assert res.meta.get("status") != "success"

# ========================================================================================
# 3. 단건 수집 및 에러 래핑 (Single Job Execution)
# ========================================================================================

@pytest.mark.asyncio
async def test_job_01_policy_not_found(mock_config):
    """[JOB-01] YAML에 등록되지 않은 식별자 요청 시 정적 오류로 간주합니다."""
    # Given
    service = ExtractorService(http_client=MagicMock())
    
    # When & Then
    with pytest.raises(ConfigurationError, match="Job ID 'INVALID_JOB'를 찾을 수 없습니다."):
        await service.extract_job("INVALID_JOB")

@pytest.mark.asyncio
async def test_job_02_param_override(mock_config, mock_factory, mock_request_dto):
    """[JOB-02] 런타임에 유입된 파라미터가 정적 정책 파라미터를 덮어씁니다."""
    # Given
    service = ExtractorService(http_client=MagicMock())
    mock_extractor = AsyncMock()
    mock_extractor.extract.return_value = DummyDTO(meta={"status": "success"})
    mock_factory.create_extractor.return_value = mock_extractor
    
    # When
    await service.extract_job("job_override", override_params={"target": "B", "new_key": 1})
    
    # Then
    mock_request_dto.assert_called_once()
    passed_params = mock_request_dto.call_args.kwargs["params"]
    assert passed_params["target"] == "B"  # Overridden
    assert passed_params["new_key"] == 1   # Appended

@pytest.mark.asyncio
async def test_job_03_domain_error_bypass(mock_config, mock_factory):
    """[JOB-03] 하위 수집기에서 이미 규격화된 도메인 에러(ETLError)는 그대로 상위로 전파합니다."""
    # Given
    service = ExtractorService(http_client=MagicMock())
    mock_extractor = AsyncMock()
    mock_extractor.extract.side_effect = ETLError("Domain Known Error")
    mock_factory.create_extractor.return_value = mock_extractor
    
    # When & Then
    with pytest.raises(ETLError, match="Domain Known Error"):
        await service.extract_job("job_domain_err")

@pytest.mark.asyncio
async def test_job_04_system_error_wrapping(mock_config, mock_factory):
    """[JOB-04] 파싱 에러(KeyError) 등 예기치 못한 시스템 에러는 ExtractorError로 안전하게 래핑합니다."""
    # Given
    service = ExtractorService(http_client=MagicMock())
    mock_extractor = AsyncMock()
    mock_extractor.extract.side_effect = KeyError("Missing Data Key")
    mock_factory.create_extractor.return_value = mock_extractor
    
    # When & Then
    with pytest.raises(ExtractorError, match="Job 'job_sys_err' 작업 중 예상치 못한 오류가 발생."):
        await service.extract_job("job_sys_err")

# ========================================================================================
# 4. 배치 및 동시성 제어 (Batch Processing)
# ========================================================================================

@pytest.mark.asyncio
async def test_batch_01_mixed_inputs_and_isolation(mock_config, mock_factory):
    """[BATCH-01, 03] 다양한 입력 포맷을 처리하며, 특정 작업의 실패가 타 작업에 영향을 주지 않음을 검증합니다."""
    # Given
    service = ExtractorService(http_client=MagicMock())
    
    # Factory Mocking: job_batch_fail만 에러 발생, 나머지는 정상 응답
    def mock_create(job_id, **kwargs):
        ext = AsyncMock()
        if job_id == "job_batch_fail":
            ext.extract.side_effect = ValueError("Network Crash")
        else:
            ext.extract.return_value = DummyDTO(data=f"{job_id}_data", meta={"status": "success"})
        return ext
        
    mock_factory.create_extractor.side_effect = mock_create
    
    # 혼합된 입력: string 단일, tuple 형태 파라미터 주입, 예외 발생 타겟
    requests = ["job_batch_1", ("job_batch_2", {"dyn": 1}), "job_batch_fail"]
    
    # When
    results = await service.extract_batch(requests)
    
    # Then: 시스템 셧다운 없이 전체 리스트 3건이 모두 반환됨
    assert len(results) == 3
    assert results[0].data == "job_batch_1_data"
    assert results[1].data == "job_batch_2_data"
    
    # 실패한 건은 Exception 객체(래핑된 ExtractorError)로 리스트에 담겨 있음
    assert isinstance(results[2], ExtractorError)

@pytest.mark.asyncio
async def test_batch_02_invalid_type_defense(mock_config, mock_factory, mock_logger):
    """[BATCH-02] 타입이 잘못된 파라미터가 유입되어도 로깅 후 스킵하여 견고함을 유지합니다."""
    # Given
    service = ExtractorService(http_client=MagicMock())
    mock_extractor = AsyncMock()
    mock_extractor.extract.return_value = DummyDTO(meta={"status": "success"})
    mock_factory.create_extractor.return_value = mock_extractor
    
    requests = ["job_batch_1", 12345]  # Invalid int
    
    # When
    results = await service.extract_batch(requests)
    
    # Then
    assert len(results) == 1
    mock_logger.warning.assert_called()

@pytest.mark.asyncio
async def test_batch_04_empty_list(mock_config):
    """[BATCH-04] 빈 작업 목록이 들어오면 무의미한 I/O 사이클을 방지하고 즉시 반환합니다."""
    # Given
    service = ExtractorService(http_client=MagicMock())
    
    # When
    results = await service.extract_batch([])
    
    # Then
    assert results == []