import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict

# [Target Modules]
from src.extractor.providers.ecos_extractor import ECOSExtractor
from src.extractor.domain.dtos import RequestDTO, ResponseDTO
from src.extractor.domain.exceptions import ExtractorError
from src.extractor.domain.interfaces import IHttpClient
from src.common.config import AppConfig

# ========================================================================================
# [Mocks & Stubs] 외부 의존성 격리를 위한 모의 객체
# ========================================================================================

class MockSecretStr:
    """Pydantic SecretStr 동작 모방"""
    def __init__(self, value: str):
        self._value = value
    
    def get_secret_value(self) -> str:
        return self._value

class MockJobPolicy:
    """Config 내 JobPolicy 객체 모방"""
    def __init__(self, provider: str = "ECOS", path: str = "StatisticSearch", params: Dict = None):
        self.provider = provider
        self.path = path
        self.params = params or {
            "stat_code": "100Y",
            "cycle": "D",
            "item_code1": "0001"
        }

# ========================================================================================
# [Fixtures] 테스트 환경 설정
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger():
    """LogManager 초기화 시 전역 Config 참조 방지 및 데코레이터 Pass-through 처리"""
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger, \
         patch("src.extractor.providers.ecos_extractor.log_decorator") as mock_log_dec, \
         patch("src.extractor.providers.ecos_extractor.retry") as mock_retry_dec, \
         patch("src.extractor.providers.ecos_extractor.rate_limit") as mock_rate_dec:
        
        mock_get_logger.return_value = MagicMock()
        passthrough = lambda *args, **kwargs: lambda func: func
        mock_log_dec.side_effect = passthrough
        mock_retry_dec.side_effect = passthrough
        mock_rate_dec.side_effect = passthrough
        yield

@pytest.fixture
def mock_http_client():
    client = MagicMock(spec=IHttpClient)
    client.get = AsyncMock()
    return client

@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.ecos = MagicMock()
    config.ecos.base_url = "https://ecos.bok.or.kr/api"
    config.ecos.api_key = MockSecretStr("test_api_key")
    config.extraction_policy = {
        "job_valid": MockJobPolicy(),
        "job_kis": MockJobPolicy(provider="KIS"),
    }
    return config

@pytest.fixture
def extractor(mock_http_client, mock_config):
    return ECOSExtractor(mock_http_client, mock_config)

# ========================================================================================
# [INIT] 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_base_url_empty(mock_http_client, mock_config):
    """[INIT-01] ecos.base_url이 비어있는 설정 객체 -> ExtractorError"""
    mock_config.ecos.base_url = ""
    with pytest.raises(ExtractorError, match="'ecos.base_url' is empty"):
        ECOSExtractor(mock_http_client, mock_config)

def test_init_02_api_key_missing(mock_http_client, mock_config):
    """[INIT-02] ecos.api_key가 없는 설정 객체 -> ExtractorError"""
    mock_config.ecos.api_key = None
    with pytest.raises(ExtractorError, match="'ecos.api_key' is missing"):
        ECOSExtractor(mock_http_client, mock_config)

def test_init_03_valid_init(extractor):
    """[INIT-03] 유효한 설정(URL, Key 포함) 객체 -> 인스턴스 정상 생성"""
    assert isinstance(extractor, ECOSExtractor)

# ========================================================================================
# [REQ] 요청 검증 테스트 (Validation - MC/DC)
# ========================================================================================

def test_req_01_missing_job_id(extractor):
    """[REQ-01] job_id가 없는 요청 객체 -> ExtractorError"""
    request = RequestDTO(job_id=None) # type: ignore
    with pytest.raises(ExtractorError, match="'job_id' is mandatory"):
        extractor._validate_request(request)

def test_req_02_policy_not_found(extractor):
    """[REQ-02] 설정 파일에 정의되지 않은 job_id 요청 -> ExtractorError"""
    request = RequestDTO(job_id="job_unknown")
    with pytest.raises(ExtractorError, match="Policy not found"):
        extractor._validate_request(request)

def test_req_03_provider_mismatch(extractor):
    """[REQ-03] Provider가 'KIS'로 설정된 정책 요청 -> ExtractorError"""
    request = RequestDTO(job_id="job_kis")
    with pytest.raises(ExtractorError, match="Provider Mismatch"):
        extractor._validate_request(request)

def test_req_04_missing_date_params(extractor):
    """[REQ-04] start_date 파라미터가 누락됨 -> ExtractorError"""
    request = RequestDTO(job_id="job_valid", params={"end_date": "20230101"})
    with pytest.raises(ExtractorError, match="'start_date' and 'end_date' are mandatory"):
        extractor._validate_request(request)

# ========================================================================================
# [FLOW] 정상 흐름 테스트 (Functional)
# ========================================================================================

@pytest.mark.asyncio
async def test_flow_01_happy_path(extractor, mock_http_client):
    """[FLOW-01] 정상 정책, 서비스 내 INFO-000 응답 -> ResponseDTO 반환 및 URL 검증"""
    # Given
    request = RequestDTO(job_id="job_valid", params={"start_date": "20230101", "end_date": "20230131"})
    mock_response = {
        "StatisticSearch": {
            "list_total_count": 1,
            "row": [{"TIME": "2023", "DATA_VALUE": "100"}],
            "RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"}
        }
    }
    mock_http_client.get.return_value = mock_response
    
    # When
    response = await extractor.extract(request)
    
    # Then
    assert isinstance(response, ResponseDTO)
    assert response.data == mock_response
    assert response.meta["job_id"] == "job_valid"
    
    # ECOS Path Variable URL Construction Check
    expected_url = (
        "https://ecos.bok.or.kr/api/StatisticSearch/"
        "test_api_key/json/kr/1/100000/"
        "100Y/D/20230101/20230131/0001"
    )
    mock_http_client.get.assert_called_once_with(expected_url)

# ========================================================================================
# [DATA] 데이터 안정성 및 응답 구조 테스트 (Data Parsing)
# ========================================================================================

@pytest.mark.asyncio
async def test_data_01_root_level_failure(extractor, mock_http_client):
    """[DATA-01] Root 레벨에 RESULT.CODE='INFO-200' -> ExtractorError"""
    mock_response = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "Limit Exceeded"}}
    mock_http_client.get.return_value = mock_response
    request = RequestDTO(job_id="job_valid", params={"start_date": "20230101", "end_date": "20230102"})
    
    with pytest.raises(ExtractorError, match="ECOS API Failed"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_data_02_service_key_missing(extractor, mock_http_client):
    """[DATA-02] Root에 정책 경로(StatisticSearch) 없음 -> ExtractorError"""
    mock_response = {"WrongServiceKey": {"row": []}}
    mock_http_client.get.return_value = mock_response
    request = RequestDTO(job_id="job_valid", params={"start_date": "20230101", "end_date": "20230102"})
    
    with pytest.raises(ExtractorError, match="Invalid ECOS Response"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_data_03_inner_level_failure(extractor, mock_http_client):
    """[DATA-03] 서비스 내 RESULT.CODE='INFO-200' -> ExtractorError"""
    mock_response = {"StatisticSearch": {"RESULT": {"CODE": "INFO-200", "MESSAGE": "No Data"}}}
    mock_http_client.get.return_value = mock_response
    request = RequestDTO(job_id="job_valid", params={"start_date": "20230101", "end_date": "20230102"})
    
    with pytest.raises(ExtractorError, match="ECOS API Failed"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_data_04_root_result_success_ignored(extractor, mock_http_client):
    """[DATA-04] Root RESULT 존재하나 성공(INFO-000) -> 정상 반환 (방어 로직)"""
    # Given: Root에 성공 코드가 있고, 실제 데이터도 존재하는 복합 응답
    request = RequestDTO(job_id="job_valid", params={"start_date": "20230101", "end_date": "20230131"})
    mock_response = {
        "RESULT": {"CODE": "INFO-000", "MESSAGE": "Root Success"},
        "StatisticSearch": {
            "list_total_count": 1,
            "row": [{"TIME": "2023", "DATA_VALUE": "100"}],
            "RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"}
        }
    }
    mock_http_client.get.return_value = mock_response

    # When
    response = await extractor.extract(request)

    # Then
    assert response.data == mock_response
    assert response.meta["status"] == "success"

@pytest.mark.asyncio
async def test_data_05_inner_result_missing(extractor, mock_http_client):
    """[DATA-05] 서비스 내 RESULT 키 자체가 누락됨 -> 정상 반환 (암시적 성공)"""
    # Given: 필수 메타데이터인 RESULT가 누락되었으나 데이터는 있는 상황
    request = RequestDTO(job_id="job_valid", params={"start_date": "20230101", "end_date": "20230131"})
    mock_response = {
        "StatisticSearch": {
            "list_total_count": 1,
            "row": [{"TIME": "2023", "DATA_VALUE": "100"}]
            # RESULT key missing
        }
    }
    mock_http_client.get.return_value = mock_response

    # When
    response = await extractor.extract(request)

    # Then
    assert response.data == mock_response

# ========================================================================================
# [ERR] 예외 처리 테스트 (Exceptions)
# ========================================================================================

@pytest.mark.asyncio
async def test_err_01_system_error_wrapping(extractor, mock_http_client):
    """[ERR-01] HTTP 클라이언트가 ValueError 발생 -> ExtractorError로 래핑"""
    mock_http_client.get.side_effect = ValueError("Network Timeout")
    request = RequestDTO(job_id="job_valid", params={"start_date": "20230101", "end_date": "20230102"})
    
    with pytest.raises(ExtractorError, match="System Error"):
        await extractor.extract(request)

@pytest.mark.asyncio
async def test_err_02_reraise_extractor_error(extractor, mock_http_client):
    """[ERR-02] 내부 로직에서 ExtractorError 발생 -> 그대로 전파"""
    mock_http_client.get.side_effect = ExtractorError("Parsing Failed")
    request = RequestDTO(job_id="job_valid", params={"start_date": "20230101", "end_date": "20230102"})
    
    with pytest.raises(ExtractorError, match="Parsing Failed"):
        await extractor.extract(request)