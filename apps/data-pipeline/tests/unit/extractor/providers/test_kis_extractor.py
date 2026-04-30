import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ExtractorError
from src.extractor.providers.kis_extractor import KISExtractor

# ========================================================================================
# [Fixtures] 의존성 격리 및 통제 (Root Cause 해결)
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_decorators():
    """
    [CRITICAL] 데코레이터로 인한 사이드 이펙트(Delay, Retry 등)를 원천 차단하여 
    순수 로직만 검증할 수 있도록 Pass-through 처리합니다.
    """
    passthrough = lambda *args, **kwargs: lambda func: func
    with patch("src.extractor.providers.kis_extractor.log_decorator", side_effect=passthrough), \
         patch("src.extractor.providers.kis_extractor.rate_limit", side_effect=passthrough), \
         patch("src.extractor.providers.kis_extractor.retry", side_effect=passthrough):
        yield

@pytest.fixture
def mock_http_client():
    """비동기 네트워크 통신 모방"""
    client = MagicMock()
    client.get = AsyncMock()
    return client

@pytest.fixture
def mock_auth_strategy():
    """토큰 발급 로직 모방"""
    strategy = MagicMock()
    strategy.get_token = AsyncMock(return_value="Bearer test_token")
    return strategy

@pytest.fixture
def mock_config():
    """
    KIS API 필수 환경 변수 및 각 Job ID별 정책을 모방하여 반환합니다.
    """
    config = MagicMock()
    config.kis.base_url = "https://api.kis.com"
    config.kis.app_key.get_secret_value.return_value = "plain_app_key"
    config.kis.app_secret.get_secret_value.return_value = "plain_app_secret"
    
    def get_extractor_mock(job_id):
        policy = MagicMock()
        if job_id == "valid_job":
            policy.provider = "KIS"
            policy.tr_id = "TR_123"
            policy.path = "/v1/stock"
            policy.params = {"static_param": "A"}
            return policy
        elif job_id == "fred_job":
            policy.provider = "FRED"
            return policy
        elif job_id == "no_tr_job":
            policy.provider = "KIS"
            policy.tr_id = None
            return policy
        else:
            raise Exception("Policy Not Found")
            
    config.get_extractor.side_effect = get_extractor_mock
    return config

@pytest.fixture
def extractor(mock_http_client, mock_auth_strategy, mock_config):
    """
    부모 클래스(AbstractExtractor)의 불필요한 초기화 간섭을 막고
    Config만 주입된 완벽하게 격리된 KISExtractor SUT를 생성합니다.
    """
    with patch("src.extractor.providers.kis_extractor.AbstractExtractor.__init__", 
               lambda self, client: setattr(self, 'config', mock_config) or setattr(self, 'http_client', client)):
        return KISExtractor(mock_http_client, mock_auth_strategy)

# ========================================================================================
# 1. 초기화 (Initialization) 테스트 [Lines 62-75 커버]
# ========================================================================================

def test_init_01_missing_base_url(mock_http_client, mock_auth_strategy, mock_config):
    """[INIT-01] base_url이 비어있을 경우 인스턴스화 시점에 조기 실패 (Fail-Fast) 검증"""
    # GIVEN
    mock_config.kis.base_url = ""
    
    # WHEN / THEN
    with patch("src.extractor.providers.kis_extractor.AbstractExtractor.__init__", 
               lambda self, client: setattr(self, 'config', mock_config)):
        with pytest.raises(ExtractorError, match="Critical Config Error"):
            KISExtractor(mock_http_client, mock_auth_strategy)

def test_init_02_success(mock_http_client, mock_auth_strategy, mock_config):
    """[INIT-02] 유효한 설정 환경에서 시크릿 평문 복호화 및 초기화 완료 검증"""
    # GIVEN
    mock_config.kis.base_url = "https://api.kis.com"
    
    # WHEN
    with patch("src.extractor.providers.kis_extractor.AbstractExtractor.__init__", 
               lambda self, client: setattr(self, 'config', mock_config)):
        instance = KISExtractor(mock_http_client, mock_auth_strategy)
    
    # THEN
    assert instance.base_url == "https://api.kis.com"
    assert instance.app_key == "plain_app_key"
    assert instance.app_secret == "plain_app_secret"

# ========================================================================================
# 2. 요청 검증 (Validation) 테스트 [Lines 86-105 커버]
# ========================================================================================

def test_req_01_missing_job_id(extractor):
    """[REQ-01] job_id가 누락된 악의적/비정상 요청의 차단 검증"""
    # GIVEN
    request = RequestDTO(job_id=None)
    
    # WHEN / THEN
    with pytest.raises(ExtractorError, match="'job_id'는 필수 항목입니다"):
        extractor._validate_request(request)

def test_req_02_policy_exception(extractor):
    """[REQ-02] 시스템(Config)에 등록되지 않은 job_id 요청의 차단 검증"""
    # GIVEN
    request = RequestDTO(job_id="unknown_job")
    
    # WHEN / THEN
    with pytest.raises(ExtractorError, match="설정 오류: Policy Not Found"):
        extractor._validate_request(request)

def test_req_03_provider_mismatch(extractor):
    """[REQ-03] KIS 추출기에 타 제공자(FRED 등) 요청이 유입되었을 때 라우팅 방어 검증"""
    # GIVEN
    request = RequestDTO(job_id="fred_job")
    
    # WHEN / THEN
    with pytest.raises(ExtractorError, match="API 제공자 불일치"):
        extractor._validate_request(request)

def test_req_04_missing_tr_id(extractor):
    """[REQ-04] KIS 필수 스펙인 tr_id가 정책에서 누락되었을 때의 차단 검증"""
    # GIVEN
    request = RequestDTO(job_id="no_tr_job")
    
    # WHEN / THEN
    with pytest.raises(ExtractorError, match="'tr_id'가 누락되었습니다"):
        extractor._validate_request(request)

def test_req_05_success(extractor):
    """[REQ-05] 완벽한 요청 시 예외 발생 없이 Validation 통과 여부 검증"""
    # GIVEN
    request = RequestDTO(job_id="valid_job")
    
    # WHEN / THEN
    extractor._validate_request(request) # 에러 없이 통과해야 함

# ========================================================================================
# 3. 데이터 실행 (Fetch) 테스트 [Lines 125-150 커버]
# ========================================================================================

@pytest.mark.asyncio
async def test_fetch_01_success(extractor, mock_http_client, mock_auth_strategy):
    """[FETCH-01] 토큰 발급, 파라미터 병합, 헤더 주입 등 네트워크 호출 전/후 프로세스 무결성 검증"""
    # GIVEN
    request = RequestDTO(job_id="valid_job", params={"dynamic_param": "B"})
    mock_http_client.get.return_value = {"rt_cd": "0", "data": "OK"}
    
    # WHEN
    result = await extractor._fetch_raw_data(request)
    
    # THEN
    mock_auth_strategy.get_token.assert_awaited_once_with(mock_http_client)
    mock_http_client.get.assert_awaited_once_with(
        "https://api.kis.com/v1/stock",
        headers={
            "content-type": "application/json; charset=utf-8",
            "authorization": "Bearer test_token",
            "appkey": "plain_app_key",
            "appsecret": "plain_app_secret",
            "tr_id": "TR_123"
        },
        params={"static_param": "A", "dynamic_param": "B"}
    )
    assert result == {"rt_cd": "0", "data": "OK"}

# ========================================================================================
# 4. 응답 파싱 (Create Response) 테스트 [Lines 168-176 커버]
# ========================================================================================

def test_res_01_biz_error(extractor):
    """[RES-01] HTTP 200 응답이더라도 rt_cd가 '0'이 아니면 비즈니스 실패로 간주하는 로직 검증"""
    # GIVEN
    raw_data = {"rt_cd": "1", "msg": "잘못된 계좌번호입니다"}
    job_id = "valid_job"
    
    # WHEN / THEN
    with pytest.raises(ExtractorError, match="KIS API 실패: 잘못된 계좌번호입니다 \\(Code: 1\\)"):
        extractor._create_response(raw_data, job_id)

def test_res_02_success(extractor):
    """[RES-02] 정상 응답 시 표준 포맷(ExtractedDTO)으로 데이터와 메타데이터가 래핑되는지 검증"""
    # GIVEN
    raw_data = {"rt_cd": "0", "output": ["A", "B"]}
    job_id = "valid_job"
    
    # WHEN
    result = extractor._create_response(raw_data, job_id)
    
    # THEN
    assert isinstance(result, ExtractedDTO)
    assert result.data == raw_data
    assert result.meta["source"] == "KIS"
    assert result.meta["job_id"] == "valid_job"
    assert result.meta["status_code"] == "0"
    assert "extracted_at" in result.meta