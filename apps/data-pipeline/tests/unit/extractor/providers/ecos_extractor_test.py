import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# --------------------------------------------------------------------------
# Import Real Objects (DTO) & Target Class
# --------------------------------------------------------------------------
from src.extractor.providers.ecos_extractor import ECOSExtractor
from src.extractor.domain.dtos import RequestDTO, ResponseDTO
from src.extractor.domain.exceptions import ExtractorError
from src.extractor.domain.interfaces import IHttpClient
from src.common.config import AppConfig 

# --------------------------------------------------------------------------
# 0. Constants & Configuration
# --------------------------------------------------------------------------

# 로그 매니저 경로 (AbstractExtractor 초기화 시 파일 I/O 유발 방지)
TARGET_LOG_MANAGER = "src.extractor.providers.abstract_extractor.LogManager"

# --------------------------------------------------------------------------
# 1. Fixtures (Test Environment Setup)
# --------------------------------------------------------------------------

@pytest.fixture
def mock_http_client():
    """[IHttpClient Mock] 외부 네트워크 통신 담당"""
    client = MagicMock(spec=IHttpClient)
    client.get = AsyncMock()
    return client

@pytest.fixture
def mock_config():
    """[AppConfig Mock] 파일 시스템 의존성 제거 및 ECOS 설정 주입"""
    # Critical Fix: spec=AppConfig 제거. 
    # spec을 사용하면 동적으로 속성(ecos)을 추가할 때 AttributeError가 발생할 수 있습니다.
    config = MagicMock() 
    
    # ECOS 기본 설정 (Base URL, API Key)
    # MagicMock은 속성에 처음 접근할 때 자동으로 자식 Mock을 생성합니다.
    config.ecos.base_url = "http://api.ecos.bok.or.kr"
    config.ecos.api_key.get_secret_value.return_value = "TEST_API_KEY"
    
    # 기본 정책 설정 (Happy Path용)
    valid_policy = MagicMock()
    valid_policy.provider = "ECOS"
    valid_policy.path = "/StatisticSearch"
    valid_policy.params = {
        "stat_code": "100Y",
        "cycle": "D",
        "item_code1": "0001"
    }
    
    config.extraction_policy = {
        "ecos_job": valid_policy
    }
    return config

@pytest.fixture
def extractor(mock_http_client, mock_config):
    """
    [System Under Test]
    ECOSExtractor의 인스턴스입니다.
    부모 클래스(AbstractExtractor)의 LogManager를 Patch하여 초기화 시 로깅 로직을 무력화합니다.
    """
    with patch(TARGET_LOG_MANAGER) as MockLogManager:
        # Logger Mock 생성 (호출 검증용)
        mock_logger_instance = MagicMock()
        MockLogManager.get_logger.return_value = mock_logger_instance
        
        # 인스턴스 생성
        instance = ECOSExtractor(mock_http_client, mock_config)
        return instance

# --------------------------------------------------------------------------
# 2. Test Cases
# --------------------------------------------------------------------------

class TestECOSExtractor:
    
    # ==========================================
    # Category: Unit (Happy Path & Logic)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc001_happy_path_success(self, extractor, mock_http_client):
        """[TC-001] 정상 Config, 유효 Policy, 정상 응답 -> INFO-000 성공 처리 및 DTO 반환"""
        # Given
        request = RequestDTO(
            job_id="ecos_job", 
            params={"start_date": "20240101", "end_date": "20240102"}
        )
        
        # ECOS 정상 응답 구조 (Service Name -> RESULT -> CODE)
        mock_response = {
            "StatisticSearch": {
                "list_total_count": 5,
                "row": [{"TIME": "20240101", "DATA_VALUE": "100"}],
                "RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."}
            }
        }
        mock_http_client.get.return_value = mock_response

        # When
        response = await extractor.extract(request)

        # Then
        assert response.meta["status"] == "success"
        assert response.meta["source"] == "ECOS"
        assert response.data == mock_response
        mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_tc002_url_construction_strict_path(self, extractor, mock_http_client):
        """[TC-002] ECOS URL Path 조립 로직 검증 (순서 엄격 준수: Key/Type/Lang/Start/End/...)"""
        # Given
        request = RequestDTO(
            job_id="ecos_job", 
            params={"start_date": "20240101", "end_date": "20240131"}
        )
        # 응답은 성공으로 가정 (URL 확인이 주 목적)
        mock_http_client.get.return_value = {"StatisticSearch": {"RESULT": {"CODE": "INFO-000"}}}

        # When
        await extractor.extract(request)

        # Then
        # Expected Format: {Base}/{Path}/{Key}/json/kr/1/100000/{Stat}/{Cycle}/{Start}/{End}/{Item}
        expected_url = (
            "http://api.ecos.bok.or.kr/StatisticSearch/"
            "TEST_API_KEY/json/kr/1/100000/"
            "100Y/D/20240101/20240131/0001"
        )
        
        actual_url = mock_http_client.get.call_args[0][0] # get 메서드의 첫 번째 인자(url) 확인
        assert actual_url == expected_url

    # ==========================================
    # Category: Unit (Config Validation)
    # ==========================================

    def test_tc003_config_empty_base_url(self, mock_http_client, mock_config):
        """[TC-003] Config의 base_url이 비어있으면 초기화 시 ExtractorError가 발생한다."""
        # Given
        mock_config.ecos.base_url = ""

        # When & Then
        with patch(TARGET_LOG_MANAGER):
            with pytest.raises(ExtractorError, match="Critical Config Error.*base_url"):
                ECOSExtractor(mock_http_client, mock_config)

    def test_tc004_config_missing_api_key(self, mock_http_client, mock_config):
        """[TC-004] Config의 api_key가 누락되면 초기화 시 ExtractorError가 발생한다."""
        # Given
        mock_config.ecos.api_key = None

        # When & Then
        with patch(TARGET_LOG_MANAGER):
            with pytest.raises(ExtractorError, match="Critical Config Error.*api_key"):
                ECOSExtractor(mock_http_client, mock_config)

    # ==========================================
    # Category: Exception (Request Validation)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc005_invalid_request_missing_job_id(self, extractor):
        """[TC-005] job_id가 누락되면 ExtractorError가 발생한다."""
        # Given
        request = RequestDTO(job_id=None)

        # When & Then
        with pytest.raises(ExtractorError, match="Invalid Request: 'job_id' is mandatory"):
            await extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc006_invalid_request_missing_start_date(self, extractor):
        """[TC-006] start_date 파라미터가 누락되면 ExtractorError가 발생한다 (ECOS 필수)."""
        # Given
        request = RequestDTO(job_id="ecos_job", params={"end_date": "20240101"})

        # When & Then
        with pytest.raises(ExtractorError, match="mandatory for ECOS"):
            await extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc007_invalid_request_missing_end_date(self, extractor):
        """[TC-007] end_date 파라미터가 누락되면 ExtractorError가 발생한다 (ECOS 필수)."""
        # Given
        request = RequestDTO(job_id="ecos_job", params={"start_date": "20240101"})

        # When & Then
        with pytest.raises(ExtractorError, match="mandatory for ECOS"):
            await extractor.extract(request)

    # ==========================================
    # Category: Exception (Policy Validation)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc008_config_unknown_policy(self, extractor):
        """[TC-008] 요청한 job_id가 Config 정책에 없으면 ExtractorError가 발생한다."""
        # Given
        request = RequestDTO(job_id="unknown_job", params={"start_date": "2024", "end_date": "2024"})

        # When & Then
        with pytest.raises(ExtractorError, match="Policy not found"):
            await extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc009_config_provider_mismatch(self, extractor, mock_config):
        """[TC-009] 해당 Policy의 Provider가 ECOS가 아니면 ExtractorError가 발생한다."""
        # Given
        kis_policy = MagicMock()
        kis_policy.provider = "KIS"
        mock_config.extraction_policy["kis_job"] = kis_policy
        
        request = RequestDTO(job_id="kis_job")

        # When & Then
        with pytest.raises(ExtractorError, match="Provider Mismatch"):
            await extractor.extract(request)

    # ==========================================
    # Category: Exception (Response Handling)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc010_api_root_failure(self, extractor, mock_http_client):
        """[TC-010] API 응답 Root 레벨 에러(인증 실패 등) 발생 시 ExtractorError로 처리한다."""
        # Given
        request = RequestDTO(job_id="ecos_job", params={"start_date": "2024", "end_date": "2024"})
        # 인증 에러 예시: 서비스 키가 없을 때 Root에 바로 RESULT가 옴
        mock_http_client.get.return_value = {
            "RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}
        }

        # When & Then
        with pytest.raises(ExtractorError, match="ECOS API Failed"):
            await extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc011_api_business_failure(self, extractor, mock_http_client):
        """[TC-011] API 응답 서비스 레벨 에러(데이터 없음 등) 발생 시 ExtractorError로 처리한다."""
        # Given
        request = RequestDTO(job_id="ecos_job", params={"start_date": "2024", "end_date": "2024"})
        # 서비스 키 내부에 에러가 있는 경우
        mock_http_client.get.return_value = {
            "StatisticSearch": {
                "RESULT": {"CODE": "INFO-200", "MESSAGE": "No Data"}
            }
        }

        # When & Then
        with pytest.raises(ExtractorError, match="ECOS API Failed"):
            await extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc012_invalid_response_structure(self, extractor, mock_http_client):
        """[TC-012] API 응답에 예상된 서비스명(Key)이 없으면 구조 불일치로 ExtractorError가 발생한다."""
        # Given
        request = RequestDTO(job_id="ecos_job", params={"start_date": "2024", "end_date": "2024"})
        # Policy path는 'StatisticSearch'인데 엉뚱한 키가 온 경우
        mock_http_client.get.return_value = {
            "WrongServiceKey": {"row": []}
        }

        # When & Then
        with pytest.raises(ExtractorError, match="Invalid ECOS Response"):
            await extractor.extract(request)

    # ==========================================
    # Category: Resource & State
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc013_system_error_network(self, extractor, mock_http_client):
        """[TC-013] HttpClient에서 네트워크 예외 발생 시 System Error로 래핑하여 던진다."""
        # Given
        request = RequestDTO(job_id="ecos_job", params={"start_date": "2024", "end_date": "2024"})
        mock_http_client.get.side_effect = Exception("Connection Refused")

        # When & Then
        with pytest.raises(ExtractorError, match="System Error: Connection Refused"):
            await extractor.extract(request)