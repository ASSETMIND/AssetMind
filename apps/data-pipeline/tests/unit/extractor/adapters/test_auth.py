import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

# 실제 프로젝트 경로에 맞게 임포트
from src.extractor.adapters.auth import KISAuthStrategy
from src.extractor.domain.exceptions import AuthError, NetworkError

# --- [Mock Definitions] 테스트를 위한 가짜 객체 정의 ---
class MockSecretStr:
    def __init__(self, value: str):
        self._value = value
    def get_secret_value(self) -> str:
        return self._value

class MockConfig:
    def __init__(self, base_url="https://api.test.com", app_key="key", app_secret="secret"):
        self.kis = MagicMock()
        self.kis.base_url = base_url
        self.kis.app_key = MockSecretStr(app_key)
        self.kis.app_secret = MockSecretStr(app_secret)

# --- [Fixtures] 테스트 환경 설정 ---

@pytest.fixture(autouse=True)
def mock_external_dependencies():
    """
    [핵심 수정] 
    @log_decorator가 실행될 때 LogManager가 전역 Config(AppConfig)를 
    참조하지 못하도록 LogManager.get_logger 메서드 자체를 Mocking합니다.
    이 픽스처는 autouse=True로 설정되어 모든 테스트에 자동 적용됩니다.
    """
    # src.common.log 모듈 경로에 유의하여 LogManager를 패치합니다.
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        # 로거가 호출되면 아무 동작도 하지 않는 MagicMock을 반환
        mock_get_logger.return_value = MagicMock()
        yield

@pytest.fixture
def mock_http_client():
    client = MagicMock()
    client.post = AsyncMock()
    return client

@pytest.fixture
def auth_strategy(mock_http_client):
    """기본 설정이 완료된 AuthStrategy 인스턴스를 반환합니다."""
    config = MockConfig()
    return KISAuthStrategy(config)

@pytest.fixture
def valid_token_response():
    """표준적인 성공 응답 데이터"""
    expiry = (datetime.now() + timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "access_token": "test_access_token",
        "access_token_token_expired": expiry
    }

# ========================================================================================
# 1. 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_valid_config():
    """[INIT-01] 유효한 설정으로 초기화 시 인스턴스 정상 생성"""
    # Given
    config = MockConfig(base_url="https://api.kis.com")
    
    # When
    strategy = KISAuthStrategy(config)
    
    # Then
    assert strategy.base_url == "https://api.kis.com"
    assert strategy._access_token is None

def test_init_02_invalid_base_url():
    """[INIT-02] base_url이 비어있으면 ValueError 발생"""
    # Given
    config = MockConfig(base_url="")
    
    # When & Then
    with pytest.raises(ValueError, match="missing"):
        KISAuthStrategy(config)

def test_init_03_secret_handling():
    """[INIT-03] SecretStr 타입이 내부적으로 평문으로 저장되는지 검증"""
    # Given
    config = MockConfig(app_key="secret_key_123")
    
    # When
    strategy = KISAuthStrategy(config)
    
    # Then
    assert strategy.app_key == "secret_key_123"

# ========================================================================================
# 2. 토큰 수명주기 테스트 (Lifecycle)
# ========================================================================================

@pytest.mark.asyncio
async def test_life_01_initial_fetch(auth_strategy, mock_http_client, valid_token_response):
    """[LIFE-01] 초기 구동 시 API 호출하여 토큰 발급"""
    # Given
    mock_http_client.post.return_value = valid_token_response
    
    # When
    token = await auth_strategy.get_token(mock_http_client)
    
    # Then
    assert token == "Bearer test_access_token"
    mock_http_client.post.assert_called_once()
    assert auth_strategy._access_token == "test_access_token"

@pytest.mark.asyncio
async def test_life_02_valid_cache_hit(auth_strategy, mock_http_client):
    """[LIFE-02] 토큰 유효기간이 버퍼(10분)보다 많이 남았으면 캐시 반환 (API 호출 X)"""
    # Given
    auth_strategy._access_token = "cached_token"
    auth_strategy._expires_at = datetime.now() + timedelta(minutes=11)
    
    # When
    token = await auth_strategy.get_token(mock_http_client)
    
    # Then
    assert token == "Bearer cached_token"
    mock_http_client.post.assert_not_called()

@pytest.mark.asyncio
async def test_life_03_lazy_refresh_buffer_entry(auth_strategy, mock_http_client, valid_token_response):
    """[LIFE-03] 토큰 유효기간이 9분 남음 (버퍼 10분 진입) -> 갱신 수행"""
    # Given
    auth_strategy._access_token = "old_token"
    auth_strategy._expires_at = datetime.now() + timedelta(minutes=9)
    mock_http_client.post.return_value = valid_token_response
    
    # When
    token = await auth_strategy.get_token(mock_http_client)
    
    # Then
    assert token == "Bearer test_access_token"
    mock_http_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_life_04_token_expired(auth_strategy, mock_http_client, valid_token_response):
    """[LIFE-04] 이미 만료된 토큰 -> 갱신 수행"""
    # Given
    auth_strategy._access_token = "expired_token"
    auth_strategy._expires_at = datetime.now() - timedelta(minutes=1)
    mock_http_client.post.return_value = valid_token_response
    
    # When
    token = await auth_strategy.get_token(mock_http_client)
    
    # Then
    mock_http_client.post.assert_called_once()

# ========================================================================================
# 3. 동시성 테스트 (Concurrency)
# ========================================================================================

@pytest.mark.asyncio
async def test_conc_01_concurrency_locking(auth_strategy, mock_http_client, valid_token_response):
    """[CONC-01] 다수의 코루틴이 동시에 요청해도 API 호출은 1회만 발생 (Double-Checked Locking)"""
    # Given
    async def delayed_response(*args, **kwargs):
        await asyncio.sleep(0.1) 
        return valid_token_response
    
    mock_http_client.post.side_effect = delayed_response
    
    # When
    tasks = [auth_strategy.get_token(mock_http_client) for _ in range(5)]
    results = await asyncio.gather(*tasks)
    
    # Then
    assert all(token == "Bearer test_access_token" for token in results)
    assert mock_http_client.post.call_count == 1

# ========================================================================================
# 4. API 응답 및 파싱 테스트 (API Interaction)
# ========================================================================================

@pytest.mark.asyncio
async def test_api_01_parsing_normal(auth_strategy, mock_http_client):
    """[API-01] 응답 파싱 및 만료시간 설정 검증"""
    # Given
    target_time = datetime.now().replace(microsecond=0) + timedelta(hours=1)
    expiry_str = target_time.strftime("%Y-%m-%d %H:%M:%S")
    
    response = {
        "access_token": "new_token",
        "access_token_token_expired": expiry_str
    }
    mock_http_client.post.return_value = response
    
    # When
    await auth_strategy.get_token(mock_http_client)
    
    # Then
    assert auth_strategy._access_token == "new_token"
    assert auth_strategy._expires_at == target_time

@pytest.mark.asyncio
async def test_api_02_missing_expiry_key(auth_strategy, mock_http_client):
    """[API-02] 만료시간 키 누락 시 기본값(12시간) 설정"""
    # Given
    mock_http_client.post.return_value = {"access_token": "token_no_expiry"}
    
    # When
    await auth_strategy.get_token(mock_http_client)
    
    # Then
    expected_expiry = datetime.now() + timedelta(hours=12)
    diff = abs((auth_strategy._expires_at - expected_expiry).total_seconds())
    assert diff < 5

@pytest.mark.asyncio
async def test_api_03_missing_access_token(auth_strategy, mock_http_client):
    """[API-03] access_token 키 누락 시 AuthError 발생"""
    # Given
    mock_http_client.post.return_value = {"msg": "invalid response"}
    
    # When & Then
    with pytest.raises(AuthError, match="Missing access_token"):
        await auth_strategy.get_token(mock_http_client)

@pytest.mark.asyncio
async def test_api_04_mcdc_invalid_date_format(auth_strategy, mock_http_client):
    """[API-04] [MC/DC] 만료시간 포맷 오류 시 ValueError Catch 후 기본값 적용"""
    # Given
    mock_http_client.post.return_value = {
        "access_token": "token",
        "access_token_token_expired": "Invalid-Date-Format"
    }
    
    # When
    await auth_strategy.get_token(mock_http_client)
    
    # Then
    expected_expiry = datetime.now() + timedelta(hours=12)
    diff = abs((auth_strategy._expires_at - expected_expiry).total_seconds())
    assert diff < 5

# ========================================================================================
# 5. 에러 처리 테스트 (Error Handling)
# ========================================================================================

@pytest.mark.asyncio
async def test_err_01_fail_fast_401(auth_strategy, mock_http_client):
    """[ERR-01] 401 Unauthorized 발생 시 재시도 없이 AuthError 발생 (Fail-Fast)"""
    # Given
    mock_http_client.post.side_effect = NetworkError("401 Unauthorized")
    
    # When & Then
    with pytest.raises(AuthError, match="Invalid Credentials"):
        await auth_strategy.get_token(mock_http_client)

@pytest.mark.asyncio
async def test_err_02_fail_fast_403(auth_strategy, mock_http_client):
    """[ERR-02] 403 Forbidden 발생 시 재시도 없이 AuthError 발생 (Fail-Fast)"""
    # Given
    mock_http_client.post.side_effect = NetworkError("403 Forbidden")
    
    # When & Then
    with pytest.raises(AuthError, match="Invalid Credentials"):
        await auth_strategy.get_token(mock_http_client)

@pytest.mark.asyncio
async def test_err_03_unknown_exception(auth_strategy, mock_http_client):
    """[ERR-03] 알 수 없는 예외 발생 시 AuthError로 래핑"""
    # Given
    mock_http_client.post.side_effect = KeyError("Unexpected Key")
    
    # When & Then
    with pytest.raises(AuthError, match="Error during token issuance"):
        await auth_strategy.get_token(mock_http_client)

@pytest.mark.asyncio
async def test_err_04_token_none_logic(auth_strategy, mock_http_client):
    """[ERR-04] 로직 수행 후에도 토큰이 없는 경우 AuthError (Mocking으로 강제)"""
    # Given
    # 내부 _issue_token이 호출되지만 아무 일도 안 하도록 Mocking
    with patch.object(auth_strategy, '_issue_token', new=AsyncMock()) as mock_issue:
        # 갱신 조건 강제 만족
        auth_strategy._access_token = None
        
        # When & Then
        with pytest.raises(AuthError, match="Failed to retrieve access token"):
            await auth_strategy.get_token(mock_http_client)

@pytest.mark.asyncio
async def test_err_05_retry_logic_500(auth_strategy, mock_http_client):
    """[ERR-05] 500 에러 발생 시 NetworkError가 그대로 전파됨 (Retry 데코레이터 트리거용)"""
    # Given
    mock_http_client.post.side_effect = NetworkError("500 Internal Server Error")
    
    # When & Then
    # 여기서는 데코레이터가 Mocking된 상태일 수 있으나(로깅만 Mocking함), 
    # _issue_token 내부 로직이 500 에러를 catch하지 않고 raise하는지를 검증함.
    with pytest.raises(NetworkError, match="500"):
        await auth_strategy._issue_token(mock_http_client)