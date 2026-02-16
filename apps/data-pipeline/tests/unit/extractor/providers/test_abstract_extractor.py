import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Any

# [Real Imports]
from src.extractor.providers.abstract_extractor import AbstractExtractor
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ConfigurationError, ETLError, ExtractorError, NetworkConnectionError
from src.common.interfaces import IHttpClient
from src.common.config import ConfigManager

# ========================================================================================
# [Test Stub] 추상 클래스 테스트를 위한 구체화 (Stub)
# ========================================================================================

class StubExtractor(AbstractExtractor):
    """
    AbstractExtractor의 템플릿 메서드 로직을 검증하기 위한 테스트용 구현체.
    """
    def __init__(self, http_client: IHttpClient, config: ConfigManager):
        super().__init__(http_client, config)
        
        self.validate_mock = MagicMock()
        self.fetch_mock = AsyncMock()
        self.create_mock = MagicMock()

    def _validate_request(self, request: RequestDTO) -> None:
        self.validate_mock(request)

    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        return await self.fetch_mock(request)

    def _create_response(self, raw_data: Any, job_id: str = "") -> ExtractedDTO:
        return self.create_mock(raw_data)

# ========================================================================================
# [Fixtures] 테스트 환경 설정 및 Mocking
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_external_deps():
    """모든 테스트에 공통적으로 적용되는 Logger Mock 설정"""
    with patch("src.extractor.providers.abstract_extractor.LogManager.get_logger") as mock_logger:
        yield mock_logger

@pytest.fixture
def mock_logger(mock_external_deps):
    return mock_external_deps.return_value

@pytest.fixture
def mock_http_client():
    return MagicMock(spec=IHttpClient)

@pytest.fixture
def mock_config():
    return MagicMock(spec=ConfigManager)

@pytest.fixture
def extractor(mock_http_client, mock_config):
    """테스트 대상 StubExtractor 인스턴스 (Happy Path 기본 설정 포함)"""
    stub = StubExtractor(mock_http_client, mock_config)
    stub.fetch_mock.return_value = {"raw": "data"}
    stub.create_mock.return_value = ExtractedDTO(data={"raw": "data"})
    return stub

# ========================================================================================
# 1. 초기화 및 방어 로직 테스트 (Initialization)
# ========================================================================================

def test_init_01_config_none(mock_http_client):
    """[INIT-01] config가 None이면 ConfigurationError 발생 (Fail-Fast)"""
    with pytest.raises(ConfigurationError, match="초기화 실패: ConfigManager 인스턴스가 필요합니다."):
        StubExtractor(mock_http_client, None) # type: ignore

@pytest.mark.asyncio
async def test_init_02_request_none_handling(extractor, mock_logger):
    """[INIT-02] request가 None일 때 로깅 안전성 및 Validate 에러 검증"""
    # Given
    extractor.validate_mock.side_effect = ETLError("Invalid Request")
    
    # When
    with pytest.raises(ETLError, match="Invalid Request"):
        await extractor.extract(None) # type: ignore
    
    # Then
    mock_logger.info.assert_any_call("[StubExtractor] 추출 시작 | Job: Unknown")

# ========================================================================================
# 2. 흐름 제어 및 상태 테스트 (Flow Control & State)
# ========================================================================================

@pytest.mark.asyncio
async def test_flow_01_happy_path(extractor):
    """[FLOW-01] 정상 흐름: Validate -> Fetch -> Create 순서 호출 확인"""
    # Given
    request = RequestDTO(job_id="job_123")
    
    # When
    result = await extractor.extract(request)
    
    # Then
    extractor.validate_mock.assert_called_once_with(request)
    extractor.fetch_mock.assert_called_once_with(request)
    extractor.create_mock.assert_called_once()
    assert isinstance(result, ExtractedDTO)

@pytest.mark.asyncio
async def test_flow_02_validation_failure_stops_execution(extractor):
    """[FLOW-02] Validate 실패 시 Fetch 단계로 넘어가지 않아야 함 (Flow Control)"""
    # Given
    extractor.validate_mock.side_effect = ExtractorError("Validation Failed")
    request = RequestDTO(job_id="job_fail")
    
    # When
    with pytest.raises(ExtractorError, match="Validation Failed"):
        await extractor.extract(request)
    
    # Then
    extractor.fetch_mock.assert_not_called()
    extractor.create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_flow_03_statelessness(extractor):
    """[FLOW-03] 단일 인스턴스로 여러 요청 처리 시 상태 독립성 유지"""
    # Given
    req1 = RequestDTO(job_id="job_A")
    req2 = RequestDTO(job_id="job_B")
    
    # Side effect: 호출마다 다른 데이터 반환
    extractor.fetch_mock.side_effect = ["data_A", "data_B"]
    
    # When
    await extractor.extract(req1)
    await extractor.extract(req2)
    
    # Then
    assert extractor.fetch_mock.call_count == 2
    extractor.fetch_mock.assert_has_calls([call(req1), call(req2)])

# ========================================================================================
# 3. 에러 핸들링 테스트 (Error Handling)
# ========================================================================================

@pytest.mark.asyncio
async def test_err_01_network_error_propagation(extractor, mock_logger):
    """[ERR-01] ETLError(Network 등) 발생 시 ERROR 로그 기록 및 원본 예외 전파 (Re-raise)"""
    # Given
    extractor.fetch_mock.side_effect = NetworkConnectionError("Connection Timeout")
    request = RequestDTO(job_id="job_net")
    
    # When
    with pytest.raises(NetworkConnectionError) as exc_info:
        await extractor.extract(request)
    
    # Then
    assert "Connection Timeout" in str(exc_info.value)
    # [Fix] 실제 로그에는 예외 클래스 이름이 포함됨: '[NetworkConnectionError] Connection Timeout'
    mock_logger.error.assert_called_with("[StubExtractor] 도메인 로직 실패 | Job: job_net | Error: [NetworkConnectionError] Connection Timeout")

@pytest.mark.asyncio
async def test_err_02_common_error_propagation(extractor, mock_logger):
    """[ERR-02] ExtractorError 발생 시 로그 ERROR 기록 및 그대로 전파"""
    # Given
    origin_error = ExtractorError("Business Logic Fail")
    extractor.fetch_mock.side_effect = origin_error
    request = RequestDTO(job_id="job_biz")
    
    # When
    with pytest.raises(ExtractorError) as exc_info:
        await extractor.extract(request)
    
    # Then
    assert exc_info.value is origin_error
    # [Fix] 실제 로그에는 예외 클래스 이름이 포함됨: '[ExtractorError] Business Logic Fail'
    mock_logger.error.assert_called_with("[StubExtractor] 도메인 로직 실패 | Job: job_biz | Error: [ExtractorError] Business Logic Fail")

@pytest.mark.asyncio
async def test_err_03_unknown_exception_handling(extractor, mock_logger):
    """[ERR-03] 알 수 없는 예외(KeyError 등) 발생 시 로그 ERROR(Stack Trace) 및 ExtractorError 래핑"""
    # Given
    extractor.fetch_mock.side_effect = KeyError("Unexpected Key")
    request = RequestDTO(job_id="job_bug")
    
    # When
    with pytest.raises(ExtractorError, match="작업 중 알 수 없는 시스템 오류 발생"):
        await extractor.extract(request)
    
    # Then
    mock_logger.error.assert_called_with(
        "[StubExtractor] 작업 중 알 수 없는 시스템 오류 발생 | Job: job_bug | Error: 'Unexpected Key'", 
        exc_info=True
    )

# ========================================================================================
# 4. 데이터 검증 및 로깅 테스트 (Data & Logging)
# ========================================================================================

@pytest.mark.asyncio
async def test_data_01_response_packaging(extractor):
    """[DATA-01] _create_response가 반환한 DTO가 최종 반환되는지 확인"""
    # Given
    expected_response = ExtractedDTO(data={"valid": True})
    extractor.create_mock.return_value = expected_response
    request = RequestDTO(job_id="job_data")
    
    # When
    result = await extractor.extract(request)
    
    # Then
    assert result is expected_response
    assert result.data == {"valid": True}

@pytest.mark.asyncio
async def test_log_01_logging_sequence(extractor, mock_logger):
    """[LOG-01] 정상 실행 시 시작/종료 로그가 INFO 레벨로 기록되는지 확인"""
    # Given
    request = RequestDTO(job_id="job_log")
    
    # When
    await extractor.extract(request)
    
    # Then
    mock_logger.info.assert_any_call("[StubExtractor] 추출 시작 | Job: job_log")
    mock_logger.info.assert_any_call("[StubExtractor] 추출 완료 | Job: job_log")