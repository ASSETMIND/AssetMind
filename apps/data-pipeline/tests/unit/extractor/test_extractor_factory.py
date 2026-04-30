import pytest
from unittest.mock import MagicMock, patch
from typing import Dict

# [Target Modules]
from src.extractor.extractor_factory import ExtractorFactory
from src.common.exceptions import ExtractorError
from src.common.interfaces import IHttpClient, IAuthStrategy

# [Implementations]
from src.extractor.providers.kis_extractor import KISExtractor
from src.extractor.providers.upbit_extractor import UPBITExtractor
from src.extractor.providers.fred_extractor import FREDExtractor
from src.extractor.providers.ecos_extractor import ECOSExtractor
from src.extractor.adapters.auth import KISAuthStrategy, UPBITAuthStrategy


# ========================================================================================
# [Mocks & Stubs] 실제 의존성(Test Doubles) 격리
# ========================================================================================

class MockSecretStr:
    """Pydantic SecretStr 동작 모방을 위한 Stub"""
    def __init__(self, value: str):
        self._value = value
    
    def get_secret_value(self) -> str:
        return self._value

class MockPolicy:
    """ConfigManager 내부의 extraction_policy Value 객체 모방"""
    def __init__(self, provider: str):
        self.provider = provider

class MockConfig:
    """ConfigManager 객체 모방 (프로덕션 환경과 동일한 속성 및 메서드 제공)"""
    def __init__(self, policies: Dict[str, MockPolicy] = None):
        self.extraction_policy = policies if policies is not None else {}
        
        # Provider Configs
        self.kis = MagicMock()
        self.kis.base_url = "https://api.kis.test"
        self.kis.app_key = MockSecretStr("kis_key")
        self.kis.app_secret = MockSecretStr("kis_secret")
        
        self.upbit = MagicMock()
        self.upbit.base_url = "https://api.upbit.test"
        self.upbit.api_key = MockSecretStr("upbit_ak")
        self.upbit.secret_key = MockSecretStr("upbit_sk")

        self.fred = MagicMock()
        self.fred.base_url = "https://api.fred.test"
        self.fred.api_key = MockSecretStr("fred_key")
        
        self.ecos = MagicMock()
        self.ecos.base_url = "https://api.ecos.test"
        self.ecos.api_key = MockSecretStr("ecos_key")

    def get_extractor(self, job_id: str):
        """내부 get_extractor 메서드 모방. 정책 부재 시 명확한 에러 반환"""
        if not self.extraction_policy:
            raise ExtractorError("Configuration Error: Empty policies")
        if job_id not in self.extraction_policy:
            raise ExtractorError(f"Configuration Error: Job ID not found - {job_id}")
        return self.extraction_policy[job_id]


# ========================================================================================
# [Fixtures] 테스트 환경 설정 및 격리 (Isolation)
# ========================================================================================

@pytest.fixture(autouse=True)
def reset_factory_state():
    """
    [Core Fix] Factory Class의 전역 상태(Global State) 격리 픽스처.
    테스트 간 간섭을 원천 차단하기 위해 인증 캐시를 완벽히 초기화합니다.
    (로거는 데코레이터에서 처리되므로 팩토리 상태 관리가 불필요함)
    """
    ExtractorFactory._auth_cache = {}
    yield
    ExtractorFactory._auth_cache = {}

@pytest.fixture
def mock_http_client():
    """HTTP 클라이언트 Mocking"""
    return MagicMock(spec=IHttpClient)

@pytest.fixture
def config_with_policies():
    """표준적인 정책(Happy Path & Edge Case)이 포함된 설정 객체"""
    policies = {
        "job_kis": MockPolicy("KIS"),
        "job_upbit": MockPolicy("UPBIT"),
        "job_fred": MockPolicy("FRED"),
        "job_ecos": MockPolicy("Ecos"),       # 대소문자 혼용 테스트용
        "job_unknown": MockPolicy("BINANCE")  # 미지원 Provider 테스트용
    }
    return MockConfig(policies)

@pytest.fixture(autouse=True)
def mock_config_loader(config_with_policies):
    """
    [Core Fix] 팩토리 내부의 ConfigManager.load() 호출을 철저히 제어하여 파일 I/O를 막고 
    우리가 통제할 수 있는 MockConfig를 반환하도록 패칭(Patching)합니다.
    """
    with patch("src.extractor.extractor_factory.ConfigManager.load") as mock_load:
        mock_load.return_value = config_with_policies
        yield mock_load


# ========================================================================================
# 1. 기능 정상 동작 테스트 (Functional Success)
# ========================================================================================

def test_func_01_create_kis_extractor(mock_http_client):
    """[FUNC-01] KIS 정책 -> KISExtractor 생성 및 KISAuthStrategy 주입 확인"""
    # GIVEN (전제 조건): KIS에 매핑된 job_id 준비
    job_id = "job_kis"
    
    # WHEN (수행): 팩토리를 통해 Extractor 생성
    extractor = ExtractorFactory.create_extractor(job_id, mock_http_client)
    
    # THEN (검증): KIS 전용 객체와 인증 전략이 올바르게 생성/주입되었는지 확인
    assert isinstance(extractor, KISExtractor)
    assert isinstance(extractor.auth_strategy, KISAuthStrategy)

def test_func_02_create_upbit_extractor(mock_http_client):
    """[FUNC-02] UPBIT 정책 -> UPBITExtractor 생성 및 UPBITAuthStrategy 주입 확인"""
    # GIVEN (전제 조건): UPBIT에 매핑된 job_id 준비
    job_id = "job_upbit"
    
    # WHEN (수행)
    extractor = ExtractorFactory.create_extractor(job_id, mock_http_client)
    
    # THEN (검증)
    assert isinstance(extractor, UPBITExtractor)
    assert isinstance(extractor.auth_strategy, UPBITAuthStrategy)

def test_func_03_create_fred_extractor(mock_http_client):
    """[FUNC-03] FRED 정책 -> FREDExtractor 생성 (인증 전략 없음)"""
    # GIVEN (전제 조건): 무인증 Provider인 FRED job_id 준비
    job_id = "job_fred"
    
    # WHEN (수행)
    extractor = ExtractorFactory.create_extractor(job_id, mock_http_client)
    
    # THEN (검증): FRED 객체가 생성되며, 내부에 auth_strategy 의존성이 없음을 간접 확인
    assert isinstance(extractor, FREDExtractor)

def test_func_04_provider_case_normalization(mock_http_client):
    """[FUNC-04] Provider 대소문자 혼용('Ecos') -> 대문자 변환 및 ECOSExtractor 생성"""
    # GIVEN (전제 조건): 설정값이 "Ecos"로 입력된 job_id 준비
    job_id = "job_ecos"
    
    # WHEN (수행)
    extractor = ExtractorFactory.create_extractor(job_id, mock_http_client)
    
    # THEN (검증): 강제 대문자 변환(Upper) 로직을 통과하여 정상 생성됨
    assert isinstance(extractor, ECOSExtractor)


# ========================================================================================
# 2. 상태 및 캐싱 전략 테스트 (State & Caching Strategy)
# ========================================================================================

def test_cache_01_auth_strategy_reuse(mock_http_client):
    """[CACHE-01] 캐시 적중(Hit) 시 기존 인증 객체 재사용 검증 (Identity Check)"""
    # GIVEN (전제 조건): 이미 메모리(캐시)에 Mock 인증 객체가 등록된 상황
    mock_auth = MagicMock(spec=IAuthStrategy)
    ExtractorFactory._auth_cache["KIS"] = mock_auth
    
    # WHEN (수행): 동일한 Provider(KIS)의 Extractor 생성 요청
    extractor = ExtractorFactory.create_extractor("job_kis", mock_http_client)
    
    # THEN (검증): 새로 객체를 만들지 않고 주입된 기존 Mock 객체를 그대로(`is`) 재사용함
    assert extractor.auth_strategy is mock_auth

def test_cache_02_auth_strategy_creation(mock_http_client):
    """[CACHE-02] 캐시 미적중(Miss) 시 신규 생성 및 캐시 저장 검증"""
    # GIVEN (전제 조건): 캐시가 완전히 비어있음 (autouse fixture가 보장)
    assert "KIS" not in ExtractorFactory._auth_cache
    
    # WHEN (수행): 최초 생성 요청
    ExtractorFactory.create_extractor("job_kis", mock_http_client)
    
    # THEN (검증): 신규 객체가 캐시에 올바른 키("KIS")로 적재됨
    assert "KIS" in ExtractorFactory._auth_cache
    assert isinstance(ExtractorFactory._auth_cache["KIS"], KISAuthStrategy)


# ========================================================================================
# 3. 초기화 및 내부 로직 테스트 (Initialization & Internal Logic)
# ========================================================================================

def test_int_01_internal_auth_validation(config_with_policies):
    """[INT-01] 내부 메서드 _get_or_create_auth에 잘못된 Provider 전달 시 예외 처리"""
    # GIVEN (전제 조건): 지원하지 않는 잘못된 인증 Provider 이름 지정
    invalid_provider = "INVALID_PROVIDER"
    
    # WHEN & THEN (수행 및 검증): 내부 전략 생성기 호출 시 지원하지 않는다는 에러 발생 확인
    with pytest.raises(ExtractorError, match="지원하지 않는 인증 제공자입니다"):
        ExtractorFactory._get_or_create_auth(invalid_provider, config_with_policies)


# ========================================================================================
# 4. 예외 처리 및 회복력 테스트 (Error Handling & Resilience)
# ========================================================================================

def test_conf_01_empty_policies(mock_http_client, mock_config_loader):
    """[CONF-01] 정책 설정이 완전히 비어있는 경우 (Empty Dictionary)의 조기 에러 처리"""
    # GIVEN (전제 조건): 정책이 아예 존재하지 않는 빈 Config 주입
    empty_config = MockConfig(policies={})
    mock_config_loader.return_value = empty_config
    
    # WHEN & THEN (수행 및 검증): 정책 조회가 불가능하므로 ExtractorError로 조기 차단됨
    with pytest.raises(ExtractorError, match="Configuration Error: Empty policies"):
        ExtractorFactory.create_extractor("any_job", mock_http_client)

def test_err_01_undefined_job_id(mock_http_client):
    """[ERR-01] 설정에 정의되지 않은 Job ID 요청 시 방어 로직 검증"""
    # GIVEN (전제 조건): 정책 목록에 없는 job_id
    unknown_job_id = "job_does_not_exist"
    
    # WHEN & THEN (수행 및 검증)
    with pytest.raises(ExtractorError, match="Job ID not found"):
        ExtractorFactory.create_extractor(unknown_job_id, mock_http_client)

def test_err_02_unsupported_provider(mock_http_client):
    """[ERR-02] 정책은 존재하나 팩토리에 구현되지 않은 Provider인 경우"""
    # GIVEN (전제 조건): "BINANCE"로 설정된 job_unknown 지정
    
    # WHEN & THEN (수행 및 검증): 해당 분기가 없으므로 에러 처리 및 메시지 확인
    with pytest.raises(ExtractorError, match="지원하지 않는 제공자입니다: 'BINANCE'"):
        ExtractorFactory.create_extractor("job_unknown", mock_http_client)

def test_err_03_instantiation_failure(mock_http_client):
    """[ERR-03] Extractor 클래스 내부의 생성 실패(에러)를 도메인 에러로 래핑하여 상위 전파"""
    # GIVEN (전제 조건): KISExtractor 생성자 호출 시 강제로 예기치 않은 에러 발생시키기 (Patch)
    with patch("src.extractor.extractor_factory.KISExtractor") as mock_cls:
        mock_cls.side_effect = TypeError("Constructor Failed")
        
        # WHEN & THEN (수행 및 검증): 원본 에러(TypeError)가 ExtractorError로 안전하게 래핑되었는지 확인
        with pytest.raises(ExtractorError, match="'KIS' 수집기 초기화에 실패했습니다: Constructor Failed"):
            ExtractorFactory.create_extractor("job_kis", mock_http_client)


# ========================================================================================
# 5. 의존성 격리 테스트 (Dependency Isolation)
# ========================================================================================

def test_di_01_isolation(mock_http_client):
    """[DI-01] 팩토리가 생성한 객체에 HTTP Client가 정확하게 전달(주입)되는지 확인"""
    # GIVEN (전제 조건): 통제된 mock_http_client 객체 주입 준비
    
    # WHEN (수행)
    result = ExtractorFactory.create_extractor("job_kis", mock_http_client)
    
    # THEN (검증): 리플렉션 없이 명시적으로 인스턴스가 조립되며 주소값(`is`)이 일치하는지 확인
    assert result.http_client is mock_http_client