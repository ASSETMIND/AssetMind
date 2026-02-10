import jwt
import uuid
import pytest
import asyncio
import hashlib
from urllib.parse import urlencode
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

# 실제 프로젝트 경로에 맞게 임포트
from src.extractor.adapters.auth import KISAuthStrategy, UPBITAuthStrategy
from src.extractor.domain.exceptions import AuthError, NetworkError

# --- [Constants] 테스트용 상수 (보안 경고 방지를 위해 32바이트 이상 설정) ---
# HS256 알고리즘은 보안상 256비트(32바이트) 이상의 키 길이를 권장합니다.
TEST_UPBIT_SECRET = "test_secret_key_must_be_at_least_32_bytes_long_001"
TEST_UPBIT_WRONG_SECRET = "wrong_secret_key_must_be_at_least_32_bytes_long_999"

# --- [Mock Definitions] 테스트를 위한 가짜 객체 정의 ---
class MockSecretStr:
    def __init__(self, value: str):
        self._value = value
    def get_secret_value(self) -> str:
        return self._value

class MockKISConfig:
    """KIS 테스트를 위한 설정 Mock 객체"""
    def __init__(self, base_url="https://api.test.com", app_key="key", app_secret="secret"):
        self.kis = MagicMock()
        self.kis.base_url = base_url
        self.kis.app_key = MockSecretStr(app_key)
        self.kis.app_secret = MockSecretStr(app_secret)

class MockUpbitConfig:
    """UPBIT 테스트를 위한 설정 Mock 객체"""
    def __init__(self, base_url="https://api.upbit.com", api_key="u_key", secret_key=TEST_UPBIT_SECRET, missing_secret=False):
        self.upbit = MagicMock()
        self.upbit.base_url = base_url
        self.upbit.api_key = MockSecretStr(api_key)
        
        # [UPBIT-INIT-02] 테스트를 위해 secret_key 속성 자체를 누락시키는 옵션
        if not missing_secret:
            self.upbit.secret_key = MockSecretStr(secret_key)
        else:
            del self.upbit.secret_key

# --- [Fixtures] 테스트 환경 설정 ---

@pytest.fixture(autouse=True)
def mock_external_dependencies():
    """
    [핵심 수정] 
    @log_decorator가 실행될 때 LogManager가 전역 Config(AppConfig)를 
    참조하지 못하도록 LogManager.get_logger 메서드 자체를 Mocking합니다.
    이 픽스처는 autouse=True로 설정되어 모든 테스트에 자동 적용됩니다.
    """
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        mock_get_logger.return_value = MagicMock()
        yield

@pytest.fixture
def mock_http_client():
    client = MagicMock()
    client.post = AsyncMock()
    return client

@pytest.fixture
def kis_strategy(mock_http_client):
    """기본 설정이 완료된 AuthStrategy 인스턴스를 반환합니다."""
    config = MockKISConfig()
    return KISAuthStrategy(config)

@pytest.fixture
def upbit_strategy():
    """기본 설정이 완료된 UPBITAuthStrategy 인스턴스를 반환합니다."""
    config = MockUpbitConfig()
    return UPBITAuthStrategy(config)

@pytest.fixture
def valid_token_response():
    """표준적인 성공 응답 데이터"""
    expiry = (datetime.now() + timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "access_token": "test_access_token",
        "access_token_token_expired": expiry
    }

# ========================================================================================
# 1. KIS 초기화 테스트 (Initialization)
# ========================================================================================

def test_kis_init_01_valid_config():
    """[KIS-INIT-01] 유효한 설정으로 초기화 시 인스턴스 정상 생성"""
    # Given
    config = MockKISConfig(base_url="https://api.kis.com")
    
    # When
    strategy = KISAuthStrategy(config)
    
    # Then
    assert strategy.base_url == "https://api.kis.com"
    assert strategy._access_token is None

def test_kis_init_02_invalid_base_url():
    """[KIS-INIT-02] base_url이 비어있으면 ValueError 발생"""
    # Given
    config = MockKISConfig(base_url="")
    
    # When & Then
    with pytest.raises(ValueError, match="missing"):
        KISAuthStrategy(config)

def test_kis_init_03_secret_handling():
    """[KIS-INIT-03] SecretStr 타입이 내부적으로 평문으로 저장되는지 검증"""
    # Given
    config = MockKISConfig(app_key="secret_key_123")
    
    # When
    strategy = KISAuthStrategy(config)
    
    # Then
    assert strategy.app_key == "secret_key_123"

# ========================================================================================
# 2. KIS 토큰 수명주기 테스트 (Lifecycle)
# ========================================================================================

@pytest.mark.asyncio
async def test_kis_life_01_initial_fetch(kis_strategy, mock_http_client, valid_token_response):
    """[KIS-LIFE-01] 초기 구동 시 API 호출하여 토큰 발급"""
    # Given
    mock_http_client.post.return_value = valid_token_response
    
    # When
    token = await kis_strategy.get_token(mock_http_client)
    
    # Then
    assert token == "Bearer test_access_token"
    mock_http_client.post.assert_called_once()
    assert kis_strategy._access_token == "test_access_token"

@pytest.mark.asyncio
async def test_kis_life_02_valid_cache_hit(kis_strategy, mock_http_client):
    """[KIS-LIFE-02] 토큰 유효기간이 버퍼(10분)보다 많이 남았으면 캐시 반환 (API 호출 X)"""
    # Given
    kis_strategy._access_token = "cached_token"
    kis_strategy._expires_at = datetime.now() + timedelta(minutes=11)
    
    # When
    token = await kis_strategy.get_token(mock_http_client)
    
    # Then
    assert token == "Bearer cached_token"
    mock_http_client.post.assert_not_called()

@pytest.mark.asyncio
async def test_kis_life_03_lazy_refresh_buffer_entry(kis_strategy, mock_http_client, valid_token_response):
    """[KIS-LIFE-03] 토큰 유효기간이 9분 남음 (버퍼 10분 진입) -> 갱신 수행"""
    # Given
    kis_strategy._access_token = "old_token"
    kis_strategy._expires_at = datetime.now() + timedelta(minutes=9)
    mock_http_client.post.return_value = valid_token_response
    
    # When
    token = await kis_strategy.get_token(mock_http_client)
    
    # Then
    assert token == "Bearer test_access_token"
    mock_http_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_kis_life_04_token_expired(kis_strategy, mock_http_client, valid_token_response):
    """[KIS-LIFE-04] 이미 만료된 토큰 -> 갱신 수행"""
    # Given
    kis_strategy._access_token = "expired_token"
    kis_strategy._expires_at = datetime.now() - timedelta(minutes=1)
    mock_http_client.post.return_value = valid_token_response
    
    # When
    token = await kis_strategy.get_token(mock_http_client)
    
    # Then
    mock_http_client.post.assert_called_once()

# ========================================================================================
# 3. KIS 동시성 테스트 (Concurrency)
# ========================================================================================

@pytest.mark.asyncio
async def test_kis_conc_01_concurrency_locking(kis_strategy, mock_http_client, valid_token_response):
    """[KIS-CONC-01] 다수의 코루틴이 동시에 요청해도 API 호출은 1회만 발생 (Double-Checked Locking)"""
    # Given
    async def delayed_response(*args, **kwargs):
        await asyncio.sleep(0.1) 
        return valid_token_response
    
    mock_http_client.post.side_effect = delayed_response
    
    # When
    tasks = [kis_strategy.get_token(mock_http_client) for _ in range(5)]
    results = await asyncio.gather(*tasks)
    
    # Then
    assert all(token == "Bearer test_access_token" for token in results)
    assert mock_http_client.post.call_count == 1

# ========================================================================================
# 4. KIS API 응답 및 파싱 테스트 (API Interaction)
# ========================================================================================

@pytest.mark.asyncio
async def test_kis_api_01_parsing_normal(kis_strategy, mock_http_client):
    """[KIS-API-01] 응답 파싱 및 만료시간 설정 검증"""
    # Given
    target_time = datetime.now().replace(microsecond=0) + timedelta(hours=1)
    expiry_str = target_time.strftime("%Y-%m-%d %H:%M:%S")
    
    response = {
        "access_token": "new_token",
        "access_token_token_expired": expiry_str
    }
    mock_http_client.post.return_value = response
    
    # When
    await kis_strategy.get_token(mock_http_client)
    
    # Then
    assert kis_strategy._access_token == "new_token"
    assert kis_strategy._expires_at == target_time

@pytest.mark.asyncio
async def test_kis_api_02_missing_expiry_key(kis_strategy, mock_http_client):
    """[KIS-API-02] 만료시간 키 누락 시 기본값(12시간) 설정"""
    # Given
    mock_http_client.post.return_value = {"access_token": "token_no_expiry"}
    
    # When
    await kis_strategy.get_token(mock_http_client)
    
    # Then
    expected_expiry = datetime.now() + timedelta(hours=12)
    diff = abs((kis_strategy._expires_at - expected_expiry).total_seconds())
    assert diff < 5

@pytest.mark.asyncio
async def test_kis_api_03_missing_access_token(kis_strategy, mock_http_client):
    """[KIS-API-03] access_token 키 누락 시 AuthError 발생"""
    # Given
    mock_http_client.post.return_value = {"msg": "invalid response"}
    
    # When & Then
    with pytest.raises(AuthError, match="Missing access_token"):
        await kis_strategy.get_token(mock_http_client)

@pytest.mark.asyncio
async def test_kis_api_04_mcdc_invalid_date_format(kis_strategy, mock_http_client):
    """[KIS-API-04] [MC/DC] 만료시간 포맷 오류 시 ValueError Catch 후 기본값 적용"""
    # Given
    mock_http_client.post.return_value = {
        "access_token": "token",
        "access_token_token_expired": "Invalid-Date-Format"
    }
    
    # When
    await kis_strategy.get_token(mock_http_client)
    
    # Then
    expected_expiry = datetime.now() + timedelta(hours=12)
    diff = abs((kis_strategy._expires_at - expected_expiry).total_seconds())
    assert diff < 5

# ========================================================================================
# 5. KIS 에러 처리 테스트 (Error Handling)
# ========================================================================================

@pytest.mark.asyncio
async def test_kis_err_01_fail_fast_401(kis_strategy, mock_http_client):
    """[KIS-ERR-01] 401 Unauthorized 발생 시 재시도 없이 AuthError 발생 (Fail-Fast)"""
    # Given
    mock_http_client.post.side_effect = NetworkError("401 Unauthorized")
    
    # When & Then
    with pytest.raises(AuthError, match="Invalid Credentials"):
        await kis_strategy.get_token(mock_http_client)

@pytest.mark.asyncio
async def test_kis_err_02_fail_fast_403(kis_strategy, mock_http_client):
    """[KIS-ERR-02] 403 Forbidden 발생 시 재시도 없이 AuthError 발생 (Fail-Fast)"""
    # Given
    mock_http_client.post.side_effect = NetworkError("403 Forbidden")
    
    # When & Then
    with pytest.raises(AuthError, match="Invalid Credentials"):
        await kis_strategy.get_token(mock_http_client)

@pytest.mark.asyncio
async def test_kis_err_03_unknown_exception(kis_strategy, mock_http_client):
    """[KIS-ERR-03] 알 수 없는 예외 발생 시 AuthError로 래핑"""
    # Given
    mock_http_client.post.side_effect = KeyError("Unexpected Key")
    
    # When & Then
    with pytest.raises(AuthError, match="Error during token issuance"):
        await kis_strategy.get_token(mock_http_client)

@pytest.mark.asyncio
async def test_kis_err_04_token_none_logic(kis_strategy, mock_http_client):
    """[KIS-ERR-04] 로직 수행 후에도 토큰이 없는 경우 AuthError (Mocking으로 강제)"""
    # Given
    # 내부 _issue_token이 호출되지만 아무 일도 안 하도록 Mocking
    with patch.object(kis_strategy, '_issue_token', new=AsyncMock()) as mock_issue:
        # 갱신 조건 강제 만족
        kis_strategy._access_token = None
        
        # When & Then
        with pytest.raises(AuthError, match="Failed to retrieve access token"):
            await kis_strategy.get_token(mock_http_client)

@pytest.mark.asyncio
async def test_kis_err_05_retry_logic_500(kis_strategy, mock_http_client):
    """[KIS-ERR-05] 500 에러 발생 시 NetworkError가 그대로 전파됨 (Retry 데코레이터 트리거용)"""
    # Given
    mock_http_client.post.side_effect = NetworkError("500 Internal Server Error")
    
    # When & Then
    with pytest.raises(NetworkError, match="500"):
        await kis_strategy._issue_token(mock_http_client)

# ========================================================================================
# 6. UPBIT 초기화 테스트 (Initialization)
# ========================================================================================

def test_upbit_init_01_invalid_base_url():
    """[UPBIT-INIT-01] base_url이 비어있으면 ValueError 발생"""
    # Given
    config = MockUpbitConfig(base_url="")
    
    # When & Then
    with pytest.raises(ValueError, match="base_url"):
        UPBITAuthStrategy(config)

def test_upbit_init_02_missing_secret_key_attribute():
    """[UPBIT-INIT-02] 설정 객체에 secret_key 속성이 없으면 ValueError 발생"""
    # Given
    config = MockUpbitConfig(missing_secret=True)
    
    # When & Then
    with pytest.raises(ValueError, match="secret_key"):
        UPBITAuthStrategy(config)

# ========================================================================================
# 7. UPBIT 토큰 수명주기 및 데이터 무결성 (Lifecycle & Data Integrity)
# ========================================================================================

@pytest.mark.asyncio
async def test_upbit_life_01_basic_token_structure(upbit_strategy, mock_http_client):
    """[UPBIT-LIFE-01] 인자 없이 호출 시 기본 토큰 구조(Access Key, Nonce) 검증"""
    # When
    token_str = await upbit_strategy.get_token(mock_http_client)
    
    # Then
    assert token_str.startswith("Bearer ")
    raw_token = token_str.split(" ")[1]
    
    # JWT Decode (서명 검증 포함 - TEST_UPBIT_SECRET 사용)
    payload = jwt.decode(raw_token, TEST_UPBIT_SECRET, algorithms=["HS256"])
    
    assert payload["access_key"] == "u_key"
    assert "nonce" in payload
    assert "query_hash" not in payload  # 쿼리가 없으므로 해시도 없어야 함

@pytest.mark.asyncio
async def test_upbit_life_02_query_hash_integrity(upbit_strategy, mock_http_client):
    """[UPBIT-LIFE-02] 쿼리 파라미터 전달 시 SHA512 해시 무결성 검증"""
    # Given
    params = {"market": "KRW-BTC", "count": 1}
    
    # 수동 해시 계산 (검증용 Oracle)
    query_string = urlencode(params).encode("utf-8")
    expected_hash = hashlib.sha512(query_string).hexdigest()
    
    # When
    token_str = await upbit_strategy.get_token(mock_http_client, query_params=params)
    
    # Then
    raw_token = token_str.split(" ")[1]
    payload = jwt.decode(raw_token, TEST_UPBIT_SECRET, algorithms=["HS256"])
    
    assert payload.get("query_hash") == expected_hash
    assert payload.get("query_hash_alg") == "SHA512"

@pytest.mark.asyncio
async def test_upbit_data_01_empty_query_params(upbit_strategy, mock_http_client):
    """[UPBIT-DATA-01] 빈 딕셔너리 쿼리 파라미터는 None과 동일하게 처리(해시 미생성)"""
    # Given
    empty_params = {}
    
    # When
    token_str = await upbit_strategy.get_token(mock_http_client, query_params=empty_params)
    
    # Then
    raw_token = token_str.split(" ")[1]
    payload = jwt.decode(raw_token, TEST_UPBIT_SECRET, algorithms=["HS256"])
    
    assert "query_hash" not in payload

@pytest.mark.asyncio
async def test_upbit_compat_01_bytes_token_handling(upbit_strategy, mock_http_client):
    """[UPBIT-COMPAT-01] PyJWT 구버전 호환성: jwt.encode가 bytes를 반환할 경우 str로 디코딩"""
    # Given
    # jwt.encode가 bytes 타입의 토큰을 반환하도록 Mocking
    with patch("jwt.encode", return_value=b"bytes_token_mock"):
        
        # When
        token_str = await upbit_strategy.get_token(mock_http_client)
        
        # Then
        # 내부 로직에서 .decode("utf-8")이 호출되어 문자열로 변환되었는지 확인
        assert token_str == "Bearer bytes_token_mock"

# ========================================================================================
# 8. UPBIT 보안 로직 검증 (Security Logic)
# ========================================================================================

@pytest.mark.asyncio
async def test_upbit_logic_01_algorithm_check(upbit_strategy, mock_http_client):
    """[UPBIT-LOGIC-01] 생성된 토큰의 헤더가 HS256 알고리즘을 사용하는지 확인"""
    # When
    token_str = await upbit_strategy.get_token(mock_http_client)
    raw_token = token_str.split(" ")[1]
    
    # Then
    header = jwt.get_unverified_header(raw_token)
    assert header["alg"] == "HS256"

@pytest.mark.asyncio
async def test_upbit_logic_02_invalid_signature(upbit_strategy, mock_http_client):
    """[UPBIT-LOGIC-02] 잘못된 Secret Key로 검증 시 서명 에러 발생 (위조 방지)"""
    # Given
    token_str = await upbit_strategy.get_token(mock_http_client)
    raw_token = token_str.split(" ")[1]
    
    # When & Then
    # 올바르지 않은 키도 길이 조건을 만족해야 경고 없이 InvalidSignatureError 검증 가능
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(raw_token, TEST_UPBIT_WRONG_SECRET, algorithms=["HS256"])

@pytest.mark.asyncio
async def test_upbit_sec_01_nonce_uniqueness(upbit_strategy, mock_http_client):
    """[UPBIT-SEC-01] 연속 호출 시 Nonce가 매번 달라지는지 확인 (Replay Attack 방지)"""
    # When
    token1 = await upbit_strategy.get_token(mock_http_client)
    token2 = await upbit_strategy.get_token(mock_http_client)
    
    # Then
    payload1 = jwt.decode(token1.split(" ")[1], TEST_UPBIT_SECRET, algorithms=["HS256"])
    payload2 = jwt.decode(token2.split(" ")[1], TEST_UPBIT_SECRET, algorithms=["HS256"])
    
    assert token1 != token2
    assert payload1["nonce"] != payload2["nonce"]