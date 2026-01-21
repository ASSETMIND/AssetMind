import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call, ANY

# --------------------------------------------------------------------------
# Import Real Objects (DTO) & Target Class
# --------------------------------------------------------------------------
from src.extractor.providers.abstract_extractor import AbstractExtractor
from src.extractor.domain.dtos import RequestDTO, ResponseDTO
from src.extractor.domain.exceptions import ExtractorError, NetworkError
from src.extractor.domain.interfaces import IHttpClient
from src.common.config import AppConfig

# --------------------------------------------------------------------------
# 0. Constants & Configuration
# --------------------------------------------------------------------------

# 로그 매니저 경로 (파일 I/O를 유발하므로 Patch 대상)
TARGET_LOG_MANAGER = "src.common.log.LogManager.get_logger"

# --------------------------------------------------------------------------
# 1. Fixtures (Test Environment Setup)
# --------------------------------------------------------------------------

class ConcreteMockExtractor(AbstractExtractor):
    """[Helper] AbstractExtractor 테스트를 위한 최소 구현체"""
    def _validate_request(self, request: RequestDTO) -> None:
        pass

    async def _fetch_raw_data(self, request: RequestDTO) -> any:
        return {"mock": "data"}

    def _create_response(self, raw_data: any) -> ResponseDTO:
        return ResponseDTO(data=raw_data, meta={})

@pytest.fixture
def mock_http_client():
    """[IHttpClient Mock] 외부 네트워크 통신 담당"""
    return MagicMock(spec=IHttpClient)

@pytest.fixture
def mock_config():
    """[AppConfig Mock] 파일 시스템 의존성 제거"""
    config = MagicMock(spec=AppConfig)
    config.extraction_policy = {"valid_job": {"active": True}}
    return config

@pytest.fixture
def extractor(mock_http_client, mock_config):
    """
    [System Under Test]
    AbstractExtractor를 상속받은 ConcreteMockExtractor의 인스턴스입니다.
    LogManager를 Patch하여 초기화 시 Disk I/O(Config Load)를 방지합니다.
    """
    with patch(TARGET_LOG_MANAGER) as mock_get_logger:
        # Logger Mock 생성 및 주입
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance
        
        instance = ConcreteMockExtractor(mock_http_client, mock_config)
        
        # 내부 메서드 호출 감지를 위해 Spy/Mock 부착
        # (인스턴스 메서드를 Mock으로 덮어씌워 side_effect 제어 및 호출 검증)
        instance._validate_request = MagicMock(wraps=instance._validate_request)
        instance._fetch_raw_data = AsyncMock(wraps=instance._fetch_raw_data)
        instance._create_response = MagicMock(wraps=instance._create_response)
        
        # 테스트 코드에서 logger 호출 검증이 필요하므로 명시적 할당
        instance.logger = mock_logger_instance
        return instance

# --------------------------------------------------------------------------
# 2. Test Cases
# --------------------------------------------------------------------------

class TestAbstractExtractor:
    
    # ==========================================
    # Category: Unit (Happy Path & Logic)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc001_standard_flow(self, extractor):
        """[TC-001] 정상 요청(valid) 시 Validate -> Fetch -> Create 순서로 실행되고 결과가 반환된다."""
        # Given
        request = RequestDTO(job_id="valid", params={})
        
        # When
        result = await extractor.extract(request)
        
        # Then
        extractor._validate_request.assert_called_once_with(request)
        extractor._fetch_raw_data.assert_awaited_once_with(request)
        extractor._create_response.assert_called_once()
        assert isinstance(result, ResponseDTO)

    @pytest.mark.asyncio
    async def test_tc002_lifecycle_logging(self, extractor):
        """[TC-002] extract 실행 시 시작(Starting)과 종료(completed) 로그가 기록된다."""
        # Given
        request = RequestDTO(job_id="valid", params={})

        # When
        await extractor.extract(request)

        # Then
        info_calls = [args[0][0] for args in extractor.logger.info.call_args_list]
        assert any("Starting" in log for log in info_calls)
        assert any("completed" in log for log in info_calls)

    # ==========================================
    # Category: Unit (Config Validation)
    # ==========================================

    def test_tc003_init_fail_missing_config(self, mock_http_client):
        """[TC-003] Config가 None으로 주입되면 초기화 단계에서 ExtractorError가 발생한다."""
        # Given
        config = None

        # When & Then
        with patch(TARGET_LOG_MANAGER):
            with pytest.raises(ExtractorError, match="'AppConfig' cannot be None"):
                ConcreteMockExtractor(mock_http_client, config)

    def test_tc004_init_success(self, mock_http_client, mock_config):
        """[TC-004] 유효한 Client와 Config 주입 시 인스턴스가 정상 생성된다."""
        # Given
        config = mock_config

        # When
        with patch(TARGET_LOG_MANAGER):
            instance = ConcreteMockExtractor(mock_http_client, config)
        
        # Then
        assert instance.config == config
        assert instance.http_client == mock_http_client

    # ==========================================
    # Category: Boundary & Null Safety
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc005_null_request_safety(self, extractor):
        """[TC-005] Request 객체가 None일 때 발생하는 에러를 ExtractorError로 래핑하여 안전하게 처리한다."""
        # Given
        request = None

        # When & Then
        with pytest.raises(ExtractorError, match="Extraction failed"):
            await extractor.extract(request)

    @pytest.mark.asyncio
    async def test_tc006_empty_raw_data(self, extractor):
        """[TC-006] _fetch 단계에서 None이 반환되어도 에러 없이 _create 단계로 전달된다."""
        # Given
        request = RequestDTO(job_id="valid", params={})
        extractor._fetch_raw_data.return_value = None

        # When
        await extractor.extract(request)

        # Then
        extractor._create_response.assert_called_once_with(None)

    # ==========================================
    # Category: Exception (Request & Policy)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc007_validation_error_reraise(self, extractor):
        """[TC-007] _validate 단계에서 ExtractorError 발생 시 경고 로그 후 재발생(Re-raise)시킨다."""
        # Given
        request = RequestDTO(job_id="invalid", params={})
        extractor._validate_request.side_effect = ExtractorError("Policy Violation")

        # When & Then
        with pytest.raises(ExtractorError, match="Policy Violation"):
            await extractor.extract(request)
        
        # Then (Isolation Check)
        extractor._fetch_raw_data.assert_not_called()
        extractor.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_tc008_network_error_isolation(self, extractor):
        """[TC-008] _fetch 중 NetworkError 발생 시 ExtractorError로 변환하고 에러 로그를 남긴다."""
        # Given
        request = RequestDTO(job_id="valid", params={})
        network_error = NetworkError("Connection Refused")
        extractor._fetch_raw_data.side_effect = network_error

        # When & Then
        with pytest.raises(ExtractorError, match="Network failure") as exc_info:
            await extractor.extract(request)

        # Then (Chaining Check)
        assert exc_info.value.__cause__ is network_error
        extractor.logger.error.assert_called()

    # ==========================================
    # Category: Exception (Response Logic)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc009_packaging_error_reraise(self, extractor):
        """[TC-009] _create 중 ExtractorError 발생 시 경고 로그 후 재발생시킨다."""
        # Given
        request = RequestDTO(job_id="valid", params={})
        extractor._create_response.side_effect = ExtractorError("Packaging Failed")

        # When & Then
        with pytest.raises(ExtractorError, match="Packaging Failed"):
            await extractor.extract(request)
        
        # Then
        extractor.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_tc010_uncaught_exception_safety(self, extractor):
        """[TC-010] 예상치 못한 버그(ValueError) 발생 시 Stack Trace와 함께 ExtractorError로 래핑한다."""
        # Given
        request = RequestDTO(job_id="bug", params={})
        extractor._fetch_raw_data.side_effect = ValueError("Unexpected Bug")

        # When & Then
        with pytest.raises(ExtractorError, match="Extraction failed"):
            await extractor.extract(request)

        # Then
        args, kwargs = extractor.logger.error.call_args
        assert kwargs.get('exc_info') is True

    # ==========================================
    # Category: Resource & State
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc011_config_immutability(self, extractor):
        """[TC-011] extract 실행 도중 주입된 Config 객체의 내용이 변경되지 않음을 보장한다."""
        # Given
        request = RequestDTO(job_id="valid", params={})
        original_policy = extractor.config.extraction_policy.copy()

        # When
        await extractor.extract(request)

        # Then
        assert extractor.config.extraction_policy == original_policy

    @pytest.mark.asyncio
    async def test_tc012_execution_sequence(self, extractor):
        """[TC-012] Validate가 성공하면 즉시 Fetch가 호출되는 실행 순서를 보장한다."""
        # Given
        request = RequestDTO(job_id="valid", params={})
        
        manager = MagicMock()
        manager.attach_mock(extractor._validate_request, 'validate')
        manager.attach_mock(extractor._fetch_raw_data, 'fetch')
        manager.attach_mock(extractor._create_response, 'create')

        # When
        await extractor.extract(request)

        # Then
        expected_calls = [
            call.validate(request),
            call.fetch(request),
            call.create(ANY)
        ]
        manager.assert_has_calls(expected_calls, any_order=False)