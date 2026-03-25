import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# ========================================================================================
# [Mocks & Stubs] DTO 및 도메인 의존성 격리
# ========================================================================================
class MockRequestDTO:
    def __init__(self, job_id: str = None, params: Dict = None):
        self.job_id = job_id
        self.params = params or {}

class MockExtractedDTO:
    def __init__(self, data: Any = None, meta: Dict = None):
        self.data = data
        self.meta = meta or {}

class ExtractorError(Exception):
    """테스트용 Mock ExtractorError"""
    pass

# ========================================================================================
# [Fixtures] 가혹한 수준의 격리 및 환경 통제
# ========================================================================================
@pytest.fixture(autouse=True)
def isolate_environment():
    """
    GIVEN: 테스트 구동 환경
    WHEN: FREDExtractor 모듈이 임포트 및 평가되기 전
    THEN: 모든 외부 의존성(데코레이터, DTO, 로거 등)을 순수 Mock으로 치환하여 Side-Effect 원천 차단
    """
    passthrough = lambda *args, **kwargs: lambda func: func
    
    with patch("src.common.log.LogManager.get_logger") as mock_logger, \
         patch("src.common.decorators.log_decorator.log_decorator", side_effect=passthrough), \
         patch("src.common.decorators.retry_decorator.retry", side_effect=passthrough), \
         patch("src.common.decorators.rate_limit_decorator.rate_limit", side_effect=passthrough), \
         patch("src.common.dtos.RequestDTO", MockRequestDTO), \
         patch("src.common.dtos.ExtractedDTO", MockExtractedDTO), \
         patch("src.common.exceptions.ExtractorError", ExtractorError):
        
        mock_logger.return_value = MagicMock()
        yield

@pytest.fixture
def mock_http_client():
    """HTTP 클라이언트 Mocking (비동기 get 메서드 포함)"""
    client = MagicMock()
    client.get = AsyncMock()
    return client

@pytest.fixture
def mock_config():
    """FREDExtractor 구동을 위한 최상위 ConfigManager Mocking"""
    config = MagicMock()
    config.fred.base_url = "https://api.stlouisfed.org/fred"
    config.fred.api_key.get_secret_value.return_value = "TEST_API_KEY"
    return config

@pytest.fixture
def fred_extractor(mock_http_client, mock_config):
    """
    GIVEN: 정상적인 HTTP Client와 Config
    WHEN: 부모 클래스의 초기화를 낚아채어(Patch) 의존성을 주입하고 인스턴스화
    THEN: 완벽히 통제된 FREDExtractor 인스턴스 반환
    """
    # [근본 원인 해결] 기존 테스트는 부모 클래스(__init__)의 인자 구조가 달라 인스턴스화에 실패했음.
    # AbstractExtractor.__init__를 Patch하여 self.config를 런타임에 직접 주입하는 방식으로 제어권 탈환.
    def mock_base_init(self, http_client):
        self.http_client = http_client
        self.config = mock_config

    from src.extractor.providers.fred_extractor import FREDExtractor
    
    with patch("src.extractor.providers.fred_extractor.AbstractExtractor.__init__", autospec=True, side_effect=mock_base_init):
        return FREDExtractor(mock_http_client)

# ========================================================================================
# 1. 초기화 테스트 (Initialization) : 방어 로직 검증
# ========================================================================================
def test_init_01_missing_base_url(mock_http_client, mock_config):
    """
    GIVEN: Config 내 FRED base_url이 비어있음
    WHEN: FREDExtractor 초기화
    THEN: ExtractorError 발생 (조기 실패)
    """
    mock_config.fred.base_url = ""
    
    from src.extractor.providers.fred_extractor import FREDExtractor
    def mock_base_init(self, http_client):
        self.config = mock_config
        self.http_client = http_client

    with patch("src.extractor.providers.fred_extractor.AbstractExtractor.__init__", autospec=True, side_effect=mock_base_init):
        with pytest.raises(ExtractorError, match="base_url.*누락"):
            FREDExtractor(mock_http_client)

def test_init_02_missing_api_key(mock_http_client, mock_config):
    """
    GIVEN: Config 내 FRED api_key가 비어있음
    WHEN: FREDExtractor 초기화
    THEN: ExtractorError 발생 (조기 실패)
    """
    mock_config.fred.api_key.get_secret_value.return_value = ""
    
    from src.extractor.providers.fred_extractor import FREDExtractor
    def mock_base_init(self, http_client):
        self.config = mock_config
        self.http_client = http_client

    with patch("src.extractor.providers.fred_extractor.AbstractExtractor.__init__", autospec=True, side_effect=mock_base_init):
        with pytest.raises(ExtractorError, match="api_key.*누락"):
            FREDExtractor(mock_http_client)

def test_init_03_valid_initialization(fred_extractor):
    """
    GIVEN: 정상적인 base_url과 api_key
    WHEN: 인스턴스 생성
    THEN: 멤버 변수에 평문값 할당 완료
    """
    assert fred_extractor.base_url == "https://api.stlouisfed.org/fred"
    assert fred_extractor.api_key == "TEST_API_KEY"

# ========================================================================================
# 2. 유효성 검증 테스트 (Validation - Logic & MC/DC)
# ========================================================================================
def test_val_01_missing_job_id(fred_extractor):
    """
    GIVEN: job_id가 없는 RequestDTO
    WHEN: _validate_request 호출
    THEN: ExtractorError 발생
    """
    request = MockRequestDTO(job_id=None)
    with pytest.raises(ExtractorError, match="'job_id'는 필수 항목입니다"):
        fred_extractor._validate_request(request)

def test_val_02_policy_fetch_error(fred_extractor):
    """
    GIVEN: ConfigManager에서 정책 조회 중 예외 발생
    WHEN: _validate_request 호출
    THEN: ExtractorError로 래핑되어 발생
    """
    request = MockRequestDTO(job_id="JOB_INVALID")
    fred_extractor.config.get_extractor.side_effect = Exception("Config DB Down")
    
    with pytest.raises(ExtractorError, match="설정 오류: Config DB Down"):
        fred_extractor._validate_request(request)

def test_val_03_provider_mismatch(fred_extractor):
    """
    GIVEN: 타 API(Provider='ECOS') 정책이 FRED 수집기로 라우팅됨
    WHEN: _validate_request 호출
    THEN: ExtractorError 발생 (제공자 불일치)
    """
    request = MockRequestDTO(job_id="JOB_ECOS")
    mock_policy = MagicMock(provider="ECOS")
    fred_extractor.config.get_extractor.return_value = mock_policy
    
    with pytest.raises(ExtractorError, match="API 제공자 불일치"):
        fred_extractor._validate_request(request)

def test_val_04_missing_series_id_all(fred_extractor):
    """
    GIVEN: [MC/DC] series_id가 Policy와 Request 양쪽 모두 없음
    WHEN: _validate_request 호출
    THEN: ExtractorError 발생
    """
    request = MockRequestDTO(job_id="JOB_01", params={"limit": 10})
    mock_policy = MagicMock(provider="FRED", params={"frequency": "m"})
    fred_extractor.config.get_extractor.return_value = mock_policy
    
    with pytest.raises(ExtractorError, match="'series_id'가 필요합니다"):
        fred_extractor._validate_request(request)

def test_val_05_series_id_in_policy_only(fred_extractor):
    """
    GIVEN: [MC/DC] series_id가 Policy에만 존재
    WHEN: _validate_request 호출
    THEN: 예외 없이 통과
    """
    request = MockRequestDTO(job_id="JOB_01", params={})
    mock_policy = MagicMock(provider="FRED", params={"series_id": "GDP"})
    fred_extractor.config.get_extractor.return_value = mock_policy
    
    # 예외가 발생하지 않으면 테스트 성공
    fred_extractor._validate_request(request)

def test_val_06_series_id_in_request_only(fred_extractor):
    """
    GIVEN: [MC/DC] series_id가 Request에만 존재
    WHEN: _validate_request 호출
    THEN: 예외 없이 통과
    """
    request = MockRequestDTO(job_id="JOB_01", params={"series_id": "CPI"})
    mock_policy = MagicMock(provider="FRED", params={})
    fred_extractor.config.get_extractor.return_value = mock_policy
    
    # 예외가 발생하지 않으면 테스트 성공
    fred_extractor._validate_request(request)

# ========================================================================================
# 3. 실행 및 병합 테스트 (Execution & Merging)
# ========================================================================================
@pytest.mark.asyncio
async def test_exec_01_fetch_raw_data_merging(fred_extractor):
    """
    GIVEN: Policy 파라미터와 Request 파라미터가 혼재됨
    WHEN: _fetch_raw_data 호출
    THEN: Request 파라미터가 덮어쓰고, 시스템 포맷(json, api_key)이 강제 병합되어 HTTP GET 호출
    """
    request = MockRequestDTO(job_id="JOB_01", params={"frequency": "m", "limit": 100})
    mock_policy = MagicMock(path="/series/observations", params={"series_id": "GDP", "frequency": "a"})
    fred_extractor.config.get_extractor.return_value = mock_policy
    
    # 비동기 HTTP 응답 설정
    fred_extractor.http_client.get.return_value = {"observations": []}
    
    await fred_extractor._fetch_raw_data(request)
    
    # 병합된 파라미터 검증 (우선순위: Policy < Request < System Forced)
    fred_extractor.http_client.get.assert_called_once_with(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": "GDP",       # Policy에서 유지
            "frequency": "m",         # Request가 Policy('a')를 오버라이드
            "limit": 100,             # Request에서 추가
            "file_type": "json",      # System Forced (무결성 보장)
            "api_key": "TEST_API_KEY" # System Forced (무결성 보장)
        }
    )

# ========================================================================================
# 4. 응답 처리 테스트 (Response Parsing)
# ========================================================================================
def test_res_01_logical_error_in_payload(fred_extractor):
    """
    GIVEN: HTTP Status는 200이나 JSON 내부에 error_message가 존재함 (논리적 비즈니스 에러)
    WHEN: _create_response 호출
    THEN: 내부 에러를 감지하고 방어적으로 ExtractorError 발생
    """
    raw_data = {"error_code": 400, "error_message": "Bad Request"}
    
    with pytest.raises(ExtractorError, match="FRED API 실패: Bad Request \\(Code: 400\\)"):
        fred_extractor._create_response(raw_data, job_id="JOB_01")

def test_res_02_successful_response_packaging(fred_extractor):
    """
    GIVEN: 순수한 데이터만 포함된 정상 JSON 응답
    WHEN: _create_response 호출
    THEN: ExtractedDTO 표준 객체로 래핑 및 필수 메타데이터 주입 완료 반환
    """
    raw_data = {"observations": [{"date": "2023-01-01", "value": "123.4"}]}
    
    response_dto = fred_extractor._create_response(raw_data, job_id="JOB_01")
    
    # 객체 타입 및 원본 페이로드 무결성 검증
    assert isinstance(response_dto, MockExtractedDTO)
    assert response_dto.data == raw_data
    
    # 메타데이터 주입 검증
    meta = response_dto.meta
    assert meta["source"] == "FRED"
    assert meta["job_id"] == "JOB_01"
    assert meta["status_code"] == "200"
    assert "extracted_at" in meta