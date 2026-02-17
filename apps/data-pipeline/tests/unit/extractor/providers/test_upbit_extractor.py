import pytest
import asyncio
import types
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from typing import Dict, Any, Optional

# [Target Modules] 테스트 대상 및 의존성 모듈
from src.extractor.providers.upbit_extractor import UPBITExtractor
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ExtractorError
from src.common.interfaces import IHttpClient, IAuthStrategy
from src.common.config import ConfigManager

# ========================================================================================
# [Mocks & Stubs] 외부 의존성 격리를 위한 모의 객체 정의
# ========================================================================================

class MockJobPolicy:
    """Config 내 JobPolicy 객체 모방 (설정 주입용 Stub)"""
    def __init__(self, provider: str = "UPBIT", path: str = "/v1/candles/minutes/1", 
                 params: Dict = None):
        self.provider = provider
        self.path = path
        self.params = params or {}

# ========================================================================================
# [Helpers] 테스트 유틸리티
# ========================================================================================

def get_unwrapped_function(func):
    """데코레이터가 적용된 함수에서 원본 함수를 추출합니다.
    @functools.wraps로 래핑된 경우 __wrapped__ 속성을 따라갑니다.
    """
    current = func
    while hasattr(current, "__wrapped__"):
        current = current.__wrapped__
    return current

# ========================================================================================
# [Fixtures] 테스트 환경 설정 및 의존성 주입
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger():
    """
    [Core Fix] 
    LogManager가 초기화될 때 전역 ConfigManager를 참조하여 발생하는 RuntimeError를 방지합니다.
    """
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance
        yield mock_logger_instance

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
    """정상 상태의 Config 객체 (Happy Path 기준)"""
    config = MagicMock(spec=ConfigManager)
    
    # UPBIT 섹션 설정
    config.upbit = MagicMock()
    config.upbit.base_url = "https://api.upbit.com"
    
    # Extraction Policy 설정
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
    테스트 대상 인스턴스 (SUT: System Under Test)
    [중요] 단위 테스트의 격리성을 위해 데코레이터(@rate_limit, @retry 등)를 벗겨냅니다.
    """
    sut = UPBITExtractor(mock_http_client, mock_auth_strategy, mock_config)
    
    # 1. 클래스 메서드에서 원본 함수 추출 (Unwrap)
    # UPBITExtractor._fetch_raw_data는 바인딩되지 않은 함수일 수도, 바인딩된 메서드일 수도 있음
    # 여기서는 안전하게 클래스에서 가져와서 처리
    original_func = get_unwrapped_function(UPBITExtractor._fetch_raw_data)
    
    # 2. 인스턴스 메서드로 바인딩하여 교체 (Monkey Patching on Instance)
    # 이렇게 하면 이 테스트 인스턴스(sut)에서만 데코레이터가 제거된 상태로 동작함
    sut._fetch_raw_data = types.MethodType(original_func, sut)
    
    return sut

# ========================================================================================
# 1. 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_critical_config_error(mock_http_client, mock_auth_strategy, mock_config):
    """[INIT-01] upbit.base_url이 비어있으면 초기화 단계에서 즉시 실패 (Fail-Fast)"""
    mock_config.upbit.base_url = ""
    with pytest.raises(ExtractorError, match="Critical Config Error"):
        UPBITExtractor(mock_http_client, mock_auth_strategy, mock_config)

# ========================================================================================
# 2. 요청 검증 테스트 (Validation - MC/DC)
# ========================================================================================

def test_req_01_missing_job_id(extractor):
    """[REQ-01] Request에 job_id가 없는 경우 유효성 검증 실패"""
    request = RequestDTO(job_id=None) # type: ignore
    with pytest.raises(ExtractorError, match="'job_id' is mandatory"):
        extractor._validate_request(request)

def test_req_02_policy_not_found(extractor):
    """[REQ-02] Config에 정의되지 않은 job_id 요청 시 실패"""
    request = RequestDTO(job_id="job_unknown")
    with pytest.raises(ExtractorError, match="Policy not found"):
        extractor._validate_request(request)

def test_req_03_provider_mismatch(extractor):
    """[REQ-03] Provider가 UPBIT가 아닌 경우 (예: KIS) 요청 거부"""
    request = RequestDTO(job_id="job_kis")
    with pytest.raises(ExtractorError, match="Provider Mismatch"):
        extractor._validate_request(request)

def test_req_04_missing_params_warning(extractor, mock_logger):
    """[REQ-04] [MC/DC] 정책/요청에 market, markets 모두 없으면 Warning 로그 기록"""
    request = RequestDTO(job_id="job_no_params")
    extractor._validate_request(request)
    mock_logger.warning.assert_called_with(ANY)
    assert "Parameter Warning" in str(mock_logger.warning.call_args)

# ========================================================================================
# 3. 정상 흐름 및 기능 테스트 (Functional & Flow)
# ========================================================================================

@pytest.mark.asyncio
async def test_flow_01_param_override(extractor, mock_http_client):
    """[FLOW-01] 파라미터 병합 시 Request Params가 Static Policy보다 우선순위 가짐"""
    request = RequestDTO(job_id="job_param_override", params={"cnt": 10})
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
    request = RequestDTO(job_id="job_valid")
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
    request = RequestDTO(job_id="job_valid")
    mock_http_client.get.return_value = [{"market": "KRW-BTC"}]
    
    await extractor.extract(request)
    
    call_headers = mock_http_client.get.call_args.kwargs['headers']
    assert call_headers["authorization"] == "Bearer test_token"

@pytest.mark.asyncio
async def test_sec_02_no_token_public_api(extractor, mock_http_client, mock_auth_strategy):
    """[SEC-02] AuthStrategy가 None을 반환(Public API)하면 헤더에 포함되지 않음"""
    mock_auth_strategy.get_token.return_value = None
    request = RequestDTO(job_id="job_valid")
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
    request = RequestDTO(job_id="job_valid")
    
    with pytest.raises(ExtractorError, match="UPBIT API Failed"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_data_02_success_response_mapping(extractor, mock_http_client):
    """[DATA-02] 정상 JSON 응답 시 ExtractedDTO 매핑 및 메타데이터 검증"""
    mock_data = [{"market": "KRW-BTC", "price": 50000}]
    mock_http_client.get.return_value = mock_data
    request = RequestDTO(job_id="job_valid")
    
    response = await extractor.extract(request)
    
    assert isinstance(response, ExtractedDTO)
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
    # 데코레이터를 제거했으므로, ETLError로 래핑되지 않고 ExtractorError가 그대로 올라와야 함
    mock_auth_strategy.get_token.side_effect = ExtractorError("Auth Failed")
    request = RequestDTO(job_id="job_valid")
    
    with pytest.raises(ExtractorError, match="Auth Failed"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_err_02_system_error_wrapping(extractor, mock_http_client):
    """[ERR-02] 실행 중 예상치 못한 에러(KeyError 등) 발생 시 ExtractorError로 래핑"""
    mock_http_client.get.side_effect = KeyError("Unexpected Key")
    request = RequestDTO(job_id="job_valid")
    
    # AbstractExtractor에서 "작업 중 알 수 없는 시스템 오류 발생" 메시지로 래핑함
    # 따라서 "시스템 오류" 또는 "System Error"가 아닌 실제 코드의 메시지를 검증해야 함
    with pytest.raises(ExtractorError, match="시스템 오류"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_err_03_logic_exception_propagation(extractor):
    """[ERR-03] 내부 로직 검증 중 발생한 ExtractorError는 래핑되지 않고 전파"""
    # _validate_request는 Template Method 패턴에서 I/O 실행 전에 호출되므로 
    # AbstractExtractor의 try-except 블록 내에서 실행되더라도, 
    # ETLError(도메인 에러)로 간주되어 re-raise 되어야 함.
    with patch.object(extractor, '_validate_request', side_effect=ExtractorError("Validation Fail")):
        request = RequestDTO(job_id="job_valid")
        
        with pytest.raises(ExtractorError, match="Validation Fail"):
            await extractor.extract(request)

def test_dec_01_decorator_application():
    """[DEC-01] 원본 클래스 메서드에는 데코레이터가 적용되어 있어야 함"""
    # 주의: extractor 픽스처는 데코레이터를 벗겨내므로, 여기서는 클래스 자체를 검사
    method = UPBITExtractor._fetch_raw_data
    assert hasattr(method, "__wrapped__"), "Production code should have decorators applied"