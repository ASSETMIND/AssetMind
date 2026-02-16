import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from typing import Dict, Any, Optional

# [Target Modules] 테스트 대상 및 의존성 모듈
from src.extractor.providers.kis_extractor import KISExtractor
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ExtractorError
from src.common.interfaces import IHttpClient, IAuthStrategy
from src.common.config import ConfigManager

# ========================================================================================
# [Mocks & Stubs] 외부 의존성 격리를 위한 모의 객체 정의
# ========================================================================================

class MockSecretStr:
    """Pydantic SecretStr 동작 모방을 위한 Stub (보안 필드 테스트용)"""
    def __init__(self, value: str):
        self._value = value
    
    def get_secret_value(self) -> str:
        return self._value

class MockJobPolicy:
    """Config 내 JobPolicy 객체 모방 (설정 주입용 Stub)"""
    def __init__(self, provider: str = "KIS", path: str = "/uapi/test", 
                 params: Dict = None, tr_id: str = "TR_123"):
        self.provider = provider
        self.path = path
        self.params = params or {}
        self.tr_id = tr_id

# ========================================================================================
# [Fixtures] 테스트 환경 설정 및 의존성 주입
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger():
    """
    [Core Fix] 
    LogManager가 초기화될 때 전역 ConfigManager를 참조하여 발생하는 RuntimeError를 근본적으로 방지합니다.
    LogManager.get_logger 메서드 자체를 Mocking하여 설정 로딩 프로세스를 우회합니다.
    """
    # src.common.log.LogManager.get_logger를 패치하여 실제 로거 초기화(Config 참조)를 막음
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger, \
         patch("src.extractor.providers.kis_extractor.log_decorator") as mock_dec:
        
        # 1. 로거 호출 시 아무 동작도 하지 않는 MagicMock 반환
        mock_get_logger.return_value = MagicMock()
        
        # 2. 데코레이터가 함수 실행을 방해하지 않도록 Pass-through(투명) 처리
        # @log_decorator(...) 호출 시 -> 래퍼 함수 반환 -> 원본 함수 실행
        mock_dec.side_effect = lambda *args, **kwargs: lambda func: func
        
        yield

@pytest.fixture
def mock_http_client():
    """비동기 HTTP 요청을 모방하는 Mock Client"""
    client = MagicMock(spec=IHttpClient)
    client.get = AsyncMock()
    return client

@pytest.fixture
def mock_auth_strategy():
    """인증 토큰 발급을 모방하는 Mock Strategy"""
    strategy = MagicMock(spec=IAuthStrategy)
    strategy.get_token = AsyncMock(return_value="Bearer test_token")
    return strategy

@pytest.fixture
def mock_config():
    """정상 상태의 Config 객체 (Happy Path 기준)"""
    config = MagicMock(spec=ConfigManager)
    
    # KIS 섹션 설정
    config.kis = MagicMock()
    config.kis.base_url = "https://api.kis.com"
    config.kis.app_key = MockSecretStr("secret_key")
    config.kis.app_secret = MockSecretStr("secret_val")
    
    # Extraction Policy (Dict 접근 허용)
    config.extraction_policy = {
        "job_valid": MockJobPolicy(params={"static": "A"}),
        "job_fred": MockJobPolicy(provider="FRED"),
        "job_no_tr": MockJobPolicy(tr_id=None),  # type: ignore
    }
    return config

@pytest.fixture
def extractor(mock_http_client, mock_auth_strategy, mock_config):
    """테스트 대상 인스턴스 (SUT: System Under Test)"""
    return KISExtractor(mock_http_client, mock_auth_strategy, mock_config)

# ========================================================================================
# 1. 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_critical_config_error(mock_http_client, mock_auth_strategy, mock_config):
    """[INIT-01] kis.base_url이 비어있는 경우 초기화 단계에서 즉시 실패 (Fail-Fast)"""
    # Given: 잘못된 설정 주입 (Base URL 누락)
    mock_config.kis.base_url = ""
    
    # When & Then: 인스턴스 생성 시도 시 예외 발생 검증
    with pytest.raises(ExtractorError, match="Critical Config Error"):
        KISExtractor(mock_http_client, mock_auth_strategy, mock_config)

# ========================================================================================
# 2. 요청 검증 테스트 (Validation - MC/DC)
# ========================================================================================

def test_req_01_missing_job_id(extractor):
    """[REQ-01] Request에 job_id가 없는 경우 유효성 검증 실패"""
    # Given: job_id가 None인 잘못된 요청
    request = RequestDTO(job_id=None) # type: ignore
    
    # When & Then: validate 수행 시 예외 발생
    with pytest.raises(ExtractorError, match="'job_id' is mandatory"):
        extractor._validate_request(request)

def test_req_02_policy_not_found(extractor):
    """[REQ-02] Config에 정의되지 않은 job_id 요청 시 실패"""
    # Given: 정책에 없는 Job ID
    request = RequestDTO(job_id="job_unknown")
    
    # When & Then: 정책 조회 실패 예외 확인
    with pytest.raises(ExtractorError, match="Policy not found"):
        extractor._validate_request(request)

def test_req_03_provider_mismatch(extractor):
    """[REQ-03] Provider가 KIS가 아닌 경우 (예: FRED) 요청 거부"""
    # Given: Provider가 "FRED"로 설정된 Job
    request = RequestDTO(job_id="job_fred")
    
    # When & Then: Provider 불일치 예외 확인
    with pytest.raises(ExtractorError, match="Provider Mismatch"):
        extractor._validate_request(request)

def test_req_04_missing_tr_id(extractor):
    """[REQ-04] 정책에 필수 필드 tr_id가 누락된 경우 실패"""
    # Given: tr_id가 없는 Job Policy
    request = RequestDTO(job_id="job_no_tr")
    
    # When & Then: 필수 설정 누락 예외 확인
    with pytest.raises(ExtractorError, match="'tr_id' is missing"):
        extractor._validate_request(request)

# ========================================================================================
# 3. 정상 흐름 및 기능 테스트 (Functional & Flow)
# ========================================================================================

@pytest.mark.asyncio
async def test_flow_01_happy_path_e2e(extractor, mock_http_client):
    """[FLOW-01] 정상 요청 -> 토큰 획득 -> API 호출 -> 응답 생성 확인 (Happy Path)"""
    # Given: 정상 요청 및 Mock 응답 준비
    request = RequestDTO(job_id="job_valid")
    mock_response = {"rt_cd": "0", "msg1": "Success", "output": []}
    mock_http_client.get.return_value = mock_response
    
    # When: 추출 실행
    response = await extractor.extract(request)
    
    # Then: 응답 객체 구조 및 데이터 일치 여부 검증
    assert isinstance(response, ExtractedDTO)
    assert response.data == mock_response
    assert response.meta["job_id"] == "job_valid"
    mock_http_client.get.assert_called_once()

@pytest.mark.asyncio
async def test_flow_02_param_priority(extractor, mock_http_client):
    """[FLOW-02] 파라미터 병합 시 Request Params가 Static Policy보다 우선순위 가짐"""
    # Given: Policy={"static": "A"}, Request={"static": "B", "dynamic": "C"}
    request = RequestDTO(job_id="job_valid", params={"static": "B", "dynamic": "C"})
    mock_http_client.get.return_value = {"rt_cd": "0"}
    
    # When: 추출 실행
    await extractor.extract(request)
    
    # Then: 실제 호출된 파라미터가 덮어씌워졌는지(Override) 확인
    call_args = mock_http_client.get.call_args
    merged_params = call_args.kwargs['params']
    assert merged_params["static"] == "B"  # Policy 값 "A"가 "B"로 교체됨
    assert merged_params["dynamic"] == "C" # 새로운 파라미터 추가됨

@pytest.mark.asyncio
async def test_flow_03_url_construction(extractor, mock_http_client, mock_config):
    """[FLOW-03] Base URL과 Policy Path가 결합되어 완전한 URL 호출"""
    # Given: 특정 URL 설정
    mock_config.kis.base_url = "https://api.test.com"
    mock_config.extraction_policy["job_valid"].path = "/v1/stock"
    request = RequestDTO(job_id="job_valid")
    mock_http_client.get.return_value = {"rt_cd": "0"}
    
    # When: 추출 실행
    await extractor.extract(request)
    
    # Then: 결합된 URL로 호출되었는지 검증
    expected_url = "https://api.test.com/v1/stock"
    mock_http_client.get.assert_called_with(expected_url, headers=ANY, params=ANY)

# ========================================================================================
# 4. 보안 및 인증 테스트 (Security)
# ========================================================================================

@pytest.mark.asyncio
async def test_sec_01_secret_decoding(extractor, mock_http_client):
    """[SEC-01] SecretStr 타입의 키가 헤더에는 평문으로 복호화되어 주입됨"""
    # Given: SecretStr로 감싸진 앱 키 설정 (Fixture 참조)
    request = RequestDTO(job_id="job_valid")
    mock_http_client.get.return_value = {"rt_cd": "0"}
    
    # When: 추출 실행
    await extractor.extract(request)
    
    # Then: 헤더에 평문이 주입되었는지 확인
    call_headers = mock_http_client.get.call_args.kwargs['headers']
    assert call_headers["appkey"] == "secret_key"
    assert call_headers["appsecret"] == "secret_val"
    assert not isinstance(call_headers["appkey"], MockSecretStr)

@pytest.mark.asyncio
async def test_sec_02_token_injection(extractor, mock_http_client):
    """[SEC-02] AuthStrategy에서 발급받은 토큰이 Authorization 헤더에 주입됨"""
    # Given: 정상 요청
    request = RequestDTO(job_id="job_valid")
    mock_http_client.get.return_value = {"rt_cd": "0"}
    
    # When: 추출 실행
    await extractor.extract(request)
    
    # Then: Authorization 헤더 검증
    call_headers = mock_http_client.get.call_args.kwargs['headers']
    assert call_headers["authorization"] == "Bearer test_token"

# ========================================================================================
# 5. 데이터 안정성 및 견고성 테스트 (Robustness & Data)
# ========================================================================================

@pytest.mark.asyncio
async def test_data_01_business_failure(extractor, mock_http_client):
    """[DATA-01] API 응답 rt_cd가 '0'이 아닌 경우 Business Failure 처리"""
    # Given: 실패 코드('1')를 포함한 응답
    mock_response = {"rt_cd": "1", "msg1": "Account Number Error"}
    mock_http_client.get.return_value = mock_response
    request = RequestDTO(job_id="job_valid")
    
    # When & Then: 커스텀 예외 및 에러 메시지 전파 확인
    with pytest.raises(ExtractorError) as exc:
        await extractor.extract(request)
    
    assert "KIS API Failed" in str(exc.value)
    assert "Account Number Error" in str(exc.value)

@pytest.mark.asyncio
async def test_data_02_missing_rt_cd(extractor, mock_http_client):
    """[DATA-02] 응답에 필수 필드 rt_cd가 없는 경우 견고성 테스트"""
    # Given: 비표준 응답 포맷
    mock_response = {"data": "invalid_structure"}
    mock_http_client.get.return_value = mock_response
    request = RequestDTO(job_id="job_valid")
    
    # When & Then: 알 수 없는 에러로 처리
    with pytest.raises(ExtractorError, match="Unknown Error"):
        await extractor.extract(request)

# ========================================================================================
# 6. 예외 처리 및 데코레이터 테스트 (Exception & Decorators)
# ========================================================================================

@pytest.mark.asyncio
async def test_err_01_system_error_wrapping(extractor):
    """[ERR-01] 실행 중 예상치 못한 에러(ValueError) 발생 시 ExtractorError로 래핑"""
    # Given: _fetch_raw_data 메서드를 직접 Mocking하여 데코레이터(@rate_limit 등)를 우회
    # 이를 통해 AbstractExtractor.extract 메서드의 'except Exception' 블록 로직을 격리하여 검증
    extractor._fetch_raw_data = AsyncMock(side_effect=ValueError("Parsing Error"))
    
    request = RequestDTO(job_id="job_valid")
    
    # When & Then: 도메인 예외로 래핑되어 던져지는지 확인
    with pytest.raises(ExtractorError, match="작업 중 알 수 없는 시스템 오류 발생"):
        await extractor.extract(request)

def test_dec_01_decorator_application(extractor):
    """[DEC-01] _fetch_raw_data 메서드에 데코레이터가 적용되어 있는지 검증"""
    # Given: 테스트 대상 메서드
    method = extractor._fetch_raw_data
    
    # When & Then: __wrapped__ 속성 존재 여부로 데코레이터 적용 확인
    # NOTE: 실제 런타임에서는 데코레이터가 중첩되므로 __wrapped__가 연쇄적으로 존재함
    assert hasattr(method, "__wrapped__"), "Decorators should be applied to _fetch_raw_data"