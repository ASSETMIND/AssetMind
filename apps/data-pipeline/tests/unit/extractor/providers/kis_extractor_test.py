import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.extractor.domain.dtos import RequestDTO, ResponseDTO
from src.extractor.domain.exceptions import ExtractorError
from src.extractor.providers.kis_extractor import KISExtractor

# -------------------------------------------------------------------------
# Mocks & Fixtures
# -------------------------------------------------------------------------

@pytest.fixture
def mock_http_client():
    """IHttpClient Mock: 실제 네트워크 요청 차단"""
    client = MagicMock()
    client.get = AsyncMock()
    return client

@pytest.fixture
def mock_auth_strategy():
    """IAuthStrategy Mock: 토큰 발급 로직 격리"""
    strategy = MagicMock()
    strategy.get_token = AsyncMock(return_value="Bearer TEST_TOKEN")
    return strategy

@pytest.fixture
def mock_config():
    """AppConfig Mock: Pydantic 모델 대신 MagicMock 사용"""
    config = MagicMock()
    
    # KIS 기본 설정
    config.kis.base_url = "https://api.kis.com"
    config.kis.app_key.get_secret_value.return_value = "TEST_APP_KEY"
    config.kis.app_secret.get_secret_value.return_value = "TEST_APP_SECRET"
    
    # 기본 정책 설정 (Happy Path용)
    valid_policy = MagicMock()
    valid_policy.provider = "KIS"
    valid_policy.path = "/uapi/test"
    valid_policy.tr_id = "TR1234"
    valid_policy.params = {"count": 10} # Default Params
    
    config.extraction_policy = {
        "valid_job": valid_policy
    }
    return config

@pytest.fixture
def extractor(mock_http_client, mock_auth_strategy, mock_config):
    """KISExtractor 인스턴스 생성 (LogManager 의존성 제거 포함)"""
    
    # Critical Fix: 
    # AbstractExtractor가 초기화될 때 LogManager를 호출하면서 Global Config를 체크하는 것을 방지합니다.
    # src.extractor.providers.abstract_extractor 모듈 내의 LogManager를 Mocking 합니다.
    with patch("src.extractor.providers.abstract_extractor.LogManager") as MockLogManager:
        # get_logger 호출 시 빈 MagicMock을 반환하여 로깅 로직을 무력화
        MockLogManager.get_logger.return_value = MagicMock()
        
        # 의존성이 제거된 상태에서 인스턴스 생성
        extractor_instance = KISExtractor(mock_http_client, mock_auth_strategy, mock_config)
        return extractor_instance

# -------------------------------------------------------------------------
# Test Cases (TC-001 ~ TC-013)
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc_001_happy_path_success(extractor, mock_http_client):
    """[TC-001] 정상 Config, 유효 토큰, 정상 API 응답(rt_cd='0') -> 성공"""
    # Given
    request = RequestDTO(job_id="valid_job")
    mock_data = {"rt_cd": "0", "msg1": "Success", "output": [1, 2, 3]}
    mock_http_client.get.return_value = mock_data

    # When
    response = await extractor.extract(request)

    # Then
    assert response.data == mock_data
    assert response.meta["status_code"] == "0"
    assert response.meta["source"] == "KIS"
    mock_http_client.get.assert_called_once()

@pytest.mark.asyncio
async def test_tc_002_logic_param_merge_distinct(extractor, mock_http_client, mock_config):
    """[TC-002] Policy Param과 Request Param 키가 다를 때 -> 병합됨"""
    # Given
    request = RequestDTO(job_id="valid_job", params={"date": "20240101"})
    mock_http_client.get.return_value = {"rt_cd": "0"}

    # When
    await extractor.extract(request)

    # Then
    # call_args[1]은 kwargs (params=...)
    call_params = mock_http_client.get.call_args[1]["params"]
    assert call_params == {"count": 10, "date": "20240101"}

@pytest.mark.asyncio
async def test_tc_003_edge_param_override(extractor, mock_http_client):
    """[TC-003] Policy Param과 Request Param 키가 같을 때 -> Request 우선"""
    # Given
    request = RequestDTO(job_id="valid_job", params={"count": 50})
    mock_http_client.get.return_value = {"rt_cd": "0"}

    # When
    await extractor.extract(request)

    # Then
    call_params = mock_http_client.get.call_args[1]["params"]
    assert call_params == {"count": 50}

@pytest.mark.asyncio
async def test_tc_004_edge_empty_request_params(extractor, mock_http_client):
    """[TC-004] Request Params가 비어있음 -> Policy Param 사용"""
    # Given
    request = RequestDTO(job_id="valid_job", params={})
    mock_http_client.get.return_value = {"rt_cd": "0"}

    # When
    await extractor.extract(request)

    # Then
    call_params = mock_http_client.get.call_args[1]["params"]
    assert call_params == {"count": 10}

@pytest.mark.asyncio
async def test_tc_005_valid_missing_job_id(extractor):
    """[TC-005] job_id 누락 -> ExtractorError"""
    # Given
    request = RequestDTO(job_id=None)

    # When & Then
    with pytest.raises(ExtractorError, match="Invalid Request: 'job_id' is mandatory"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_tc_006_edge_missing_rt_cd(extractor, mock_http_client):
    """[TC-006] 응답 JSON에 rt_cd 필드 없음 -> ExtractorError"""
    # Given
    request = RequestDTO(job_id="valid_job")
    mock_http_client.get.return_value = {"msg1": "ok", "output": []}

    # When & Then
    with pytest.raises(ExtractorError, match="KIS API Failed"):
        await extractor.extract(request)

def test_tc_007_config_empty_base_url(mock_http_client, mock_auth_strategy, mock_config):
    """[TC-007] Config의 base_url이 비어있음 -> 초기화 시 ExtractorError"""
    # Given
    mock_config.kis.base_url = "" # Empty URL

    # When & Then
    # 여기서도 __init__ 호출 시 LogManager가 터지지 않도록 Patch 필요
    with patch("src.extractor.providers.abstract_extractor.LogManager") as MockLogManager:
        MockLogManager.get_logger.return_value = MagicMock()
        
        with pytest.raises(ExtractorError, match="Critical Config Error"):
            KISExtractor(mock_http_client, mock_auth_strategy, mock_config)

@pytest.mark.asyncio
async def test_tc_008_config_unknown_policy(extractor):
    """[TC-008] 요청한 job_id가 Config에 없음 -> ExtractorError"""
    # Given
    request = RequestDTO(job_id="unknown_job")

    # When & Then
    with pytest.raises(ExtractorError, match="Policy not found"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_tc_009_config_provider_mismatch(extractor, mock_config):
    """[TC-009] Policy Provider가 KIS가 아님 -> ExtractorError"""
    # Given
    fred_policy = MagicMock()
    fred_policy.provider = "FRED"
    mock_config.extraction_policy["fred_job"] = fred_policy
    
    request = RequestDTO(job_id="fred_job")

    # When & Then
    with pytest.raises(ExtractorError, match="Provider Mismatch"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_tc_010_config_missing_tr_id(extractor, mock_config):
    """[TC-010] Policy에 tr_id 누락 -> ExtractorError"""
    # Given
    broken_policy = MagicMock()
    broken_policy.provider = "KIS"
    broken_policy.tr_id = None 
    mock_config.extraction_policy["no_tr_id"] = broken_policy

    request = RequestDTO(job_id="no_tr_id")

    # When & Then
    with pytest.raises(ExtractorError, match="'tr_id' is missing"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_tc_011_biz_api_failure(extractor, mock_http_client):
    """[TC-011] API 응답이 rt_cd='1' (실패) -> ExtractorError"""
    # Given
    request = RequestDTO(job_id="valid_job")
    mock_http_client.get.return_value = {"rt_cd": "1", "msg1": "Limit Exceeded"}

    # When & Then
    with pytest.raises(ExtractorError) as exc_info:
        await extractor.extract(request)
    
    assert "Limit Exceeded" in str(exc_info.value)
    assert "Code: 1" in str(exc_info.value)

@pytest.mark.asyncio
async def test_tc_012_error_auth_failure(extractor, mock_auth_strategy):
    """[TC-012] AuthStrategy 예외 발생 -> System Error로 래핑"""
    # Given
    request = RequestDTO(job_id="valid_job")
    mock_auth_strategy.get_token.side_effect = Exception("Auth Server Down")

    # When & Then
    with pytest.raises(ExtractorError, match="System Error: Auth Server Down"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_tc_013_error_network_failure(extractor, mock_http_client):
    """[TC-013] HttpClient 네트워크 예외 발생 -> System Error로 래핑"""
    # Given
    request = RequestDTO(job_id="valid_job")
    mock_http_client.get.side_effect = Exception("Connection Timeout")

    # When & Then
    with pytest.raises(ExtractorError, match="System Error: Connection Timeout"):
        await extractor.extract(request)