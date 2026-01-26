import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.extractor.domain.dtos import RequestDTO, ResponseDTO
from src.extractor.domain.exceptions import ExtractorError
from src.extractor.providers.fred_extractor import FREDExtractor

# -------------------------------------------------------------------------
# Mocks & Fixtures
# -------------------------------------------------------------------------

@pytest.fixture
def mock_http_client():
    """IHttpClient Mock: 실제 네트워크 요청 차단 및 파라미터 검증용"""
    client = MagicMock()
    client.get = AsyncMock()
    return client

@pytest.fixture
def mock_config():
    """AppConfig Mock: FRED 전용 설정 및 정책 주입"""
    config = MagicMock()
    
    # 1. FRED 기본 설정 (Base URL & API Key)
    config.fred.base_url = "https://api.stlouisfed.org"
    # SecretStr 동작 모방: get_secret_value() 호출 시 평문 반환
    config.fred.api_key.get_secret_value.return_value = "TEST_FRED_KEY"
    
    # 2. 정책(Policy) 설정
    # Case A: Normal Policy (series_id included)
    normal_policy = MagicMock()
    normal_policy.provider = "FRED"
    normal_policy.path = "/fred/series/observations"
    normal_policy.params = {"series_id": "GDP", "frequency": "q"} # Default Params
    
    # Case B: Policy without series_id (to test request injection)
    flexible_policy = MagicMock()
    flexible_policy.provider = "FRED"
    flexible_policy.path = "/fred/series/observations"
    flexible_policy.params = {"frequency": "m"} # series_id missing here
    
    # Case C: Provider Mismatch
    kis_policy = MagicMock()
    kis_policy.provider = "KIS" # Not FRED
    
    config.extraction_policy = {
        "valid_job": normal_policy,
        "flex_job": flexible_policy,
        "kis_job": kis_policy
    }
    return config

@pytest.fixture
def extractor(mock_http_client, mock_config):
    """FREDExtractor 인스턴스 생성 (LogManager 의존성 제거)"""
    
    # Critical Fix: KIS 테스트와 동일하게 부모 클래스의 LogManager 호출을 무력화
    with patch("src.extractor.providers.abstract_extractor.LogManager") as MockLogManager:
        MockLogManager.get_logger.return_value = MagicMock()
        
        # FRED는 AuthStrategy가 필요 없으므로 http_client와 config만 주입
        extractor_instance = FREDExtractor(mock_http_client, mock_config)
        return extractor_instance

# -------------------------------------------------------------------------
# Test Cases (TC-001 ~ TC-013)
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc_001_happy_path_success(extractor, mock_http_client):
    """[TC-001] 정상 Config, Policy, 응답(No Error Msg) -> 성공"""
    # Given
    request = RequestDTO(job_id="valid_job")
    mock_data = {"realtime_start": "2024-01-01", "observations": [{"value": "100"}]}
    mock_http_client.get.return_value = mock_data

    # When
    response = await extractor.extract(request)

    # Then
    assert response.data == mock_data
    assert response.meta["source"] == "FRED"
    assert response.meta["status_code"] == "200" # FRED는 명시적 코드가 없으므로 200 가정
    assert response.meta["job_id"] == "valid_job"
    mock_http_client.get.assert_called_once()

@pytest.mark.asyncio
async def test_tc_002_logic_param_merge_distinct(extractor, mock_http_client):
    """[TC-002] Policy Param과 Request Param 병합 확인"""
    # Given
    # Policy: {'series_id': 'GDP', 'frequency': 'q'}
    request = RequestDTO(job_id="valid_job", params={"observation_start": "2020-01-01"})
    mock_http_client.get.return_value = {}

    # When
    await extractor.extract(request)

    # Then
    call_params = mock_http_client.get.call_args[1]["params"]
    assert call_params["series_id"] == "GDP"
    assert call_params["frequency"] == "q"
    assert call_params["observation_start"] == "2020-01-01"

@pytest.mark.asyncio
async def test_tc_003_logic_forced_json_injection(extractor, mock_http_client):
    """[TC-003] Request가 xml을 요청해도 시스템이 json을 강제해야 함"""
    # Given
    request = RequestDTO(job_id="valid_job", params={"file_type": "xml"})
    mock_http_client.get.return_value = {}

    # When
    await extractor.extract(request)

    # Then
    call_params = mock_http_client.get.call_args[1]["params"]
    assert call_params["file_type"] == "json" # Override Check

@pytest.mark.asyncio
async def test_tc_004_logic_api_key_injection(extractor, mock_http_client):
    """[TC-004] Config의 SecretKey가 평문으로 Query Param에 주입되어야 함"""
    # Given
    request = RequestDTO(job_id="valid_job")
    mock_http_client.get.return_value = {}

    # When
    await extractor.extract(request)

    # Then
    call_params = mock_http_client.get.call_args[1]["params"]
    assert call_params["api_key"] == "TEST_FRED_KEY"

@pytest.mark.asyncio
async def test_tc_005_boundary_series_id_in_request(extractor, mock_http_client):
    """[TC-005] Policy에 series_id가 없어도 Request에 있으면 성공"""
    # Given
    # 'flex_job' policy has no series_id
    request = RequestDTO(job_id="flex_job", params={"series_id": "CPI"})
    mock_http_client.get.return_value = {}

    # When
    await extractor.extract(request)

    # Then
    call_params = mock_http_client.get.call_args[1]["params"]
    assert call_params["series_id"] == "CPI"

@pytest.mark.asyncio
async def test_tc_006_boundary_empty_request_params(extractor, mock_http_client):
    """[TC-006] Request Params가 비어있으면 Policy 기본값 사용"""
    # Given
    request = RequestDTO(job_id="valid_job", params={})
    mock_http_client.get.return_value = {}

    # When
    await extractor.extract(request)

    # Then
    call_params = mock_http_client.get.call_args[1]["params"]
    assert call_params["series_id"] == "GDP"

def test_tc_007_config_empty_base_url(mock_http_client, mock_config):
    """[TC-007] Config의 base_url이 비어있으면 초기화 시 에러"""
    # Given
    mock_config.fred.base_url = ""

    # When & Then
    with patch("src.extractor.providers.abstract_extractor.LogManager") as MockLogManager:
        MockLogManager.get_logger.return_value = MagicMock()
        with pytest.raises(ExtractorError, match="Critical Config Error"):
            FREDExtractor(mock_http_client, mock_config)

@pytest.mark.asyncio
async def test_tc_008_error_missing_job_id(extractor):
    """[TC-008] job_id 누락 시 ExtractorError"""
    # Given
    request = RequestDTO(job_id=None)

    # When & Then
    with pytest.raises(ExtractorError, match="Invalid Request: 'job_id' is mandatory"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_tc_009_error_unknown_policy(extractor):
    """[TC-009] Config에 없는 job_id 요청 시 ExtractorError"""
    # Given
    request = RequestDTO(job_id="unknown_job")

    # When & Then
    with pytest.raises(ExtractorError, match="Policy not found"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_tc_010_error_provider_mismatch(extractor):
    """[TC-010] Policy Provider가 FRED가 아님 -> ExtractorError"""
    # Given
    request = RequestDTO(job_id="kis_job") # Provider is KIS

    # When & Then
    with pytest.raises(ExtractorError, match="Provider Mismatch"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_tc_011_error_missing_series_id(extractor):
    """[TC-011] Policy와 Request 모두 series_id 누락 -> ExtractorError"""
    # Given
    # 'flex_job' has no series_id in policy
    request = RequestDTO(job_id="flex_job", params={}) 

    # When & Then
    with pytest.raises(ExtractorError, match="Missing Parameter: 'series_id' is required"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_tc_012_error_fred_business_failure(extractor, mock_http_client):
    """[TC-012] HTTP 200이지만 Body에 error_message 포함 -> ExtractorError"""
    # Given
    request = RequestDTO(job_id="valid_job")
    mock_http_client.get.return_value = {
        "error_code": 400,
        "error_message": "Bad Request. The value for variable series_id cannot be found."
    }

    # When & Then
    with pytest.raises(ExtractorError, match="FRED API Failed: Bad Request"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_tc_013_error_system_failure(extractor, mock_http_client):
    """[TC-013] HttpClient 네트워크 예외 발생 -> System Error로 래핑"""
    # Given
    request = RequestDTO(job_id="valid_job")
    mock_http_client.get.side_effect = Exception("Connection Timeout")

    # When & Then
    with pytest.raises(ExtractorError, match="System Error: Connection Timeout"):
        await extractor.extract(request)