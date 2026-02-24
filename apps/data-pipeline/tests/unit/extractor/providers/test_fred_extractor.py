import pytest
import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# [Target Modules]
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ETLError, ExtractorError
from src.common.interfaces import IHttpClient
from src.common.config import ConfigManager

# ========================================================================================
# [Mocks & Stubs] DTO Replacement (Isolation)
# ========================================================================================

class MockRequestDTO:
    """테스트용 Request DTO (인자 수용 가능)"""
    def __init__(self, job_id: str = "unknown", params: Dict = None):
        self.job_id = job_id
        self.params = params or {}

class MockExtractedDTO:
    """테스트용 Extracted DTO (인자 수용 가능)"""
    def __init__(self, data: Any = None, meta: Dict = None):
        self.data = data
        self.meta = meta or {}

class MockSecretStr:
    """Pydantic SecretStr 동작 모방"""
    def __init__(self, value: str):
        self._value = value
    
    def get_secret_value(self) -> str:
        return self._value

# ========================================================================================
# [Fixtures] 테스트 환경 설정 및 격리
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_environment():
    """
    [Critical Fix]
    1. LogManager 및 Decorator 패치 (Pass-through)
    2. DTO 패치 (TypeError 방지) - src.common.dtos 레벨에서 적용
    """
    passthrough = lambda *args, **kwargs: lambda func: func
    
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger, \
         patch("src.common.decorators.log_decorator.log_decorator", side_effect=passthrough), \
         patch("src.common.decorators.retry_decorator.retry", side_effect=passthrough), \
         patch("src.common.decorators.rate_limit_decorator.rate_limit", side_effect=passthrough), \
         patch("src.common.dtos.RequestDTO", side_effect=MockRequestDTO), \
         patch("src.common.dtos.ExtractedDTO", side_effect=MockExtractedDTO):
        
        mock_get_logger.return_value = MagicMock()
        yield

@pytest.fixture
def mock_http_client():
    client = MagicMock(spec=IHttpClient)
    client.get = AsyncMock()
    return client

@pytest.fixture
def mock_config():
    """
    [Fix] spec 제한을 제거하고 extraction_policy를 실제 딕셔너리로 구성하여 
    AttributeError를 방지합니다.
    """
    config = MagicMock() # spec=ConfigManager 제거
    
    # FRED 섹션 설정
    config.fred = MagicMock()
    config.fred.base_url = "https://api.stlouisfed.org/fred"
    config.fred.api_key = MockSecretStr("test_key")
    
    # Policy Helper
    def make_policy(provider="FRED", params=None):
        p = MagicMock()
        p.provider = provider
        p.params = params or {}
        p.path = "/series/observations"
        return p

    # Policy Dictionary (실제 Dict 사용)
    config.extraction_policy = {
        "JOB_01": make_policy(params={"series_id": "GDP"}),
        "JOB_NO_PARAM": make_policy(params={}),
        "JOB_KIS": make_policy(provider="KIS")
    }
    
    return config

@pytest.fixture
def fred_extractor(mock_http_client, mock_config):
    """
    모듈 임포트 시점 제어 및 클린 룸 테스트 환경 제공
    """
    module_name = "src.extractor.providers.fred_extractor"
    # 기존 모듈 삭제 후 재임포트 (mock_environment 패치 적용)
    if module_name in sys.modules:
        del sys.modules[module_name]
    
    from src.extractor.providers.fred_extractor import FREDExtractor
    return FREDExtractor(mock_http_client, mock_config)

# ========================================================================================
# 1. 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_empty_base_url(mock_http_client, mock_config):
    """[INIT-01] base_url이 비어있으면 초기화 단계에서 즉시 에러 발생"""
    from src.extractor.providers.fred_extractor import FREDExtractor
    
    mock_config.fred.base_url = ""
    with pytest.raises(ExtractorError, match="base_url.*empty"):
        FREDExtractor(mock_http_client, mock_config)

def test_init_02_missing_api_key(mock_http_client, mock_config):
    """[INIT-02] api_key가 None이면 초기화 실패"""
    from src.extractor.providers.fred_extractor import FREDExtractor
    
    mock_config.fred.api_key = None
    with pytest.raises(ExtractorError, match="api_key.*missing"):
        FREDExtractor(mock_http_client, mock_config)

def test_init_03_valid_init(fred_extractor):
    """[INIT-03] 유효한 설정인 경우 인스턴스가 정상적으로 생성됨"""
    assert fred_extractor.config.fred.base_url == "https://api.stlouisfed.org/fred"

# ========================================================================================
# 2. 유효성 검증 테스트 (Validation - Logic & MC/DC)
# ========================================================================================

def test_val_00_missing_job_id(fred_extractor):
    """[VAL-00] Request에 job_id가 없는 경우 유효성 검증 실패"""
    request = MockRequestDTO(job_id="", params={})
    
    with pytest.raises(ExtractorError, match="'job_id' is mandatory"):
        fred_extractor._validate_request(request)

def test_val_01_policy_missing(fred_extractor):
    """[VAL-01] Config에 정의되지 않은 job_id 요청 시 실패"""
    request = MockRequestDTO(job_id="UNKNOWN_JOB", params={})
    
    with pytest.raises(ExtractorError, match="Policy not found"):
        fred_extractor._validate_request(request)

def test_val_02_provider_mismatch(fred_extractor):
    """[VAL-02] 해당 Policy의 Provider가 'FRED'가 아닌 경우 실패"""
    request = MockRequestDTO(job_id="JOB_KIS", params={})
    
    with pytest.raises(ExtractorError, match="Provider Mismatch"):
        fred_extractor._validate_request(request)

@pytest.mark.asyncio
async def test_val_03_mcdc_series_id_in_policy(fred_extractor, mock_http_client):
    """[VAL-03] [MC/DC] series_id가 Policy에만 존재하는 경우 -> 성공"""
    request = MockRequestDTO(job_id="JOB_01", params={})
    mock_http_client.get.return_value = {"observations": []}
    
    await fred_extractor.extract(request)
    mock_http_client.get.assert_called_once()

@pytest.mark.asyncio
async def test_val_04_mcdc_series_id_in_request(fred_extractor, mock_http_client):
    """[VAL-04] [MC/DC] series_id가 Request에만 존재하는 경우 -> 성공"""
    request = MockRequestDTO(job_id="JOB_NO_PARAM", params={"series_id": "CPI"})
    mock_http_client.get.return_value = {"observations": []}
    
    await fred_extractor.extract(request)
    
    call_kwargs = mock_http_client.get.call_args.kwargs
    assert call_kwargs['params']['series_id'] == "CPI"

def test_val_05_mcdc_series_id_missing(fred_extractor):
    """[VAL-05] [MC/DC] series_id가 Policy와 Request 어디에도 없는 경우 -> 실패"""
    request = MockRequestDTO(job_id="JOB_NO_PARAM", params={})
    
    with pytest.raises(ExtractorError, match="'series_id' is required"):
        fred_extractor._validate_request(request)

# ========================================================================================
# 3. 실행 및 병합 테스트 (Execution & Data Merging)
# ========================================================================================

@pytest.mark.asyncio
async def test_exec_01_param_merging(fred_extractor, mock_http_client):
    """[EXEC-01] 파라미터 병합 로직 검증"""
    request = MockRequestDTO(job_id="JOB_01", params={"frequency": "m"})
    mock_http_client.get.return_value = {}

    await fred_extractor.extract(request)

    call_params = mock_http_client.get.call_args.kwargs['params']
    assert call_params["series_id"] == "GDP"   # Policy 값
    assert call_params["frequency"] == "m"     # Request 값
    assert call_params["file_type"] == "json"  # 시스템 강제
    assert call_params["api_key"] == "test_key"

@pytest.mark.asyncio
async def test_exec_02_metadata_injection(fred_extractor, mock_http_client):
    """[EXEC-02] ExtractedDTO 반환 타입 및 메타데이터 확인"""
    request = MockRequestDTO(job_id="JOB_01", params={})
    mock_http_client.get.return_value = {"observations": []}

    response = await fred_extractor.extract(request)

    assert isinstance(response, MockExtractedDTO)
    assert response.meta["job_id"] == "JOB_01"
    assert response.meta["source"] == "FRED"

# ========================================================================================
# 4. 에러 처리 테스트 (Error Handling)
# ========================================================================================

@pytest.mark.asyncio
async def test_err_01_logical_error_in_body(fred_extractor, mock_http_client):
    """[ERR-01] Body에 에러 메시지가 포함된 경우 (Logical Error)"""
    request = MockRequestDTO(job_id="JOB_01", params={})
    mock_http_client.get.return_value = {
        "error_code": 400,
        "error_message": "Bad Request"
    }

    with pytest.raises(ExtractorError, match="FRED API Failed"):
        await fred_extractor.extract(request)

@pytest.mark.asyncio
async def test_err_02_unexpected_exception_wrapping(fred_extractor, mock_http_client):
    """[ERR-02] 예상치 못한 시스템 에러 발생 시 래핑 검증"""
    request = MockRequestDTO(job_id="JOB_01", params={})
    mock_http_client.get.side_effect = KeyError("Unexpected")

    with pytest.raises(ExtractorError, match="작업 중 알 수 없는 시스템 오류 발생"):
        await fred_extractor.extract(request)

@pytest.mark.asyncio
async def test_err_03_retry_decorator_trigger(fred_extractor, mock_http_client):
    """[ERR-03] 네트워크 에러 발생 시 (데코레이터 제거 상태) 동작 확인"""
    # 데코레이터 패치(Pass-through) 상태이므로 즉시 에러가 발생하거나 래핑됨
    request = MockRequestDTO(job_id="JOB_01", params={})
    mock_http_client.get.side_effect = ValueError("Network Timeout")
    
    with pytest.raises(ExtractorError):
        await fred_extractor.extract(request)