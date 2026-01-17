import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from src.extractor.adapters.auth import KISAuthStrategy
from src.common.config import AppConfig
from src.extractor.domain.exceptions import AuthError, NetworkError

# 테스트 실행을 위한 모킹 타겟 경로
TARGET_MODULE = "src.extractor.adapters.auth"

# --------------------------------------------------------------------------
# 1. Mock Objects & Fixtures (테스트 환경 구성)
# --------------------------------------------------------------------------

@pytest.fixture
def valid_config():
    """
    [AppConfig Mocking]
    KISAuthStrategy 초기화에 필요한 설정 객체를 모방합니다.
    필수값(Key, Secret, URL)이 모두 포함된 정상 상태입니다.
    """
    config = MagicMock()
    config.kis_app_key = "dummy_key"
    config.kis_app_secret = "dummy_secret"
    config.kis_base_url = "https://api.test.com"
    return config

@pytest.fixture
def mock_http_client():
    """
    [IHttpClient Mocking]
    외부 네트워크 요청을 수행하는 HTTP 클라이언트를 모방합니다.
    post 메서드는 비동기(awaitable)이므로 AsyncMock을 사용합니다.
    """
    client = MagicMock()
    client.post = AsyncMock()
    return client

@pytest.fixture
def strategy(valid_config):
    """
    [Target Under Test: KISAuthStrategy]
    테스트 대상 인스턴스를 생성합니다.
    """
    return KISAuthStrategy(valid_config)

# --------------------------------------------------------------------------
# 2. Test Cases (테스트 시나리오)
# --------------------------------------------------------------------------

class TestKISAuthStrategy:
    """
    KISAuthStrategy 명세서(TC-001 ~ TC-012) 완전 구현
    """

    # ==========================================
    # Category: Unit (Happy Path & Boundary)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc001_cold_start(self, strategy, mock_http_client):
        """[TC-001] 캐시가 비어있는 초기 상태에서 API를 호출하여 토큰을 발급받는다."""
        # Given
        expected_token = "new_tok"
        mock_http_client.post.return_value = {
            "access_token": expected_token,
            "access_token_token_expired": "2024-01-01 12:00:00"
        }

        # When
        token_str = await strategy.get_token(mock_http_client)

        # Then
        assert token_str == f"Bearer {expected_token}"
        mock_http_client.post.assert_called_once()
        assert strategy._access_token == expected_token

    @pytest.mark.asyncio
    async def test_tc002_cache_hit(self, strategy, mock_http_client):
        """[TC-002] 유효 기간이 넉넉하면(Buffer 10분 초과) API 호출 없이 기존 토큰을 반환한다."""
        # Given: 만료 15분 남음 (Buffer 10분보다 큼)
        strategy._access_token = "existing_tok"
        strategy._expires_at = datetime.now() + timedelta(minutes=15)

        # When
        token_str = await strategy.get_token(mock_http_client)

        # Then
        assert token_str == "Bearer existing_tok"
        mock_http_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_tc003_lazy_refresh_warning(self, strategy, mock_http_client):
        """[TC-003] 토큰이 존재하나 만료 임박(5분 남음) 시 갱신을 수행한다."""
        # Given: 만료 5분 남음 (Buffer 10분 진입)
        strategy._access_token = "old_tok"
        strategy._expires_at = datetime.now() + timedelta(minutes=5)
        
        mock_http_client.post.return_value = {
            "access_token": "refreshed_tok",
            "access_token_token_expired": "2099-01-01 12:00:00"
        }

        # When
        token_str = await strategy.get_token(mock_http_client)

        # Then
        assert token_str == "Bearer refreshed_tok"
        mock_http_client.post.assert_called_once()

    def test_tc004_config_validation(self):
        """[TC-004] 필수 설정값이 누락되면 초기화 시 ValueError가 발생한다."""
        # Given
        invalid_config = MagicMock()
        invalid_config.kis_app_key = "" # Key 누락

        # When & Then
        with pytest.raises(ValueError, match="KIS API configuration missing"):
            KISAuthStrategy(invalid_config)

    @pytest.mark.asyncio
    async def test_tc005_boundary_safe(self, strategy, mock_http_client):
        """[TC-005] 만료 시간이 정확히 10분 1초 남았을 때(Safe)는 갱신하지 않는다."""
        # Given: Time Freeze & Expire Set
        fixed_now = datetime(2024, 1, 1, 12, 0, 0)
        expires_at = fixed_now + timedelta(minutes=10, seconds=1)
        
        strategy._access_token = "safe_tok"
        strategy._expires_at = expires_at

        # When
        with patch(f"{TARGET_MODULE}.datetime") as mock_date:
            mock_date.now.return_value = fixed_now
            mock_date.strptime.side_effect = datetime.strptime 
            await strategy.get_token(mock_http_client)

        # Then
        mock_http_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_tc006_boundary_unsafe(self, strategy, mock_http_client):
        """[TC-006] 만료 시간이 정확히 9분 59초 남았을 때(Unsafe)는 갱신을 수행한다."""
        # Given
        fixed_now = datetime(2024, 1, 1, 12, 0, 0)
        expires_at = fixed_now + timedelta(minutes=10, seconds=-1) # 9분 59초
        
        strategy._access_token = "unsafe_tok"
        strategy._expires_at = expires_at
        
        mock_http_client.post.return_value = {
            "access_token": "new_tok",
            "access_token_token_expired": "2099-01-01 12:00:00"
        }

        # When
        with patch(f"{TARGET_MODULE}.datetime") as mock_date:
            mock_date.now.return_value = fixed_now
            mock_date.strptime.side_effect = datetime.strptime
            await strategy.get_token(mock_http_client)

        # Then
        mock_http_client.post.assert_called_once()

    # ==========================================
    # Category: Exception & Logic
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc007_missing_key(self, strategy, mock_http_client):
        """[TC-007] API 응답에 access_token 필드가 없으면 AuthError가 발생한다."""
        # Given
        mock_http_client.post.return_value = {"msg_code": "error", "msg": "fail"}

        # When & Then
        with pytest.raises(AuthError, match="Invalid token response"):
            await strategy.get_token(mock_http_client)

    @pytest.mark.asyncio
    async def test_tc008_malformed_date(self, strategy, mock_http_client):
        """[TC-008] 만료시간 포맷이 비표준이면 에러 없이 12시간 Fallback을 적용한다."""
        # Given
        mock_http_client.post.return_value = {
            "access_token": "tok", 
            "access_token_token_expired": "invalid-date"
        }
        fixed_now = datetime(2024, 1, 1, 12, 0, 0)

        # When
        with patch(f"{TARGET_MODULE}.datetime") as mock_date:
            mock_date.now.return_value = fixed_now
            mock_date.strptime.side_effect = datetime.strptime
            await strategy.get_token(mock_http_client)

        # Then
        expected_expiry = fixed_now + timedelta(hours=12)
        assert strategy._expires_at == expected_expiry
        assert strategy._access_token == "tok"

    @pytest.mark.asyncio
    async def test_tc009_missing_date_field(self, strategy, mock_http_client):
        """[TC-009] 만료시간 필드 자체가 없으면 에러 없이 12시간 Fallback을 적용한다."""
        # Given
        mock_http_client.post.return_value = {"access_token": "tok"}
        fixed_now = datetime(2024, 1, 1, 12, 0, 0)

        # When
        with patch(f"{TARGET_MODULE}.datetime") as mock_date:
            mock_date.now.return_value = fixed_now
            mock_date.strptime.side_effect = datetime.strptime
            await strategy.get_token(mock_http_client)

        # Then
        expected_expiry = fixed_now + timedelta(hours=12)
        assert strategy._expires_at == expected_expiry

    @pytest.mark.asyncio
    async def test_tc010_network_error(self, strategy, mock_http_client):
        """[TC-010] 네트워크 연결 실패 시 AuthError로 래핑하여 발생시킨다."""
        # Given
        mock_http_client.post.side_effect = NetworkError("Connection refused")

        # When & Then
        with pytest.raises(AuthError, match="Failed to connect"):
            await strategy.get_token(mock_http_client)

    @pytest.mark.asyncio
    async def test_tc011_silent_logic_failure(self, strategy, mock_http_client):
        """[TC-011] 로직 오류로 토큰 갱신 후에도 토큰이 None이면 AuthError를 발생시킨다."""
        # Given: _issue_token 메서드가 호출되어도 아무것도 하지 않도록(Silent Fail) 조작
        with patch.object(strategy, '_issue_token', new=AsyncMock()):
            
            # When & Then
            with pytest.raises(AuthError, match="Failed to retrieve access token"):
                await strategy.get_token(mock_http_client)

    @pytest.mark.asyncio
    async def test_tc012_expired_token(self, strategy, mock_http_client):
        """[TC-012] 토큰이 완전히 만료된(과거 시간) 경우 갱신을 수행한다."""
        # Given: 만료 시간이 현재보다 1분 전
        strategy._access_token = "expired_tok"
        strategy._expires_at = datetime.now() - timedelta(minutes=1)
        
        mock_http_client.post.return_value = {
            "access_token": "new_tok_2",
            "access_token_token_expired": "2099-01-01 12:00:00"
        }

        # When
        token_str = await strategy.get_token(mock_http_client)

        # Then
        assert token_str == "Bearer new_tok_2"
        mock_http_client.post.assert_called_once()