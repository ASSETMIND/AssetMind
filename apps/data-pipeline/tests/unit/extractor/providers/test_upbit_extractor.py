import pytest
import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from typing import Dict, Any, Optional

# [Target Modules]
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ExtractorError
from src.common.interfaces import IHttpClient, IAuthStrategy
from src.common.config import ConfigManager

# ========================================================================================
# [Mocks & Stubs] DTO & Value Object Replacement (Isolation)
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

class MockJobPolicy:
    """Config 내 JobPolicy 객체 모방"""
    def __init__(self, provider: str = "UPBIT", path: str = "/v1/candles/minutes/1", 
                 params: Dict = None):
        self.provider = provider
        self.path = path
        self.params = params or {}

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
    """비동기 HTTP 요청을 모방하는 Mock Client"""
    client = MagicMock(spec=IHttpClient)
    client.get = AsyncMock()
    return client

@pytest.fixture
def mock_auth_strategy():
    """인증 토큰 발급을 모방하는 Mock Strategy"""
    strategy = MagicMock(spec=IAuthStrategy)
    strategy.get_token = AsyncMock(return_value="Bearer test_token")
    return strategy

@pytest.fixture
def mock_config():
    """
    [Fix] spec 제한을 제거하고 extraction_policy를 실제 딕셔너리로 구성
    """
    config = MagicMock() # spec=ConfigManager 제거
    
    # UPBIT 섹션 설정
    config.upbit = MagicMock()
    config.upbit.base_url = "https://api.upbit.com"
    
    # Extraction Policy (Dict 접근 허용)
    config.extraction_policy = {
        "job_valid": MockJobPolicy(params={"market": "KRW-BTC"}),
        "job_param_override": MockJobPolicy(params={"cnt": 1}),
        "job_kis": MockJobPolicy(provider="KIS"),  # Provider Mismatch 테스트용
        "job_no_params": MockJobPolicy(params={}), # 파라미터 경고 테스트용
    }
    return config

@pytest.fixture
def extractor(mock_http_client, mock_auth_strategy, mock_config):
    """
    모듈 임포트 시점 제어 및 클린 룸 테스트 환경 제공 (SUT)
    """
    module_name = "src.extractor.providers.upbit_extractor"
    # 기존 모듈 삭제 후 재임포트 (mock_environment 패치 적용)
    if module_name in sys.modules:
        del sys.modules[module_name]
    
    from src.extractor.providers.upbit_extractor import UPBITExtractor
    return UPBITExtractor(mock_http_client, mock_auth_strategy, mock_config)

# ========================================================================================
# 1. 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_critical_config_error(mock_http_client, mock_auth_strategy, mock_config):
    """[INIT-01] upbit.base_url이 비어있는 경우 초기화 단계에서 즉시 실패 (Fail-Fast)"""
    from src.extractor.providers.upbit_extractor import UPBITExtractor
    mock_config.upbit.base_url = ""
    with pytest.raises(ExtractorError, match="Critical Config Error"):
        UPBITExtractor(mock_http_client, mock_auth_strategy, mock_config)

# ========================================================================================
# 2. 요청 검증 테스트 (Validation - MC/DC)
# ========================================================================================

def test_req_01_missing_job_id(extractor):
    """[REQ-01] Request에 job_id가 없는 경우 유효성 검증 실패"""
    request = MockRequestDTO(job_id=None) # type: ignore
    with pytest.raises(ExtractorError, match="'job_id' is mandatory"):
        extractor._validate_request(request)

def test_req_02_policy_not_found(extractor):
    """[REQ-02] Config에 정의되지 않은 job_id 요청 시 실패"""
    request = MockRequestDTO(job_id="job_unknown")
    with pytest.raises(ExtractorError, match="Policy not found"):
        extractor._validate_request(request)

def test_req_03_provider_mismatch(extractor):
    """[REQ-03] Provider가 UPBIT가 아닌 경우 (예: KIS) 요청 거부"""
    request = MockRequestDTO(job_id="job_kis")
    with pytest.raises(ExtractorError, match="Provider Mismatch"):
        extractor._validate_request(request)

def test_req_04_missing_params_warning(extractor):
    """[REQ-04] [MC/DC] 정책/요청에 market, markets 모두 없으면 Warning 로그 기록"""
    # mock_logger는 autouse=True인 mock_environment에서 처리됨.
    # 여기서는 로직 실행 시 에러가 없는지만 확인.
    # (로거 호출 확인을 위해서는 별도의 Mock Logger Fixture가 필요하나, 
    # 현재 구조상 Pass-through 패치되므로 MagicMock을 획득하기 어려움. 로직 통과만 검증)
    request = MockRequestDTO(job_id="job_no_params")
    extractor._validate_request(request)

# ========================================================================================
# 3. 정상 흐름 및 기능 테스트 (Functional & Flow)
# ========================================================================================

@pytest.mark.asyncio
async def test_flow_01_param_override(extractor, mock_http_client):
    """[FLOW-01] 파라미터 병합 시 Request Params가 Static Policy보다 우선순위 가짐"""
    request = MockRequestDTO(job_id="job_param_override", params={"cnt": 10})
    mock_http_client.get.return_value = {"market": "KRW-BTC"}
    
    await extractor.extract(request)
    
    call_args = mock_http_client.get.call_args
    merged_params = call_args.kwargs['params']
    assert merged_params["cnt"] == 10

@pytest.mark.asyncio
async def test_flow_02_url_construction(extractor, mock_http_client, mock_config):
    """[FLOW-02] Base URL과 Policy Path가 결합되어 완전한 URL 호출"""
    mock_config.upbit.base_url = "https://api.upbit-test.com"
    mock_config.extraction_policy["job_valid"].path = "/v1/test/candles"
    request = MockRequestDTO(job_id="job_valid")
    mock_http_client.get.return_value = [{"market": "KRW-BTC"}]
    
    await extractor.extract(request)
    
    expected_url = "https://api.upbit-test.com/v1/test/candles"
    mock_http_client.get.assert_called_with(expected_url, headers=ANY, params=ANY)

# ========================================================================================
# 4. 보안 및 인증 테스트 (Security)
# ========================================================================================

@pytest.mark.asyncio
async def test_sec_01_token_injection(extractor, mock_http_client, mock_auth_strategy):
    """[SEC-01] AuthStrategy가 토큰을 반환하면 Authorization 헤더에 주입됨"""
    request = MockRequestDTO(job_id="job_valid")
    mock_http_client.get.return_value = [{"market": "KRW-BTC"}]
    
    await extractor.extract(request)
    
    call_headers = mock_http_client.get.call_args.kwargs['headers']
    assert call_headers["authorization"] == "Bearer test_token"

@pytest.mark.asyncio
async def test_sec_02_no_token_public_api(extractor, mock_http_client, mock_auth_strategy):
    """[SEC-02] AuthStrategy가 None을 반환(Public API)하면 헤더에 포함되지 않음"""
    mock_auth_strategy.get_token.return_value = None
    request = MockRequestDTO(job_id="job_valid")
    mock_http_client.get.return_value = [{"market": "KRW-BTC"}]
    
    await extractor.extract(request)
    
    call_headers = mock_http_client.get.call_args.kwargs['headers']
    assert "authorization" not in call_headers

# ========================================================================================
# 5. 데이터 안정성 및 견고성 테스트 (Robustness & Data)
# ========================================================================================

@pytest.mark.asyncio
async def test_data_01_api_error_response(extractor, mock_http_client):
    """[DATA-01] API 응답 본문에 'error' 키가 존재하면 ExtractorError 발생"""
    mock_response = {"error": {"name": "invalid_query", "message": "query param error"}}
    mock_http_client.get.return_value = mock_response
    request = MockRequestDTO(job_id="job_valid")
    
    with pytest.raises(ExtractorError, match="UPBIT API Failed"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_data_02_success_response_mapping(extractor, mock_http_client):
    """[DATA-02] 정상 JSON 응답 시 ExtractedDTO 매핑 및 메타데이터 검증"""
    mock_data = [{"market": "KRW-BTC", "price": 50000}]
    mock_http_client.get.return_value = mock_data
    request = MockRequestDTO(job_id="job_valid")
    
    response = await extractor.extract(request)
    
    assert isinstance(response, MockExtractedDTO)
    assert response.data == mock_data
    assert response.meta["source"] == "UPBIT"
    assert response.meta["job_id"] == "job_valid"
    assert response.meta["status_code"] == "OK"

# ========================================================================================
# 6. 예외 처리 테스트 (Exception Handling)
# ========================================================================================

@pytest.mark.asyncio
async def test_err_01_auth_exception_propagation(extractor, mock_auth_strategy):
    """[ERR-01] AuthStrategy에서 발생한 ExtractorError는 그대로 상위 전파"""
    # 데코레이터가 Pass-through 상태이므로, ETLError로 래핑되지 않고 전파됨
    mock_auth_strategy.get_token.side_effect = ExtractorError("Auth Failed")
    request = MockRequestDTO(job_id="job_valid")
    
    with pytest.raises(ExtractorError, match="Auth Failed"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_err_02_system_error_wrapping(extractor, mock_http_client):
    """[ERR-02] 실행 중 예상치 못한 에러(KeyError 등) 발생 시 ExtractorError로 래핑"""
    mock_http_client.get.side_effect = KeyError("Unexpected Key")
    request = MockRequestDTO(job_id="job_valid")
    
    with pytest.raises(ExtractorError, match="작업 중 알 수 없는 시스템 오류 발생"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_err_03_logic_exception_propagation(extractor):
    """[ERR-03] 내부 로직 검증 중 발생한 ExtractorError는 래핑되지 않고 전파"""
    # _validate_request를 Mocking하여 강제 에러 발생
    with patch.object(extractor, '_validate_request', side_effect=ExtractorError("Validation Fail")):
        request = MockRequestDTO(job_id="job_valid")
        
        with pytest.raises(ExtractorError, match="Validation Fail"):
            await extractor.extract(request)