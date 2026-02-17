import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, ANY

# [Target Modules] 테스트 대상 및 의존성
from src.extractor.providers.fred_extractor import FREDExtractor
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ETLError, ExtractorError

# ========================================================================================
# [Fixtures] Common Test Environment Setup
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger():
    """
    [Auto-use Fixture]
    LogManager 초기화 시 전역 Config를 로딩하는 부작용(Side Effect)을 차단합니다.
    """
    with patch("src.common.log.LogManager.get_logger") as mock_get:
        mock_get.return_value = MagicMock()
        yield mock_get

@pytest.fixture
def mock_http_client():
    """
    [Dependency Mock] 비동기 HTTP 클라이언트 모방.
    """
    client = MagicMock()
    client.get = AsyncMock() # 비동기 메서드 모방
    return client

@pytest.fixture
def mock_config():
    """
    [Config Mock] 별도의 Helper Class 없이 MagicMock으로 복잡한 설정 객체를 모방합니다.
    """
    config = MagicMock()
    
    # 1. FRED 섹션 설정 (기본값 주입)
    config.fred.base_url = "https://api.stlouisfed.org/fred"
    config.fred.api_key.get_secret_value.return_value = "test_key" # SecretStr 동작 모방
    
    # 2. Policy 설정 (Dictionary 동작 에뮬레이션)
    # 팩토리 함수로 Mock Policy 객체 생성
    def make_policy(provider="FRED", params=None):
        p = MagicMock()
        p.provider = provider
        p.params = params or {}
        p.path = "/series/observations"
        return p

    # 테스트 시나리오별 정책 정의
    policies = {
        "JOB_01": make_policy(params={"series_id": "GDP"}),
        "JOB_NO_PARAM": make_policy(params={}),
        "JOB_KIS": make_policy(provider="KIS")
    }
    
    # 객체를 딕셔너리처럼 조회(.get, []) 할 수 있도록 side_effect 설정
    config.extraction_policy.__getitem__.side_effect = policies.__getitem__
    config.extraction_policy.get.side_effect = policies.get
    
    return config

@pytest.fixture
def fred_extractor(mock_http_client, mock_config):
    """[SUT] System Under Test: 테스트 대상 인스턴스"""
    return FREDExtractor(mock_http_client, mock_config)

# ========================================================================================
# 1. 초기화 테스트 (Initialization & Configuration)
# ========================================================================================

def test_init_01_empty_base_url(mock_http_client, mock_config):
    """[INIT-01] base_url이 비어있으면 초기화 단계에서 즉시 에러 발생 (Fail-Fast)"""
    # Given: 잘못된 설정 (URL 누락)
    mock_config.fred.base_url = ""
    
    # When & Then: 인스턴스 생성 시 예외 발생 검증
    with pytest.raises(ExtractorError, match="base_url.*empty"):
        FREDExtractor(mock_http_client, mock_config)

def test_init_02_missing_api_key(mock_http_client, mock_config):
    """[INIT-02] api_key가 None이면 초기화 실패"""
    # Given: 잘못된 설정 (Key 누락)
    mock_config.fred.api_key = None
    
    # When & Then
    with pytest.raises(ExtractorError, match="api_key.*missing"):
        FREDExtractor(mock_http_client, mock_config)

def test_init_03_valid_init(fred_extractor):
    """[INIT-03] 유효한 설정인 경우 인스턴스가 정상적으로 생성됨"""
    # Then: Config가 정상적으로 주입되었는지 확인
    assert fred_extractor.config.fred.base_url == "https://api.stlouisfed.org/fred"

# ========================================================================================
# 2. 유효성 검증 테스트 (Validation - Logic & MC/DC)
# ========================================================================================

def test_val_00_missing_job_id(fred_extractor):
    """[VAL-00] Request에 job_id가 없는 경우 유효성 검증 실패 (Coverage Hole Patch)"""
    # Given: Job ID가 없는 요청
    request = RequestDTO(job_id="", params={})
    
    # When & Then: 필수 필드 누락 에러 확인
    with pytest.raises(ExtractorError, match="'job_id' is mandatory"):
        fred_extractor._validate_request(request)

def test_val_01_policy_missing(fred_extractor):
    """[VAL-01] Config에 정의되지 않은 job_id 요청 시 실패"""
    # Given: 알 수 없는 Job ID
    request = RequestDTO(job_id="UNKNOWN_JOB", params={})
    
    # When & Then: 정책 미존재 에러 확인
    with pytest.raises(ExtractorError, match="Policy not found"):
        fred_extractor._validate_request(request)

def test_val_02_provider_mismatch(fred_extractor):
    """[VAL-02] 해당 Policy의 Provider가 'FRED'가 아닌 경우 실패"""
    # Given: KIS용 Job을 FRED 수집기에 요청
    request = RequestDTO(job_id="JOB_KIS", params={})
    
    # When & Then: 제공자 불일치 에러 확인
    with pytest.raises(ExtractorError, match="Provider Mismatch"):
        fred_extractor._validate_request(request)

@pytest.mark.asyncio
async def test_val_03_mcdc_series_id_in_policy(fred_extractor, mock_http_client):
    """[VAL-03] [MC/DC] series_id가 Policy에만 존재하는 경우 -> 성공"""
    # Given: Policy에는 "GDP"가 있고, Request에는 없음
    request = RequestDTO(job_id="JOB_01", params={})
    mock_http_client.get.return_value = {"observations": []}
    
    # When: 추출 실행
    await fred_extractor.extract(request)
    
    # Then: 에러 없이 API 호출이 발생했는지 확인
    mock_http_client.get.assert_called_once()

@pytest.mark.asyncio
async def test_val_04_mcdc_series_id_in_request(fred_extractor, mock_http_client):
    """[VAL-04] [MC/DC] series_id가 Request에만 존재하는 경우 -> 성공"""
    # Given: Policy(JOB_NO_PARAM)에는 없고, Request 파라미터로 "CPI" 전달
    request = RequestDTO(job_id="JOB_NO_PARAM", params={"series_id": "CPI"})
    mock_http_client.get.return_value = {"observations": []}
    
    # When: 추출 실행
    await fred_extractor.extract(request)
    
    # Then: 실제 API 호출 시 Request의 "CPI"가 사용되었는지 확인
    call_kwargs = mock_http_client.get.call_args.kwargs
    assert call_kwargs['params']['series_id'] == "CPI"

def test_val_05_mcdc_series_id_missing(fred_extractor):
    """[VAL-05] [MC/DC] series_id가 Policy와 Request 어디에도 없는 경우 -> 실패"""
    # Given: 양쪽 모두 series_id 없음
    request = RequestDTO(job_id="JOB_NO_PARAM", params={})
    
    # When & Then: 필수 파라미터 누락 에러 확인
    with pytest.raises(ExtractorError, match="'series_id' is required"):
        fred_extractor._validate_request(request)

# ========================================================================================
# 3. 실행 및 병합 테스트 (Execution & Data Merging)
# ========================================================================================

@pytest.mark.asyncio
async def test_exec_01_param_merging(fred_extractor, mock_http_client):
    """
    [EXEC-01] 파라미터 병합 로직 검증
    1. Request 파라미터가 Policy 파라미터보다 우선순위가 높은가?
    2. 시스템 필수 파라미터(api_key, file_type)가 강제 주입되는가?
    """
    # Given
    # Policy(JOB_01) params: {series_id: GDP}
    # Request params: {frequency: m}
    request = RequestDTO(job_id="JOB_01", params={"frequency": "m"})
    mock_http_client.get.return_value = {}

    # When
    await fred_extractor.extract(request)

    # Then
    call_params = mock_http_client.get.call_args.kwargs['params']
    assert call_params["series_id"] == "GDP"   # Policy 값 유지
    assert call_params["frequency"] == "m"     # Request 값 병합됨
    assert call_params["file_type"] == "json"  # 시스템 강제 주입 확인
    assert call_params["api_key"] == "test_key" # API Key 주입 확인

@pytest.mark.asyncio
async def test_exec_02_metadata_injection(fred_extractor, mock_http_client):
    """[EXEC-02] extract 메서드 오버라이딩을 통해 ExtractedDTO에 job_id가 주입되는지 확인"""
    # Given
    request = RequestDTO(job_id="JOB_01", params={})
    mock_http_client.get.return_value = {"observations": []}

    # When
    response = await fred_extractor.extract(request)

    # Then
    assert response.meta["job_id"] == "JOB_01"
    assert response.meta["source"] == "FRED"

# ========================================================================================
# 4. 에러 처리 테스트 (Error Handling & Reliability)
# ========================================================================================

@pytest.mark.asyncio
async def test_err_01_logical_error_in_body(fred_extractor, mock_http_client):
    """[ERR-01] HTTP 200 OK이지만 Body에 에러 메시지가 포함된 경우 (Logical Error)"""
    # Given: FRED API 특유의 에러 응답 포맷
    request = RequestDTO(job_id="JOB_01", params={})
    mock_http_client.get.return_value = {
        "error_code": 400,
        "error_message": "Bad Request"
    }

    # When & Then: ExtractorError로 변환되어 던져지는지 확인
    with pytest.raises(ExtractorError, match="FRED API Failed"):
        await fred_extractor.extract(request)

@pytest.mark.asyncio
async def test_err_02_unexpected_exception_wrapping(fred_extractor, mock_http_client):
    """
    [ERR-02] 내부 로직 수행 중 예기치 못한 에러 발생 시 래핑 처리 검증
    데코레이터에 의해 ETLError로 래핑되어 전파되는 현상을 반영하여 수정
    """
    # Given: 예상치 못한 KeyError 발생
    request = RequestDTO(job_id="JOB_01", params={})
    mock_http_client.get.side_effect = KeyError("Unexpected")

    # Then: 데코레이터 체인을 거치면 ETLError가 발생함을 확인
    # 만약 시스템 전체에서 ExtractorError로 통일하고 싶다면 AbstractExtractor를 고쳐야 하지만,
    # 현재 로그/데코레이터 구현상 ETLError가 최상위로 노출됨.
    with pytest.raises(ETLError) as excinfo:
        await fred_extractor.extract(request)
    
    # 래핑된 내부 메시지 확인
    assert "실행 중 예기치 못한 오류 발생" in str(excinfo.value)

@pytest.mark.asyncio
async def test_err_03_retry_decorator_trigger(fred_extractor, mock_http_client):
    """[ERR-03] 네트워크 타임아웃 발생 시 @retry 데코레이터 작동 여부 검증"""
    # Given: 항상 실패하는 API 호출
    request = RequestDTO(job_id="JOB_01", params={})
    mock_http_client.get.side_effect = Exception("Network Timeout")
    
    # When & Then: 최종적으로 ETLError가 발생해야 함
    with pytest.raises(ETLError):
        await fred_extractor.extract(request)
    
    # Assert: 재시도로 인해 호출 횟수가 1회 초과(최대 3회)인지 확인
    assert mock_http_client.get.call_count > 1