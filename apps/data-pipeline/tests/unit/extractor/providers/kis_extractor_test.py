import pytest
from unittest.mock import MagicMock, AsyncMock, patch, ANY

# --------------------------------------------------------------------------
# Import Target Modules & DTOs
# --------------------------------------------------------------------------
from src.extractor.providers.kis_extractor import KISExtractor
from src.extractor.domain.dtos import RequestDTO, ResponseDTO
from src.extractor.domain.exceptions import ExtractorError
from src.extractor.domain.interfaces import IHttpClient, IAuthStrategy
from src.common.config import AppConfig

# --------------------------------------------------------------------------
# 0. Constants & Configuration
# --------------------------------------------------------------------------

# 로그 매니저 경로 (파일 I/O를 유발하므로 Patch 대상)
TARGET_LOG_MANAGER = "src.common.log.LogManager.get_logger"

# --------------------------------------------------------------------------
# 1. Fixtures (Test Environment Setup)
# --------------------------------------------------------------------------

@pytest.fixture
def mock_http_client():
    """[IHttpClient Mock] 외부 네트워크 통신 담당"""
    client = MagicMock(spec=IHttpClient)
    # 기본적으로 비동기 get 메서드를 AsyncMock으로 설정
    client.get = AsyncMock() 
    return client

@pytest.fixture
def mock_auth_strategy():
    """[IAuthStrategy Mock] 인증 토큰 발급 전략"""
    auth = MagicMock(spec=IAuthStrategy)
    auth.get_token = AsyncMock(return_value="Bearer test_token")
    return auth

@pytest.fixture
def base_config():
    """[AppConfig Mock] 테스트용 기본 AppConfig 객체"""
    config = MagicMock(spec=AppConfig)
    config.kis_base_url = "https://api.test.com"
    config.kis_app_key = "test_app_key"
    config.kis_app_secret = "test_app_secret"
    
    # 기본 정책 설정 (Happy Path용)
    config.extraction_policy = {
        "valid_job": {
            "path": "/uapi/test",
            "tr_id": "TR1234",
            "params": {"static": "value"},
            "extra_headers": {}
        },
        "header_job": {
            "path": "/uapi/header",
            "tr_id": "TR_HEAD",
            "extra_headers": {"X-Custom-Header": "CustomValue"}
        }
    }
    return config

@pytest.fixture
def kis_extractor(mock_http_client, mock_auth_strategy, base_config):
    """
    [System Under Test]
    의존성이 주입된 KISExtractor 인스턴스입니다.
    LogManager를 Patch하여 초기화 시 Disk I/O(Config Load)를 방지합니다.
    """
    with patch(TARGET_LOG_MANAGER) as mock_logger:
        instance = KISExtractor(mock_http_client, mock_auth_strategy, base_config)
        # 테스트 코드에서 logger 호출 검증이 필요하므로 명시적 할당
        instance.logger = mock_logger.return_value 
        return instance

# --------------------------------------------------------------------------
# 2. Test Cases
# --------------------------------------------------------------------------

class TestKISExtractor:

    # ==========================================
    # Category: Unit (Happy Path & Logic)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc001_happy_path_standard(self, kis_extractor, mock_http_client):
        """[TC-001] 정상 설정 및 응답(rt_cd:0) 시 ResponseDTO가 반환된다."""
        # Given
        request = RequestDTO(job_id="valid_job", params={"dynamic": "data"})
        mock_http_client.get.return_value = {"rt_cd": "0", "msg1": "Success", "output": []}

        # When
        response = await kis_extractor.extract(request)

        # Then
        assert isinstance(response, ResponseDTO)
        assert response.meta["status_code"] == "0"
        assert response.data["msg1"] == "Success"
        mock_http_client.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tc002_parameter_merging_priority(self, kis_extractor, mock_http_client):
        """[TC-002] Config의 Static Param보다 Request의 Dynamic Param이 우선순위를 가진다."""
        # Given
        # Config에는 'static': 'value'가 있음. Request로 같은 키 'static'을 덮어씌움.
        request = RequestDTO(job_id="valid_job", params={"static": "OVERRIDDEN", "new": "1"})
        mock_http_client.get.return_value = {"rt_cd": "0"}

        # When
        await kis_extractor.extract(request)

        # Then
        # 호출된 params 인자를 확인
        call_args = mock_http_client.get.call_args
        passed_params = call_args.kwargs['params']
        
        assert passed_params['static'] == "OVERRIDDEN" # Dynamic overrides Static
        assert passed_params['new'] == "1"

    @pytest.mark.asyncio
    async def test_tc003_extra_headers_injection(self, kis_extractor, mock_http_client):
        """[TC-003] 정책에 extra_headers가 정의된 경우 요청 헤더에 포함된다."""
        # Given
        request = RequestDTO(job_id="header_job") # extra_headers: X-Custom-Header 정의됨
        mock_http_client.get.return_value = {"rt_cd": "0"}

        # When
        await kis_extractor.extract(request)

        # Then
        call_args = mock_http_client.get.call_args
        passed_headers = call_args.kwargs['headers']
        
        assert passed_headers.get("X-Custom-Header") == "CustomValue"
        assert "authorization" in passed_headers # 기본 헤더도 유지 확인

    # ==========================================
    # Category: Unit (Initialization & Config)
    # ==========================================

    def test_tc004_init_fail_missing_base_url(self, mock_http_client, mock_auth_strategy):
        """[TC-004] Config에 kis_base_url이 없으면 초기화 시 ExtractorError가 발생한다."""
        # Given
        invalid_config = MagicMock(spec=AppConfig)
        invalid_config.kis_base_url = None # Missing URL

        # When & Then
        with patch(TARGET_LOG_MANAGER):
            with pytest.raises(ExtractorError, match="'kis_base_url' is missing"):
                KISExtractor(mock_http_client, mock_auth_strategy, invalid_config)

    def test_tc005_init_fail_missing_policy_dict(self, mock_http_client, mock_auth_strategy):
        """[TC-005] Config에 extraction_policy 딕셔너리가 없으면 초기화 시 ExtractorError가 발생한다."""
        # Given
        invalid_config = MagicMock(spec=AppConfig)
        invalid_config.kis_base_url = "http://valid.com"
        del invalid_config.extraction_policy # Missing Policy

        # When & Then
        with patch(TARGET_LOG_MANAGER):
            with pytest.raises(ExtractorError, match="'extraction_policy' dictionary is missing"):
                KISExtractor(mock_http_client, mock_auth_strategy, invalid_config)

    # ==========================================
    # Category: Unit (Validation Logic)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc006_validation_missing_job_id(self, kis_extractor):
        """[TC-006] Request에 job_id가 없으면 ExtractorError가 발생한다."""
        # Given
        request = RequestDTO(job_id=None)

        # When & Then
        with pytest.raises(ExtractorError, match="'job_id' is mandatory"):
            await kis_extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc007_validation_unknown_job_id(self, kis_extractor):
        """[TC-007] Config에 정의되지 않은 job_id 요청 시 ExtractorError가 발생한다."""
        # Given
        request = RequestDTO(job_id="unknown_job")

        # When & Then
        with pytest.raises(ExtractorError, match="Policy not found"):
            await kis_extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc008_validation_policy_missing_path(self, kis_extractor, base_config):
        """[TC-008] 정책에 필수 키 'path'가 누락되면 ExtractorError가 발생한다."""
        # Given
        base_config.extraction_policy["broken_job"] = {"tr_id": "TR00"} # Path Missing
        request = RequestDTO(job_id="broken_job")

        # When & Then
        with pytest.raises(ExtractorError, match="Missing keys"):
            await kis_extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc009_validation_policy_missing_tr_id(self, kis_extractor, base_config):
        """[TC-009] 정책에 필수 키 'tr_id'가 누락되면 ExtractorError가 발생한다."""
        # Given
        base_config.extraction_policy["broken_job"] = {"path": "/ok"} # tr_id Missing
        request = RequestDTO(job_id="broken_job")

        # When & Then
        with pytest.raises(ExtractorError, match="Missing keys"):
            await kis_extractor.extract(request)

    # ==========================================
    # Category: Unit (Execution & Headers)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc010_execution_auth_failure_propagation(self, kis_extractor, mock_auth_strategy):
        """[TC-010] AuthStrategy에서 에러 발생 시 예외가 전파된다."""
        # Given
        request = RequestDTO(job_id="valid_job")
        mock_auth_strategy.get_token.side_effect = ValueError("Token Server Down")

        # When & Then
        # AbstractExtractor가 잡아서 ExtractorError로 감싸거나, Unexpected로 처리함.
        # 최종적으로는 ExtractorError가 발생해야 함.
        with pytest.raises(ExtractorError, match="Extraction failed"): 
            await kis_extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc011_execution_header_mapping(self, kis_extractor, mock_http_client, base_config):
        """[TC-011] AppKey, Secret, TR_ID 등이 정확한 헤더 키로 매핑되어 전달된다."""
        # Given
        request = RequestDTO(job_id="valid_job")
        mock_http_client.get.return_value = {"rt_cd": "0"}

        # When
        await kis_extractor.extract(request)

        # Then
        call_args = mock_http_client.get.call_args
        headers = call_args.kwargs['headers']

        assert headers["appkey"] == base_config.kis_app_key
        assert headers["appsecret"] == base_config.kis_app_secret
        assert headers["tr_id"] == "TR1234" # From valid_job policy
        assert headers["authorization"] == "Bearer test_token" # From Mock Auth

    # ==========================================
    # Category: Unit (Response Parsing & Business Error)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc012_response_business_failure(self, kis_extractor, mock_http_client):
        """[TC-012] API 응답 rt_cd가 '0'이 아니면(실패) ExtractorError가 발생한다."""
        # Given
        request = RequestDTO(job_id="valid_job")
        # rt_cd='1' (Failure), msg1='Limit Exceeded'
        mock_http_client.get.return_value = {"rt_cd": "1", "msg1": "Limit Exceeded"}

        # When & Then
        with pytest.raises(ExtractorError, match="Limit Exceeded"):
            await kis_extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc013_response_missing_rt_cd(self, kis_extractor, mock_http_client):
        """[TC-013] API 응답에 rt_cd 필드가 아예 없으면 ExtractorError가 발생한다."""
        # Given
        request = RequestDTO(job_id="valid_job")
        mock_http_client.get.return_value = {"msg1": "System Error"} # No rt_cd

        # When & Then
        # 로직상 rt_cd.get(..., "") -> "" != "0" -> Error Raise
        with pytest.raises(ExtractorError, match="KIS API Failed"):
            await kis_extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc014_response_empty_data(self, kis_extractor, mock_http_client):
        """[TC-014] API 응답이 빈 딕셔너리인 경우 ExtractorError가 발생한다."""
        # Given
        request = RequestDTO(job_id="valid_job")
        mock_http_client.get.return_value = {} # Empty

        # When & Then
        with pytest.raises(ExtractorError, match="KIS API Failed"):
            await kis_extractor.extract(request)