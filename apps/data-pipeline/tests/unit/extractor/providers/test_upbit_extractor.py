import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from datetime import datetime

# [Target Modules]
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ExtractorError
from src.common.interfaces import IHttpClient, IAuthStrategy
from src.extractor.providers.upbit_extractor import UPBITExtractor

# ========================================================================================
# [Mocks & Stubs] Value Object Replacement
# ========================================================================================

class MockRequestDTO:
    """테스트용 Request DTO (인자 수용 가능)"""
    def __init__(self, job_id: str = "test_job", params: dict = None):
        self.job_id = job_id
        self.params = params or {}

class MockJobPolicy:
    """Config 내 JobPolicy 객체 모방"""
    def __init__(self, provider: str = "UPBIT", path: str = "/v1/ticker", params: dict = None):
        self.provider = provider
        self.path = path
        self.params = params or {"market": "KRW-BTC"}

# ========================================================================================
# [Fixtures] Isolation & Setup
# ========================================================================================

@pytest.fixture(autouse=True)
def bypass_decorators():
    """타이머/재시도 데코레이터로 인한 테스트 지연 및 사이드 이펙트를 완벽히 차단합니다."""
    passthrough = lambda *args, **kwargs: lambda func: func
    with patch("src.common.decorators.rate_limit_decorator.rate_limit", side_effect=passthrough), \
         patch("src.common.decorators.retry_decorator.retry", side_effect=passthrough), \
         patch("src.common.decorators.log_decorator.log_decorator", side_effect=passthrough):
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
    """ConfigManager 객체 및 속성 모방"""
    config = MagicMock()
    config.upbit.base_url = "https://api.upbit.com"
    config.get_extractor.return_value = MockJobPolicy()
    return config

@pytest.fixture
def extractor(mock_http_client, mock_auth_strategy, mock_config):
    """
    AbstractExtractor의 __init__을 Mocking하여 의존성 주입을 완벽히 격리합니다.
    이를 통해 불필요한 초기화 에러를 방지하고 SUT(System Under Test)에 집중합니다.
    """
    def mock_super_init(self_obj, http_client):
        self_obj.http_client = http_client
        self_obj.config = mock_config  

    with patch("src.extractor.providers.upbit_extractor.AbstractExtractor.__init__", side_effect=mock_super_init, autospec=True):
        return UPBITExtractor(mock_http_client, mock_auth_strategy)

# ========================================================================================
# 1. 초기화 (Initialization)
# ========================================================================================

def test_init_01_missing_base_url(mock_http_client, mock_auth_strategy, mock_config):
    """[INIT-01] 필수 설정값인 base_url이 없을 경우 조기 예외 발생을 검증합니다."""
    # GIVEN: base_url이 빈 문자열로 설정되어 환경 변수 누락 상황 모사
    mock_config.upbit.base_url = ""
    
    def mock_super_init(self_obj, http_client):
        self_obj.http_client = http_client
        self_obj.config = mock_config

    with patch("src.extractor.providers.upbit_extractor.AbstractExtractor.__init__", side_effect=mock_super_init, autospec=True):
        # WHEN & THEN: 인스턴스 초기화 시도 시 ExtractorError가 즉각(Fail-Fast) 발생해야 함
        with pytest.raises(ExtractorError, match="Critical Config Error"):
            UPBITExtractor(mock_http_client, mock_auth_strategy)

# ========================================================================================
# 2. 요청 검증 (Validation)
# ========================================================================================

def test_req_01_missing_job_id(extractor):
    """[REQ-01] 요청 객체에 job_id가 누락된 경우를 검증합니다."""
    # GIVEN: job_id가 None인 비정상적인 RequestDTO
    request = MockRequestDTO(job_id=None)
    
    # WHEN & THEN: 로직 진입 전 사전 예외 발생 검증
    with pytest.raises(ExtractorError, match="'job_id'는 필수 항목입니다"):
        extractor._validate_request(request)

def test_req_02_policy_lookup_failure(extractor, mock_config):
    """[REQ-02] 식별자는 존재하나 Config에서 정책 조회 중 예외가 발생한 상황을 검증합니다."""
    # GIVEN: 정책 조회 메서드가 시스템 에러를 발생시키도록 Mocking
    request = MockRequestDTO(job_id="unknown_job")
    mock_config.get_extractor.side_effect = Exception("Policy Not Found")
    
    # WHEN & THEN: 내부 에러가 도메인 에러(ExtractorError)로 올바르게 래핑되는지 검증
    with pytest.raises(ExtractorError, match="설정 오류: Policy Not Found"):
        extractor._validate_request(request)

def test_req_03_provider_mismatch(extractor, mock_config):
    """[REQ-03] 정책의 Provider가 현재 추출기(UPBIT)와 불일치하는 잘못된 라우팅 상황을 방어합니다."""
    # GIVEN: KIS용 작업이 UPBIT 추출기로 잘못 전달된 상황 모사
    request = MockRequestDTO(job_id="kis_job")
    mock_config.get_extractor.return_value = MockJobPolicy(provider="KIS")
    
    # WHEN & THEN: API 제공자 불일치 에러 발생 검증 (방어 코드 동작)
    with pytest.raises(ExtractorError, match="API 제공자 불일치"):
        extractor._validate_request(request)

def test_req_04_valid_request(extractor, mock_config):
    """[REQ-04] 완벽하게 유효한 요청일 경우 예외 없이 검증을 통과하는 해피 패스를 검증합니다. (Branch 100% 달성)"""
    # GIVEN: 정상적인 식별자와 일치하는 Provider(UPBIT) 세팅
    request = MockRequestDTO(job_id="valid_upbit_job")
    mock_config.get_extractor.return_value = MockJobPolicy(provider="UPBIT")
    
    # WHEN & THEN: _validate_request 호출 시 어떠한 Exception도 발생하지 않고 정상 종료됨 (Coverage 89->exit 해결)
    try:
        extractor._validate_request(request)
    except Exception as e:
        pytest.fail(f"정상 요청에서 예상치 못한 예외가 발생했습니다: {e}")

# ========================================================================================
# 3. 통신 및 인가 (Fetch & Auth)
# ========================================================================================

@pytest.mark.asyncio
async def test_fetch_01_with_token_and_params(extractor, mock_http_client, mock_auth_strategy, mock_config):
    """[FETCH-01] JWT 토큰이 존재할 시 Header 주입 및 정적/동적 파라미터가 완벽히 병합됨을 검증합니다."""
    # GIVEN: AuthStrategy가 정상 토큰 반환, 정책과 요청에 파라미터 분산 배치
    mock_auth_strategy.get_token.return_value = "Bearer mock_token"
    mock_config.get_extractor.return_value = MockJobPolicy(path="/v1/ticker", params={"market": "KRW-BTC"})
    request = MockRequestDTO(job_id="test_job", params={"count": 10})
    
    # WHEN: API HTTP 비동기 통신 로직 호출
    await extractor._fetch_raw_data(request)
    
    # THEN: 헤더(토큰 포함), URL, 파라미터가 비즈니스 규칙에 맞게 병합 조립되어 IHttpClient에 전달됨
    mock_http_client.get.assert_awaited_once_with(
        "https://api.upbit.com/v1/ticker",
        headers={"accept": "application/json", "authorization": "Bearer mock_token"},
        params={"market": "KRW-BTC", "count": 10}
    )

@pytest.mark.asyncio
async def test_fetch_02_no_token_public_api(extractor, mock_http_client, mock_auth_strategy):
    """[FETCH-02] 인증이 불필요한 Public API의 경우 Authorization 헤더가 안전하게 생략됨을 검증합니다."""
    # GIVEN: AuthStrategy가 None 반환 (Public 시세 조회 등)
    mock_auth_strategy.get_token.return_value = None
    request = MockRequestDTO(job_id="test_job")
    
    # WHEN: API HTTP 비동기 통신 로직 호출
    await extractor._fetch_raw_data(request)
    
    # THEN: 전송 헤더에 'authorization' 키가 전혀 없음을 명시적으로 검증
    call_kwargs = mock_http_client.get.call_args.kwargs
    assert "authorization" not in call_kwargs["headers"]

# ========================================================================================
# 4. 응답 조립 (Response)
# ========================================================================================

def test_resp_01_upbit_business_error(extractor):
    """[RESP-01] 업비트 API가 HTTP 상태 코드는 200이나 Payload에 비즈니스 에러를 담아준 상황을 통제합니다."""
    # GIVEN: 파라미터 오류 등에 의한 업비트 고유 에러 응답 객체 모사
    raw_response = {
        "error": {
            "name": "invalid_parameter",
            "message": "지원하지 않는 마켓입니다."
        }
    }
    
    # WHEN & THEN: 정규표현식 이스케이프 경고 방지를 위해 Raw String(r"")을 사용하여 매칭 및 예외 발생 검증
    with pytest.raises(ExtractorError, match=r"업비트 API 실패: 지원하지 않는 마켓입니다. \(이름: invalid_parameter\)"):
        extractor._create_response(raw_response, job_id="test_job")

def test_resp_02_successful_response(extractor):
    """[RESP-02] 정상 데이터 수신 시 파이프라인이 즉시 소비 가능한 표준 컨트랙트(ExtractedDTO)로 래핑함을 검증합니다."""
    # GIVEN: 시세 캔들 등 순수 데이터가 담긴 JSON List 반환
    raw_response = [{"market": "KRW-BTC", "trade_price": 50000000}]
    job_id = "test_job"
    
    # WHEN: 응답 DTO 생성 로직 호출
    result = extractor._create_response(raw_response, job_id)
    
    # THEN: 원본 데이터가 보호되며, 추출 출처/작업ID/상태코드가 정확히 할당되어 반환됨
    assert isinstance(result, ExtractedDTO)
    assert result.data == raw_response
    assert result.meta["source"] == "UPBIT"
    assert result.meta["job_id"] == "test_job"
    assert result.meta["status_code"] == "OK"
    assert "extracted_at" in result.meta