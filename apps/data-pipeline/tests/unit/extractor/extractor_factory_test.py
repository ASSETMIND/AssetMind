import pytest
from unittest.mock import MagicMock, patch
from typing import Dict

# [Target Modules]
from src.extractor.extractor_factory import ExtractorFactory
from src.extractor.domain.exceptions import ExtractorError
from src.extractor.domain.interfaces import IHttpClient, IAuthStrategy
from src.common.config import AppConfig

# [Implementations]
from src.extractor.providers.kis_extractor import KISExtractor
from src.extractor.providers.upbit_extractor import UPBITExtractor
from src.extractor.providers.fred_extractor import FREDExtractor
from src.extractor.providers.ecos_extractor import ECOSExtractor
from src.extractor.adapters.auth import KISAuthStrategy, UPBITAuthStrategy

# ========================================================================================
# [Mocks & Stubs] 실제 객체와 동일한 인터페이스를 갖도록 설계 (Test Doubles)
# ========================================================================================

class MockSecretStr:
    """Pydantic SecretStr 동작 모방을 위한 Stub"""
    def __init__(self, value: str):
        self._value = value
    
    def get_secret_value(self) -> str:
        return self._value

class MockPolicy:
    """AppConfig.extraction_policy의 Value 객체 모방"""
    def __init__(self, provider: str):
        self.provider = provider

class MockConfig:
    """AppConfig 객체 모방 (프로덕션 환경과 동일한 속성 구조 제공)"""
    def __init__(self, policies: Dict[str, MockPolicy] = None):
        self.extraction_policy = policies or {}
        
        # 1. KIS Config
        self.kis = MagicMock()
        self.kis.base_url = "https://api.kis.test"
        self.kis.app_key = MockSecretStr("kis_key")
        self.kis.app_secret = MockSecretStr("kis_secret")
        
        # 2. UPBIT Config
        self.upbit = MagicMock()
        self.upbit.base_url = "https://api.upbit.test"
        self.upbit.api_key = MockSecretStr("upbit_ak")
        self.upbit.secret_key = MockSecretStr("upbit_sk")

        # 3. FRED Config
        self.fred = MagicMock()
        self.fred.base_url = "https://api.fred.test"
        self.fred.api_key = MockSecretStr("fred_key")
        
        # 4. ECOS Config
        self.ecos = MagicMock()
        self.ecos.base_url = "https://api.ecos.test"
        self.ecos.api_key = MockSecretStr("ecos_key")

# ========================================================================================
# [Fixtures] 테스트 환경 설정 및 격리 (Isolation)
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger_and_reset_state():
    """
    [Core Fix] Factory Class의 전역 상태(Global State) 격리 픽스처.
    1. LogManager.get_logger를 Mocking하여 설정 파일 로딩으로 인한 Side-effect 방지.
    2. 테스트 전/후로 _auth_cache와 _logger를 초기화하여 테스트 간 간섭 제거.
    """
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        mock_get_logger.return_value = MagicMock()
        
        # Setup: 상태 초기화
        ExtractorFactory._auth_cache = {}
        ExtractorFactory._logger = None
        
        yield
        
        # Teardown: 상태 초기화 (안전장치)
        ExtractorFactory._auth_cache = {}
        ExtractorFactory._logger = None

@pytest.fixture
def mock_http_client():
    return MagicMock(spec=IHttpClient)

@pytest.fixture
def config_with_policies():
    """표준적인 정책(Happy Path & Edge Case)이 포함된 설정 객체"""
    policies = {
        "job_kis": MockPolicy("KIS"),
        "job_upbit": MockPolicy("UPBIT"),
        "job_fred": MockPolicy("FRED"),
        "job_ecos": MockPolicy("Ecos"),  # 대소문자 혼용 테스트용
        "job_unknown": MockPolicy("BINANCE") # 미지원 Provider 테스트용
    }
    return MockConfig(policies)

# ========================================================================================
# 1. 기능 정상 동작 테스트 (Functional Success)
# ========================================================================================

def test_func_01_create_kis_extractor(mock_http_client, config_with_policies):
    """[FUNC-01] KIS 정책 -> KISExtractor 생성 및 KISAuthStrategy 주입 확인"""
    job_id = "job_kis"
    extractor = ExtractorFactory.create_extractor(job_id, mock_http_client, config_with_policies)
    
    assert isinstance(extractor, KISExtractor)
    assert isinstance(extractor.auth_strategy, KISAuthStrategy)

def test_func_02_create_upbit_extractor(mock_http_client, config_with_policies):
    """[FUNC-02] UPBIT 정책 -> UPBITExtractor 생성 및 UPBITAuthStrategy 주입 확인"""
    job_id = "job_upbit"
    extractor = ExtractorFactory.create_extractor(job_id, mock_http_client, config_with_policies)
    
    assert isinstance(extractor, UPBITExtractor)
    assert isinstance(extractor.auth_strategy, UPBITAuthStrategy)

def test_func_03_create_fred_extractor(mock_http_client, config_with_policies):
    """[FUNC-03] FRED 정책 -> FREDExtractor 생성 (인증 전략 없음)"""
    job_id = "job_fred"
    extractor = ExtractorFactory.create_extractor(job_id, mock_http_client, config_with_policies)
    
    assert isinstance(extractor, FREDExtractor)

def test_func_04_provider_case_normalization(mock_http_client, config_with_policies):
    """[FUNC-04] Provider 대소문자 혼용('Ecos') -> 대문자 변환 및 ECOSExtractor 생성"""
    job_id = "job_ecos"
    extractor = ExtractorFactory.create_extractor(job_id, mock_http_client, config_with_policies)
    
    assert isinstance(extractor, ECOSExtractor)

# ========================================================================================
# 2. 상태 및 캐싱 전략 테스트 (State & Caching Strategy)
# ========================================================================================

def test_cache_01_auth_strategy_reuse(mock_http_client, config_with_policies):
    """[CACHE-01] 캐시 적중(Hit) 시 기존 인증 객체 재사용 검증 (Identity Check)"""
    # Given: 이미 캐시에 Mock 객체가 등록된 상황
    mock_auth = MagicMock(spec=IAuthStrategy)
    ExtractorFactory._auth_cache["KIS"] = mock_auth
    
    # When
    extractor = ExtractorFactory.create_extractor("job_kis", mock_http_client, config_with_policies)
    
    # Then: 생성된 Extractor가 우리가 주입한 Mock Auth 객체를 그대로 사용하는지 확인
    assert extractor.auth_strategy is mock_auth

def test_cache_02_auth_strategy_creation(mock_http_client, config_with_policies):
    """[CACHE-02] 캐시 미적중(Miss) 시 신규 생성 및 캐시 저장 검증"""
    # Given: 캐시가 비어있음 (Fixture 보장)
    
    # When
    ExtractorFactory.create_extractor("job_kis", mock_http_client, config_with_policies)
    
    # Then
    assert "KIS" in ExtractorFactory._auth_cache
    assert isinstance(ExtractorFactory._auth_cache["KIS"], KISAuthStrategy)

# ========================================================================================
# 3. 초기화 및 내부 로직 테스트 (Initialization & Internal Logic)
# ========================================================================================

def test_init_01_lazy_logger_loading():
    """[INIT-01] _get_logger 호출 시 로거 객체 생성 (Lazy Loading)"""
    # Given: 초기 상태 확인
    assert ExtractorFactory._logger is None
    
    # When
    logger = ExtractorFactory._get_logger()
    
    # Then
    assert logger is not None
    assert ExtractorFactory._logger is not None

def test_init_02_logger_singleton():
    """[INIT-02] _get_logger 재호출 시 기존 인스턴스 재사용 (Singleton & Branch Coverage)"""
    # Given: 로거가 이미 생성된 상태
    logger1 = ExtractorFactory._get_logger()
    
    # When: 두 번째 호출
    logger2 = ExtractorFactory._get_logger()
    
    # Then: 동일 인스턴스인지 확인 (Branch 'if cls._logger is None' -> False 커버)
    assert logger1 is logger2

def test_int_01_internal_auth_validation(config_with_policies):
    """[INT-01] 내부 메서드 _get_or_create_auth에 잘못된 Provider 전달 시 에러"""
    with pytest.raises(ExtractorError, match="Auth Strategy not defined"):
        ExtractorFactory._get_or_create_auth("INVALID_PROVIDER", config_with_policies)

# ========================================================================================
# 4. 예외 처리 및 회복력 테스트 (Error Handling & Resilience)
# ========================================================================================

def test_conf_01_empty_policies(mock_http_client):
    """[CONF-01] 정책 설정이 비어있는 경우(Empty Dict) 에러 발생"""
    empty_config = MockConfig(policies={})
    with pytest.raises(ExtractorError, match="Configuration Error"):
        ExtractorFactory.create_extractor("any_job", mock_http_client, empty_config)

def test_err_01_undefined_job_id(mock_http_client, config_with_policies):
    """[ERR-01] 설정에 없는 Job ID 요청 시 ExtractorError 발생"""
    with pytest.raises(ExtractorError, match="Configuration Error"):
        ExtractorFactory.create_extractor("job_does_not_exist", mock_http_client, config_with_policies)

def test_err_02_unsupported_provider(mock_http_client, config_with_policies):
    """[ERR-02] 정책은 존재하나 미지원 Provider(BINANCE)인 경우 에러 발생"""
    with pytest.raises(ExtractorError, match="Unsupported Provider"):
        ExtractorFactory.create_extractor("job_unknown", mock_http_client, config_with_policies)

def test_err_03_instantiation_failure(mock_http_client, config_with_policies):
    """[ERR-03] Extractor 생성자 내부에서 예외 발생 시 ExtractorError로 래핑"""
    # KISExtractor 생성자 호출 시 TypeError가 발생하도록 Mocking
    with patch("src.extractor.extractor_factory.KISExtractor") as mock_cls:
        mock_cls.side_effect = TypeError("Constructor Failed")
        
        with pytest.raises(ExtractorError, match="Factory Initialization Failed"):
            ExtractorFactory.create_extractor("job_kis", mock_http_client, config_with_policies)

# ========================================================================================
# 5. 의존성 격리 테스트 (Dependency Isolation)
# ========================================================================================

def test_di_01_isolation(config_with_policies):
    """[DI-01] HttpClient 등 외부 의존성 Mocking 상태에서 Factory 로직 독립 검증"""
    mock_client = MagicMock(spec=IHttpClient)
    
    result = ExtractorFactory.create_extractor("job_kis", mock_client, config_with_policies)
    
    assert result.http_client is mock_client
    assert result.config is config_with_policies