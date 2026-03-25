import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

# 대상 모듈
from src.extractor.providers.ecos_extractor import ECOSExtractor
from src.common.exceptions import ExtractorError

# ========================================================================================
# [Mocks & Stubs] 의존성 격리를 위한 테스트 전용 객체
# ========================================================================================

class MockRequestDTO:
    """RequestDTO 의존성을 격리하기 위한 Mock 클래스"""
    def __init__(self, job_id: str = "job_ecos", params: dict = None):
        self.job_id = job_id
        self.params = params or {}

class MockExtractedDTO:
    """ExtractedDTO 의존성을 격리하기 위한 Mock 클래스"""
    def __init__(self, data: any = None, meta: dict = None):
        self.data = data
        self.meta = meta or {}

class MockPolicy:
    """Config 추출 정책 반환용 Mock 클래스"""
    def __init__(self, provider="ECOS", path="StatisticSearch", params=None):
        self.provider = provider
        self.path = path
        self.params = params or {"stat_code": "100Y", "cycle": "D", "item_code1": "0001"}

# ========================================================================================
# [Fixtures] 단위 테스트 환경 통제
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_environment():
    """데코레이터 및 공통 모듈에 의한 사이드 이펙트(Delay, 예외 등)를 차단합니다."""
    passthrough = lambda *args, **kwargs: lambda func: func
    with patch("src.common.decorators.log_decorator.log_decorator", passthrough), \
         patch("src.common.decorators.retry_decorator.retry", passthrough), \
         patch("src.common.decorators.rate_limit_decorator.rate_limit", passthrough), \
         patch("src.extractor.providers.ecos_extractor.ExtractedDTO", MockExtractedDTO):
        yield

@pytest.fixture
def mock_http_client():
    """네트워크 I/O를 통제하는 Mock HTTP 클라이언트"""
    client = MagicMock()
    client.get = AsyncMock()
    return client

@pytest.fixture
def mock_config():
    """ConfigManager와 ECOS 전용 설정을 흉내내는 Mock 객체"""
    config = MagicMock()
    config.ecos.base_url = "https://ecos.bok.or.kr/api"
    
    # 평문 API Key 반환 모방 (SecretStr 호환)
    mock_secret = MagicMock()
    mock_secret.get_secret_value.return_value = "test_api_key"
    config.ecos.api_key = mock_secret
    
    # 기본 정책 셋업
    config.get_extractor.return_value = MockPolicy()
    return config

@pytest.fixture
def mock_abstract_init(mock_config):
    """
    ECOSExtractor는 AbstractExtractor를 상속받습니다.
    super().__init__ 내부에서 self.config가 세팅된다고 가정하고 이를 강제 주입합니다.
    (TypeError 방지 및 의존성 주입 해결)
    """
    def fake_init(self, http_client):
        self.http_client = http_client
        self.config = mock_config
        
    with patch("src.extractor.providers.ecos_extractor.AbstractExtractor.__init__", new=fake_init):
        yield

@pytest.fixture
def extractor(mock_http_client, mock_abstract_init):
    """테스트 대상 ECOSExtractor 인스턴스"""
    return ECOSExtractor(mock_http_client)

# ========================================================================================
# [INIT] 인스턴스 초기화 테스트
# ========================================================================================

def test_init_01_base_url_empty(mock_http_client, mock_config, mock_abstract_init):
    """[INIT-01] GIVEN: base_url이 비어있는 상태 WHEN: 초기화 THEN: ExtractorError 발생"""
    # GIVEN
    mock_config.ecos.base_url = ""
    # WHEN & THEN
    with pytest.raises(ExtractorError, match="'base_url' is empty"):
        ECOSExtractor(mock_http_client)

def test_init_02_api_key_missing(mock_http_client, mock_config, mock_abstract_init):
    """[INIT-02] GIVEN: api_key 평문이 누락된 상태 WHEN: 초기화 THEN: ExtractorError 발생"""
    # GIVEN
    mock_config.ecos.api_key.get_secret_value.return_value = ""
    # WHEN & THEN
    with pytest.raises(ExtractorError, match="'api_key' is missing"):
        ECOSExtractor(mock_http_client)

def test_init_03_valid_init(extractor):
    """[INIT-03] GIVEN: 정상적인 설정 객체 WHEN: 초기화 THEN: URL 및 평문 키 적재 완료"""
    # GIVEN & WHEN (Fixture에서 처리됨)
    # THEN
    assert extractor.base_url == "https://ecos.bok.or.kr/api"
    assert extractor.api_key == "test_api_key"

# ========================================================================================
# [REQ] 파라미터 및 정책 검증 테스트
# ========================================================================================

def test_req_01_missing_job_id(extractor):
    """[REQ-01] GIVEN: job_id가 누락된 요청 WHEN: 검증 로직 실행 THEN: ExtractorError 발생"""
    # GIVEN
    request = MockRequestDTO(job_id=None)
    # WHEN & THEN
    with pytest.raises(ExtractorError, match="'job_id'는 필수 항목입니다"):
        extractor._validate_request(request)

def test_req_02_policy_exception(extractor, mock_config):
    """[REQ-02] GIVEN: 정책 조회 중 알 수 없는 예외 발생 WHEN: 검증 로직 실행 THEN: ExtractorError 래핑"""
    # GIVEN
    request = MockRequestDTO(job_id="job_unknown")
    mock_config.get_extractor.side_effect = Exception("Policy Not Found")
    # WHEN & THEN
    with pytest.raises(ExtractorError, match="설정 오류: Policy Not Found"):
        extractor._validate_request(request)

def test_req_03_provider_mismatch(extractor, mock_config):
    """[REQ-03] GIVEN: ECOS가 아닌 타 제공자(KIS) 정책 WHEN: 검증 로직 실행 THEN: ExtractorError 발생"""
    # GIVEN
    request = MockRequestDTO(job_id="job_kis")
    mock_config.get_extractor.return_value = MockPolicy(provider="KIS")
    # WHEN & THEN
    with pytest.raises(ExtractorError, match="API 제공자 불일치"):
        extractor._validate_request(request)

def test_req_04_default_date_injection(extractor, mock_config):
    """[REQ-04] GIVEN: 요청과 정책 모두 날짜가 누락됨 WHEN: 검증 로직 실행 THEN: 최근 30일 기본값 주입"""
    # GIVEN
    request = MockRequestDTO(job_id="job_ecos", params={})
    mock_config.get_extractor.return_value = MockPolicy(params={})
    
    # WHEN
    extractor._validate_request(request)
    
    # THEN
    assert "start_date" in request.params
    assert "end_date" in request.params
    assert len(request.params["start_date"]) == 8 # YYYYMMDD 검증

def test_req_05_dates_already_present(extractor, mock_config):
    """[REQ-05] GIVEN: 날짜 파라미터가 이미 존재 WHEN: 검증 로직 실행 THEN: 기본값 주입 분기 스킵 (Missing Branch 97, 101 커버)"""
    # GIVEN
    request = MockRequestDTO(job_id="job_ecos", params={"start_date": "20230101", "end_date": "20231231"})
    mock_config.get_extractor.return_value = MockPolicy(params={})
    
    # WHEN
    extractor._validate_request(request)
    
    # THEN
    assert request.params["start_date"] == "20230101"
    assert request.params["end_date"] == "20231231"

# ========================================================================================
# [FETCH] URL 조립 및 통신 테스트
# ========================================================================================

@pytest.mark.asyncio
async def test_fetch_01_url_construction(extractor, mock_http_client, mock_config):
    """[FETCH-01] GIVEN: 필수 파라미터 제공 WHEN: 데이터 패치 요청 THEN: ECOS 고유의 순차적 Path URL 호출"""
    # GIVEN
    request = MockRequestDTO(job_id="job_ecos", params={"start_date": "20230101", "end_date": "20230131"})
    mock_config.get_extractor.return_value = MockPolicy(path="/StatisticSearch/")
    mock_http_client.get.return_value = {"mock": "response"}
    
    # WHEN
    result = await extractor._fetch_raw_data(request)
    
    # THEN
    assert result == {"mock": "response"}
    
    # URL 조립 순서: /base_path/api_key/json/kr/1/100000/stat_code/cycle/start_date/end_date/item_code
    expected_url = (
        "https://ecos.bok.or.kr/api/StatisticSearch/"
        "test_api_key/json/kr/1/100000/"
        "100Y/D/20230101/20230131/0001"
    )
    mock_http_client.get.assert_called_once_with(expected_url)

# ========================================================================================
# [RESP] 응답 데이터 파싱 및 표준화 테스트
# ========================================================================================

def test_resp_01_root_error(extractor, mock_config):
    """[RESP-01] GIVEN: Root 객체에 RESULT 에러 코드 존재 WHEN: 응답 생성 THEN: ExtractorError 발생"""
    # GIVEN
    raw_data = {"RESULT": {"CODE": "ERR-100", "MESSAGE": "Auth Failed"}}
    # WHEN & THEN
    with pytest.raises(ExtractorError, match="ECOS API 실패: Auth Failed"):
        extractor._create_response(raw_data, "job_ecos")

def test_resp_02_missing_service_key(extractor, mock_config):
    """[RESP-02] GIVEN: 정책상의 서비스 경로(Key)가 Root에 없음 WHEN: 응답 생성 THEN: ExtractorError 발생"""
    # GIVEN
    raw_data = {"WrongServiceKey": {"row": []}}
    mock_config.get_extractor.return_value = MockPolicy(path="StatisticSearch")
    # WHEN & THEN
    with pytest.raises(ExtractorError, match="잘못된 ECOS 응답: Root key 'StatisticSearch'를 찾을 수 없습니다."):
        extractor._create_response(raw_data, "job_ecos")

def test_resp_03_inner_error(extractor, mock_config):
    """[RESP-03] GIVEN: 서비스 객체 내부에 RESULT 에러 코드 존재 WHEN: 응답 생성 THEN: ExtractorError 발생"""
    # GIVEN
    raw_data = {
        "StatisticSearch": {
            "RESULT": {"CODE": "ERR-200", "MESSAGE": "No Data Found"}
        }
    }
    mock_config.get_extractor.return_value = MockPolicy(path="StatisticSearch")
    # WHEN & THEN
    with pytest.raises(ExtractorError, match="ECOS API 실패: No Data Found"):
        extractor._create_response(raw_data, "job_ecos")

def test_resp_04_inner_success(extractor, mock_config):
    """[RESP-04] GIVEN: 서비스 내부에 정상 상태코드(INFO-000) 존재 WHEN: 응답 생성 THEN: 성공 DTO 반환"""
    # GIVEN
    raw_data = {
        "StatisticSearch": {
            "RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"},
            "row": [{"data": 100}]
        }
    }
    mock_config.get_extractor.return_value = MockPolicy(path="StatisticSearch")
    
    # WHEN
    result = extractor._create_response(raw_data, "job_ecos")
    
    # THEN
    assert result.data == raw_data
    assert result.meta["status"] == "success"
    assert result.meta["source"] == "ECOS"
    assert result.meta["job_id"] == "job_ecos"

def test_resp_05_implicit_success(extractor, mock_config):
    """[RESP-05] GIVEN: 서비스 내부에 RESULT 객체가 아예 없음 WHEN: 응답 생성 THEN: 암시적 성공 간주 및 반환"""
    # GIVEN
    raw_data = {
        "StatisticSearch": {
            "row": [{"data": 100}]
        }
    }
    mock_config.get_extractor.return_value = MockPolicy(path="StatisticSearch")
    
    # WHEN
    result = extractor._create_response(raw_data, "job_ecos")
    
    # THEN
    assert result.data == raw_data
    assert result.meta["status"] == "success"

def test_resp_06_root_success_ignored(extractor, mock_config):
    """[RESP-06] GIVEN: Root에 성공 코드(INFO-000) 포함 WHEN: 응답 생성 THEN: 에러 없이 파싱 진행 (Missing Branch 171 커버)"""
    # GIVEN
    raw_data = {
        "RESULT": {"CODE": "INFO-000", "MESSAGE": "Root Success"},
        "StatisticSearch": {
            "RESULT": {"CODE": "INFO-000", "MESSAGE": "Inner Success"},
            "row": [{"data": 100}]
        }
    }
    mock_config.get_extractor.return_value = MockPolicy(path="StatisticSearch")
    
    # WHEN
    result = extractor._create_response(raw_data, "job_ecos")
    
    # THEN
    assert result.data == raw_data
    assert result.meta["status"] == "success"