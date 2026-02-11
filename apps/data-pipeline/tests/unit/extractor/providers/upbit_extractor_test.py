import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from typing import Dict, Any, Optional

# [Target Modules] 테스트 대상 및 의존성 모듈
from src.extractor.providers.upbit_extractor import UPBITExtractor
from src.extractor.domain.dtos import RequestDTO, ResponseDTO
from src.extractor.domain.exceptions import ExtractorError
from src.extractor.domain.interfaces import IHttpClient, IAuthStrategy
from src.common.config import AppConfig

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
# [Fixtures] 테스트 환경 설정 및 의존성 주입
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger():
    """
    [Core Fix] 
    LogManager가 초기화될 때 전역 AppConfig를 참조하여 발생하는 RuntimeError를 방지합니다.
    kis_extractor_test.py와 동일한 전략으로 로거 생성을 우회합니다.
    """
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger, \
         patch("src.extractor.providers.upbit_extractor.log_decorator") as mock_dec:
        
        # 1. 로거 호출 시 MagicMock 반환 (메서드 호출 추적 가능)
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance
        
        # 2. 데코레이터 Pass-through 처리
        mock_dec.side_effect = lambda *args, **kwargs: lambda func: func
        
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
    config = MagicMock(spec=AppConfig)
    
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
    """테스트 대상 인스턴스 (SUT: System Under Test)"""
    return UPBITExtractor(mock_http_client, mock_auth_strategy, mock_config)

# ========================================================================================
# 1. 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_critical_config_error(mock_http_client, mock_auth_strategy, mock_config):
    """[INIT-01] upbit.base_url이 비어있으면 초기화 단계에서 즉시 실패 (Fail-Fast)"""
    # Given: 잘못된 설정 주입 (Base URL 누락)
    mock_config.upbit.base_url = ""
    
    # When & Then: 인스턴스 생성 시도 시 예외 발생 검증
    with pytest.raises(ExtractorError, match="Critical Config Error"):
        UPBITExtractor(mock_http_client, mock_auth_strategy, mock_config)

# ========================================================================================
# 2. 요청 검증 테스트 (Validation - MC/DC)
# ========================================================================================

def test_req_01_missing_job_id(extractor):
    """[REQ-01] Request에 job_id가 없는 경우 유효성 검증 실패"""
    # Given: job_id가 None인 잘못된 요청
    request = RequestDTO(job_id=None) # type: ignore
    
    # When & Then: 예외 발생
    with pytest.raises(ExtractorError, match="'job_id' is mandatory"):
        extractor._validate_request(request)

def test_req_02_policy_not_found(extractor):
    """[REQ-02] Config에 정의되지 않은 job_id 요청 시 실패"""
    # Given: 정책에 없는 Job ID
    request = RequestDTO(job_id="job_unknown")
    
    # When & Then: 정책 조회 실패 예외 확인
    with pytest.raises(ExtractorError, match="Policy not found"):
        extractor._validate_request(request)

def test_req_03_provider_mismatch(extractor):
    """[REQ-03] Provider가 UPBIT가 아닌 경우 (예: KIS) 요청 거부"""
    # Given: Provider가 "KIS"로 설정된 Job
    request = RequestDTO(job_id="job_kis")
    
    # When & Then: Provider 불일치 예외 확인
    with pytest.raises(ExtractorError, match="Provider Mismatch"):
        extractor._validate_request(request)

def test_req_04_missing_params_warning(extractor, mock_logger):
    """[REQ-04] [MC/DC] 정책/요청에 market, markets 모두 없으면 Warning 로그 기록"""
    # Given: 필수 파라미터가 없는 Job Policy
    request = RequestDTO(job_id="job_no_params") # params={}
    
    # When: 검증 수행 (예외는 발생하지 않음)
    extractor._validate_request(request)
    
    # Then: Logger.warning 호출 여부 검증
    mock_logger.warning.assert_called_with(ANY)
    # 구체적인 메시지 내용 검증 (Optional)
    assert "Parameter Warning" in str(mock_logger.warning.call_args)

# ========================================================================================
# 3. 정상 흐름 및 기능 테스트 (Functional & Flow)
# ========================================================================================

@pytest.mark.asyncio
async def test_flow_01_param_override(extractor, mock_http_client):
    """[FLOW-01] 파라미터 병합 시 Request Params가 Static Policy보다 우선순위 가짐"""
    # Given: Policy={"cnt": 1}, Request={"cnt": 10}
    request = RequestDTO(job_id="job_param_override", params={"cnt": 10})
    mock_http_client.get.return_value = {"market": "KRW-BTC"}
    
    # When: 추출 실행
    await extractor.extract(request)
    
    # Then: 실제 호출된 파라미터가 덮어씌워졌는지(Override) 확인
    call_args = mock_http_client.get.call_args
    merged_params = call_args.kwargs['params']
    assert merged_params["cnt"] == 10  # Policy 값 1이 10으로 교체됨

@pytest.mark.asyncio
async def test_flow_02_url_construction(extractor, mock_http_client, mock_config):
    """[FLOW-02] Base URL과 Policy Path가 결합되어 완전한 URL 호출"""
    # Given: 특정 URL 및 Path 설정
    mock_config.upbit.base_url = "https://api.upbit-test.com"
    mock_config.extraction_policy["job_valid"].path = "/v1/test/candles"
    
    request = RequestDTO(job_id="job_valid")
    mock_http_client.get.return_value = [{"market": "KRW-BTC"}]
    
    # When: 추출 실행
    await extractor.extract(request)
    
    # Then: 결합된 URL로 호출되었는지 검증
    expected_url = "https://api.upbit-test.com/v1/test/candles"
    mock_http_client.get.assert_called_with(expected_url, headers=ANY, params=ANY)

# ========================================================================================
# 4. 보안 및 인증 테스트 (Security)
# ========================================================================================

@pytest.mark.asyncio
async def test_sec_01_token_injection(extractor, mock_http_client, mock_auth_strategy):
    """[SEC-01] AuthStrategy가 토큰을 반환하면 Authorization 헤더에 주입됨"""
    # Given: AuthStrategy가 유효 토큰 반환 (Default Mock Behavior)
    request = RequestDTO(job_id="job_valid")
    mock_http_client.get.return_value = [{"market": "KRW-BTC"}]
    
    # When: 추출 실행
    await extractor.extract(request)
    
    # Then: Authorization 헤더 검증
    call_headers = mock_http_client.get.call_args.kwargs['headers']
    assert call_headers["authorization"] == "Bearer test_token"

@pytest.mark.asyncio
async def test_sec_02_no_token_public_api(extractor, mock_http_client, mock_auth_strategy):
    """[SEC-02] AuthStrategy가 None을 반환(Public API)하면 헤더에 포함되지 않음"""
    # Given: 토큰 없음 설정
    mock_auth_strategy.get_token.return_value = None
    request = RequestDTO(job_id="job_valid")
    mock_http_client.get.return_value = [{"market": "KRW-BTC"}]
    
    # When: 추출 실행
    await extractor.extract(request)
    
    # Then: Authorization 헤더 부재 확인
    call_headers = mock_http_client.get.call_args.kwargs['headers']
    assert "authorization" not in call_headers

# ========================================================================================
# 5. 데이터 안정성 및 견고성 테스트 (Robustness & Data)
# ========================================================================================

@pytest.mark.asyncio
async def test_data_01_api_error_response(extractor, mock_http_client):
    """[DATA-01] API 응답 본문에 'error' 키가 존재하면 ExtractorError 발생"""
    # Given: UPBIT 에러 응답 포맷
    mock_response = {"error": {"name": "invalid_query", "message": "query param error"}}
    mock_http_client.get.return_value = mock_response
    request = RequestDTO(job_id="job_valid")
    
    # When & Then: 비즈니스 예외 발생 검증
    with pytest.raises(ExtractorError, match="UPBIT API Failed"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_data_02_success_response_mapping(extractor, mock_http_client):
    """[DATA-02] 정상 JSON 응답 시 ResponseDTO 매핑 및 메타데이터 검증"""
    # Given: 정상 응답
    mock_data = [{"market": "KRW-BTC", "price": 50000}]
    mock_http_client.get.return_value = mock_data
    request = RequestDTO(job_id="job_valid")
    
    # When: 추출 실행
    response = await extractor.extract(request)
    
    # Then: DTO 구조 및 메타데이터 확인
    assert isinstance(response, ResponseDTO)
    assert response.data == mock_data
    assert response.meta["source"] == "UPBIT"
    assert response.meta["job_id"] == "job_valid"
    assert response.meta["status_code"] == "OK"

# ========================================================================================
# 6. 예외 처리 및 데코레이터 테스트 (Exception & Decorators)
# ========================================================================================

@pytest.mark.asyncio
async def test_err_01_auth_exception_propagation(extractor, mock_auth_strategy):
    """[ERR-01] AuthStrategy에서 발생한 ExtractorError는 그대로 상위 전파"""
    # Given: 인증 과정에서 ExtractorError 발생
    mock_auth_strategy.get_token.side_effect = ExtractorError("Auth Failed")
    request = RequestDTO(job_id="job_valid")
    
    # When & Then: 재포장 없이 그대로 전파되는지 확인
    with pytest.raises(ExtractorError, match="Auth Failed"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_err_02_system_error_wrapping(extractor, mock_http_client):
    """[ERR-02] 실행 중 예상치 못한 에러(KeyError 등) 발생 시 ExtractorError로 래핑"""
    # Given: 로직 내부에서 예상치 못한 에러 발생
    mock_http_client.get.side_effect = KeyError("Unexpected Key")
    request = RequestDTO(job_id="job_valid")
    
    # When & Then: System Error로 래핑 확인
    with pytest.raises(ExtractorError, match="System Error"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_err_03_logic_exception_propagation(extractor, mock_http_client):
    """[ERR-03] 내부 로직 검증 중 발생한 ExtractorError는 래핑되지 않고 전파"""
    # Given: 강제로 ExtractorError 발생시키기 위해 validate_request 모킹
    with patch.object(extractor, '_validate_request', side_effect=ExtractorError("Validation Fail")):
        request = RequestDTO(job_id="job_valid")
        
        # When & Then: 래핑 없이 원본 에러 전파 확인
        with pytest.raises(ExtractorError, match="Validation Fail"):
            await extractor.extract(request)

def test_dec_01_decorator_application(extractor):
    """[DEC-01] _fetch_raw_data 메서드에 데코레이터가 적용되어 있는지 검증"""
    # Given: 테스트 대상 메서드
    method = extractor._fetch_raw_data
    
    # When & Then: __wrapped__ 속성 존재 여부로 데코레이터 적용 확인
    assert hasattr(method, "__wrapped__"), "Decorators should be applied to _fetch_raw_data"