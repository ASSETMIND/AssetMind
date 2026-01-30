import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# --------------------------------------------------------------------------
# Import Real Objects (DTO) & Target Class
# --------------------------------------------------------------------------
from src.extractor.providers.upbit_extractor import UPBITExtractor
from src.extractor.domain.dtos import RequestDTO, ResponseDTO
from src.extractor.domain.exceptions import ExtractorError
from src.extractor.domain.interfaces import IHttpClient, IAuthStrategy
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
def mock_auth_strategy():
    """[IAuthStrategy Mock] 인증 토큰 발급 담당"""
    strategy = MagicMock(spec=IAuthStrategy)
    strategy.get_token = AsyncMock()
    return strategy

@pytest.fixture
def mock_config():
    """[AppConfig Mock] 파일 시스템 의존성 제거 및 UPBIT 설정 주입"""
    config = MagicMock()
    
    # UPBIT 기본 설정 (Base URL)
    config.upbit.base_url = "https://api.upbit.com/v1"
    
    # 기본 정책 설정 (Happy Path용)
    valid_policy = MagicMock()
    valid_policy.provider = "UPBIT"
    valid_policy.path = "/candles/minutes/1"
    valid_policy.params = {
        "market": "KRW-BTC",
        "count": 1
    }
    
    config.extraction_policy = {
        "upbit_job": valid_policy
    }
    return config

@pytest.fixture
def extractor(mock_http_client, mock_auth_strategy, mock_config):
    """
    [System Under Test]
    UPBITExtractor의 인스턴스입니다.
    부모 클래스(AbstractExtractor)의 LogManager를 Patch하여 초기화 시 로깅 로직을 무력화합니다.
    """
    with patch(TARGET_LOG_MANAGER) as MockLogManager:
        # Logger Mock 생성 (호출 검증용)
        mock_logger_instance = MagicMock()
        MockLogManager.get_logger.return_value = mock_logger_instance
        
        # 인스턴스 생성
        instance = UPBITExtractor(mock_http_client, mock_auth_strategy, mock_config)
        return instance

# --------------------------------------------------------------------------
# 2. Test Cases
# --------------------------------------------------------------------------

class TestUPBITExtractor:

    # ==========================================
    # Category: Unit (Config Validation)
    # ==========================================

    def test_tc001_config_empty_base_url(self, mock_http_client, mock_auth_strategy, mock_config):
        """[TC-001] Config의 base_url이 비어있으면 초기화 시 ExtractorError가 발생한다."""
        # Given
        mock_config.upbit.base_url = ""

        # When & Then
        with patch(TARGET_LOG_MANAGER):
            with pytest.raises(ExtractorError, match="Critical Config Error.*base_url"):
                UPBITExtractor(mock_http_client, mock_auth_strategy, mock_config)

    # ==========================================
    # Category: Unit (Happy Path)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc002_happy_path_success(self, extractor, mock_http_client, mock_auth_strategy):
        """[TC-002] 정상 Config, 유효 Policy, 인증 토큰 존재 -> OK 상태 및 DTO 반환"""
        # Given
        request = RequestDTO(job_id="upbit_job", params={"to": "2024-01-01 00:00:00"})
        mock_auth_strategy.get_token.return_value = "Bearer TEST_TOKEN"
        
        # UPBIT 정상 응답 (예: 캔들 데이터 리스트)
        mock_response = [{"market": "KRW-BTC", "trade_price": 50000000}]
        mock_http_client.get.return_value = mock_response

        # When
        response = await extractor.extract(request)

        # Then
        assert response.meta["status_code"] == "OK"
        assert response.meta["source"] == "UPBIT"
        assert response.data == mock_response
        mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_tc003_url_header_construction(self, extractor, mock_http_client, mock_auth_strategy):
        """[TC-003] URL, Header, Params가 정확한 순서와 값으로 조립되어 호출되는지 검증"""
        # Given
        request = RequestDTO(job_id="upbit_job")
        mock_auth_strategy.get_token.return_value = "Bearer TEST_TOKEN"
        mock_http_client.get.return_value = []

        # When
        await extractor.extract(request)

        # Then
        expected_url = "https://api.upbit.com/v1/candles/minutes/1"
        expected_headers = {
            "accept": "application/json",
            "authorization": "Bearer TEST_TOKEN"
        }
        
        # Call arguments 확인
        args, kwargs = mock_http_client.get.call_args
        assert args[0] == expected_url
        assert kwargs["headers"] == expected_headers
        assert "market" in kwargs["params"] # Policy param check

    # ==========================================
    # Category: Unit (Logic)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc004_public_api_no_auth_header(self, extractor, mock_http_client, mock_auth_strategy):
        """[TC-004] AuthStrategy가 None을 반환(Public API)하면 Header에 Authorization이 없어야 한다."""
        # Given
        request = RequestDTO(job_id="upbit_job")
        mock_auth_strategy.get_token.return_value = None # No Token Needed
        mock_http_client.get.return_value = []

        # When
        await extractor.extract(request)

        # Then
        _, kwargs = mock_http_client.get.call_args
        headers = kwargs["headers"]
        assert "authorization" not in headers
        assert headers["accept"] == "application/json"

    @pytest.mark.asyncio
    async def test_tc005_param_merge_priority(self, extractor, mock_http_client):
        """[TC-005] Policy Params와 Request Params 충돌 시 Request Params가 우선순위를 가진다."""
        # Given
        # Policy: count=1 (Fixture 설정)
        # Request: count=100
        request = RequestDTO(job_id="upbit_job", params={"count": 100})
        mock_http_client.get.return_value = []

        # When
        await extractor.extract(request)

        # Then
        _, kwargs = mock_http_client.get.call_args
        actual_params = kwargs["params"]
        assert actual_params["count"] == 100 # Request override confirmed

    @pytest.mark.asyncio
    async def test_tc006_warning_log_missing_market(self, extractor, mock_config):
        """[TC-006] Request와 Policy 모두 market 파라미터가 없으면 Warning 로그를 기록한다."""
        # Given
        # Policy에서 market 제거
        mock_config.extraction_policy["upbit_job"].params = {"count": 1}
        request = RequestDTO(job_id="upbit_job", params={}) # No market in request either

        # 로거 Mock 가져오기 (초기화 시 생성된 self.logger)
        mock_logger = extractor.logger

        # When (실행 시 에러는 안 나지만 로그가 찍혀야 함)
        await extractor.extract(request)

        # Then
        mock_logger.warning.assert_called_with("Parameter Warning: 'market' might be missing in policy 'upbit_job'.")

    @pytest.mark.asyncio
    async def test_tc007_list_response_handling(self, extractor, mock_http_client):
        """[TC-007] API가 Dict가 아닌 List를 반환해도 에러 없이 정상 처리된다."""
        # Given
        request = RequestDTO(job_id="upbit_job")
        mock_list_response = [{"candle_acc_trade_price": 100}, {"candle_acc_trade_price": 200}]
        mock_http_client.get.return_value = mock_list_response

        # When
        response = await extractor.extract(request)

        # Then
        assert isinstance(response.data, list)
        assert len(response.data) == 2

    # ==========================================
    # Category: Exception (Request Validation)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc008_invalid_request_missing_job_id(self, extractor):
        """[TC-008] job_id가 누락되면 ExtractorError가 발생한다."""
        # Given
        request = RequestDTO(job_id=None)

        # When & Then
        with pytest.raises(ExtractorError, match="Invalid Request: 'job_id' is mandatory"):
            await extractor.extract(request)

    # ==========================================
    # Category: Exception (Policy Validation)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc009_config_unknown_policy(self, extractor):
        """[TC-009] 요청한 job_id가 Config 정책에 없으면 ExtractorError가 발생한다."""
        # Given
        request = RequestDTO(job_id="unknown_job")

        # When & Then
        with pytest.raises(ExtractorError, match="Policy not found"):
            await extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc010_config_provider_mismatch(self, extractor, mock_config):
        """[TC-010] 해당 Policy의 Provider가 UPBIT가 아니면 ExtractorError가 발생한다."""
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
    async def test_tc011_api_business_failure_standard(self, extractor, mock_http_client):
        """[TC-011] API 응답에 error 객체가 포함되면 ExtractorError로 처리한다."""
        # Given
        request = RequestDTO(job_id="upbit_job")
        # Upbit Error Format
        mock_http_client.get.return_value = {
            "error": {
                "name": "invalid_query_param",
                "message": "query parameter error"
            }
        }

        # When & Then
        with pytest.raises(ExtractorError, match="UPBIT API Failed: query parameter error"):
            await extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc012_api_business_failure_malformed(self, extractor, mock_http_client):
        """[TC-012] error 객체 내부에 상세 정보가 없어도 기본 메시지로 예외 처리한다."""
        # Given
        request = RequestDTO(job_id="upbit_job")
        mock_http_client.get.return_value = {
            "error": {} # Empty error object
        }

        # When & Then
        with pytest.raises(ExtractorError, match="UPBIT API Failed: No message provided"):
            await extractor.extract(request)

    # ==========================================
    # Category: Resource & State
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc013_system_error_network(self, extractor, mock_http_client):
        """[TC-013] HttpClient에서 네트워크 예외 발생 시 System Error로 래핑하여 던진다."""
        # Given
        request = RequestDTO(job_id="upbit_job")
        mock_http_client.get.side_effect = Exception("Connection Refused")

        # When & Then
        with pytest.raises(ExtractorError, match="System Error: Connection Refused"):
            await extractor.extract(request)