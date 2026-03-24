import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict

# [Target Modules]
from src.extractor.providers.abstract_extractor import AbstractExtractor
from src.common.exceptions import ConfigurationError, ExtractorError
from src.common.interfaces import IHttpClient

# ========================================================================================
# [Mocks & Stubs] 외부 의존성 및 DTO 격리
# ========================================================================================

class MockRequestDTO:
    """테스트용 Request DTO (상태 제어용)"""
    def __init__(self, job_id: str = "unknown"):
        self.job_id = job_id

class MockExtractedDTO:
    """테스트용 Extracted DTO (결과 검증용)"""
    def __init__(self, data: Any = None, meta: Dict = None):
        self.data = data
        self.meta = meta or {}

class StubExtractor(AbstractExtractor):
    """
    AbstractExtractor의 템플릿 메서드 로직(extract) 및 초기화 흐름을 
    순수하게 검증하기 위한 구체화 스텁(Stub) 객체입니다.
    """
    def __init__(self, http_client: Any):
        # [Fix] 변경된 원본 __init__ 시그니처에 맞게 인자 전달 수정
        super().__init__(http_client)
        self.validate_mock = MagicMock()
        self.fetch_mock = AsyncMock()
        self.create_mock = MagicMock()

    def _validate_request(self, request: Any) -> None:
        self.validate_mock(request)

    async def _fetch_raw_data(self, request: Any) -> Any:
        return await self.fetch_mock(request)

    def _create_response(self, raw_data: Any, job_id: str) -> Any:
        return self.create_mock(raw_data, job_id)


# ========================================================================================
# [Fixtures] 테스트 환경 설정
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_infra_dependencies():
    """__init__ 단계에서 호출되는 외부 싱글톤/인프라 의존성을 안전하게 차단합니다."""
    with patch("src.extractor.providers.abstract_extractor.ConfigManager.load") as mock_config, \
         patch("src.extractor.providers.abstract_extractor.LogManager.get_logger") as mock_logger:
        
        mock_config.return_value = MagicMock()
        mock_logger.return_value = MagicMock()
        yield mock_config, mock_logger

@pytest.fixture
def mock_http_client():
    return MagicMock(spec=IHttpClient)

@pytest.fixture
def extractor(mock_http_client):
    """기본적인 정상 동작이 설정된 StubExtractor 인스턴스"""
    return StubExtractor(mock_http_client)


# ========================================================================================
# [Tests] 1. 초기화 및 방어 로직 검증 (INIT)
# ========================================================================================

def test_init_01_missing_http_client():
    """
    [INIT-01] 필수 의존성 누락 방어 로직 검증 (Coverage 61-69)
    """
    # GIVEN: IHttpClient 인스턴스가 주어지지 않은 상황 (None)
    invalid_client = None
    
    # WHEN & THEN: 초기화 시도 시 ConfigurationError가 즉시 발생해야 함 (Fail-Fast)
    with pytest.raises(ConfigurationError, match="초기화 실패: IHttpClient 인스턴스가 필요합니다."):
        StubExtractor(invalid_client)

def test_init_02_successful_initialization(mock_http_client):
    """
    [INIT-02] 정상 초기화 시 속성 할당 및 싱글톤 로드 검증 (Coverage 61-69)
    """
    # GIVEN: 유효한 IHttpClient 모의 객체
    # WHEN: StubExtractor를 초기화
    ext = StubExtractor(mock_http_client)
    
    # THEN: 내부 속성에 클라이언트와 Config/Logger가 올바르게 할당되어야 함
    assert ext.http_client == mock_http_client
    assert ext.config is not None
    assert ext.logger is not None


# ========================================================================================
# [Tests] 2. 흐름 제어 및 조건 분기 검증 (FLOW / DATA / ERR)
# ========================================================================================

@pytest.mark.asyncio
async def test_flow_01_request_is_none(extractor):
    """
    [FLOW-01] RequestDTO가 None일 경우의 Duck Typing 방어 검증 (Coverage 90-103)
    """
    # GIVEN: request가 None이며, 수집/생성 훅이 임의의 데이터를 반환하도록 설정
    extractor.fetch_mock.return_value = "raw_data"
    extractor.create_mock.return_value = MockExtractedDTO(meta={"job_id": "Unknown"})
    
    # WHEN: extract 메서드 호출
    res = await extractor.extract(None)
    
    # THEN: 에러 없이 진행되며 job_id가 "Unknown"으로 폴백(Fallback) 처리되어 전달됨
    extractor.validate_mock.assert_called_once_with(None)
    extractor.create_mock.assert_called_once_with("raw_data", "Unknown")
    assert res.meta["job_id"] == "Unknown"

@pytest.mark.asyncio
async def test_flow_02_request_missing_job_id(extractor):
    """
    [FLOW-02] RequestDTO에 job_id 속성이 없는 경우의 분기 검증 (Coverage 90-103)
    """
    # GIVEN: 객체는 존재하나 job_id 어트리뷰트가 없는 빈 클래스 인스턴스
    class EmptyRequest: pass
    req = EmptyRequest()
    extractor.fetch_mock.return_value = "raw_data"
    
    # WHEN: extract 메서드 호출
    await extractor.extract(req)
    
    # THEN: hasattr 조건식에 의해 job_id가 "Unknown"으로 폴백 처리됨
    extractor.create_mock.assert_called_once_with("raw_data", "Unknown")

@pytest.mark.asyncio
async def test_flow_03_happy_path(extractor):
    """
    [FLOW-03] 정상 흐름에서의 템플릿 메서드 생명주기 검증 (Coverage 90-103)
    """
    # GIVEN: 정상적인 RequestDTO
    req = MockRequestDTO(job_id="job_123")
    extractor.fetch_mock.return_value = "raw_data"
    extractor.create_mock.return_value = MockExtractedDTO(meta={"job_id": "job_123"})
    
    # WHEN: extract 메서드 호출
    res = await extractor.extract(req)
    
    # THEN: Validate -> Fetch -> Create 순으로 훅이 모두 정상 호출되어야 함
    extractor.validate_mock.assert_called_once_with(req)
    extractor.fetch_mock.assert_called_once_with(req)
    extractor.create_mock.assert_called_once_with("raw_data", "job_123")
    assert res.meta["job_id"] == "job_123"

@pytest.mark.asyncio
async def test_err_01_validation_failure(extractor):
    """
    [ERR-01] Validation 단계 실패 시 조기 중단(Early Exit) 및 격리 검증
    """
    # GIVEN: Validation Hook이 실패하도록 설정
    req = MockRequestDTO(job_id="job_err")
    extractor.validate_mock.side_effect = ExtractorError("Validation Failed")
    
    # WHEN & THEN: 예외가 상위로 전파되며, 이후 훅(Fetch, Create)은 절대 호출되지 않아야 함
    with pytest.raises(ExtractorError, match="Validation Failed"):
        await extractor.extract(req)
        
    extractor.fetch_mock.assert_not_called()
    extractor.create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_err_02_fetch_failure(extractor):
    """
    [ERR-02] Fetch 단계 실패 시 조기 중단(Early Exit) 검증
    """
    # GIVEN: Fetch Hook 실행 중 네트워크 등 도메인 에러 발생 시뮬레이션
    req = MockRequestDTO(job_id="job_err")
    extractor.fetch_mock.side_effect = ExtractorError("Fetch Failed")
    
    # WHEN & THEN: 예외가 전파되며 패키징(Create) 훅은 호출되지 않아야 함
    with pytest.raises(ExtractorError, match="Fetch Failed"):
        await extractor.extract(req)
        
    extractor.validate_mock.assert_called_once_with(req)
    extractor.create_mock.assert_not_called()