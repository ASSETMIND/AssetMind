"""
KIS API Authentication Strategy Module

이 모듈은 한국투자증권(KIS) API 사용을 위한 OAuth2 인증 토큰의 수명 주기를 관리합니다.
디스크 I/O 없이 메모리 내에서 상태를 관리하며, 만료 시간이 임박했을 때 자동으로 
토큰을 갱신하는 'Lazy Refresh' 전략을 사용합니다.

데이터 흐름 (Data Flow):
Client Request -> KISAuthStrategy.get_token() 
               -> Check In-Memory Cache (Valid?) 
               -> [If Invalid/Expired] -> Acquire Lock -> Double Check -> Decorator(Retry) -> POST KIS Auth Server 
               -> Update Memory State -> Return Access Token

주요 기능:
- OAuth2 Access Token 발급 및 In-Memory Caching
- Double-checked Locking 패턴을 이용한 Thread-Safe(Async-Safe) 토큰 갱신
- Fail-Fast 전략: 401/403 인증 에러 시 불필요한 재시도 방지

Trade-off:
- In-Memory Caching vs Redis:
    - 장점: 외부 의존성(Redis 등) 없이 구현이 간단하며, I/O Latency가 없음.
    - 단점: 애플리케이션 재시작 시 토큰이 소실되어 재발급 요청이 발생함.
    - 근거: 트레이딩 시스템 특성상 장기 실행 프로세스(Daemon)이므로 초기 1회 비용은 무시 가능함.
- Lazy Refresh vs Background Loop:
    - 장점: 별도의 백그라운드 태스크 관리 복잡성을 제거.
    - 단점: 토큰 만료 직후 첫 요청에 발급 지연(Latency) 발생.
    - 근거: Safety Buffer(10분)를 두어 실질적인 요청 지연을 최소화함.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from ..domain.interfaces import IAuthStrategy, IHttpClient
from ..domain.exceptions import AuthError, NetworkError
from ...common.config import AppConfig
from ...common.decorators import log_decorator, retry

# --- Constants & Configuration ---
TOKEN_EXPIRATION_BUFFER_MINUTES = 10
DEFAULT_TOKEN_DURATION_HOURS = 12
KIS_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
CONTENT_TYPE_JSON = "application/json"
GRANT_TYPE_CLIENT_CREDENTIALS = "client_credentials"


class KISAuthStrategy(IAuthStrategy):
    """한국투자증권(KIS) API 인증 전략 구현체.

    Attributes:
        app_key (str): KIS API App Key (평문).
        app_secret (str): KIS API App Secret (평문).
        base_url (str): API Base URL.
        _lock (asyncio.Lock): 토큰 갱신 경합 조건(Race Condition) 방지를 위한 락.
        _access_token (Optional[str]): 현재 유효한 Access Token.
        _expires_at (Optional[datetime]): 토큰 만료 예정 시각.
    """

    def __init__(self, config: AppConfig) -> None:
        """KISAuthStrategy 인스턴스를 초기화합니다.

        Args:
            config (AppConfig): 애플리케이션 전역 설정 객체.

        Raises:
            ValueError: 필수 설정(base_url)이 누락된 경우.
        """
        # Rationale: AppConfig의 계층 구조(config.kis)에 접근하여 설정 값을 로드함.
        if not config.kis.base_url:
            raise ValueError("KIS API configuration missing: 'base_url' is empty.")

        # Rationale: SecretStr 타입인 키를 .get_secret_value()로 복호화하여 메모리에 저장.
        # HTTP 헤더에는 평문이 들어가야 하기 때문임.
        self.app_key: str = config.kis.app_key.get_secret_value()
        self.app_secret: str = config.kis.app_secret.get_secret_value()
        self.base_url: str = config.kis.base_url

        self._lock = asyncio.Lock()
        self._access_token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
        
        self._logger = logging.getLogger(self.__class__.__name__)

    async def get_token(self, http_client: IHttpClient) -> str:
        """유효한 Bearer Access Token을 반환합니다.

        만료 시간이 임박했거나 토큰이 없는 경우, 동기화된(Locked) 상태에서 
        토큰을 갱신합니다.

        Args:
            http_client (IHttpClient): 토큰 발급 요청을 수행할 HTTP 클라이언트.

        Returns:
            str: "Bearer {access_token}" 형태의 인증 문자열.

        Raises:
            AuthError: 토큰 발급 실패 시.
        """
        # 1차 검사 (Lock-free): 성능을 위해 락 없이 먼저 확인
        if self._should_refresh():
            # Rationale: 여러 비동기 요청이 동시에 만료를 감지했을 때, 
            # 한 번만 갱신 요청을 보내기 위해 Async Lock 사용.
            async with self._lock:
                # 2차 검사 (Double-checked locking): 락 획득 대기 중에 다른 코루틴이 이미 갱신했을 수 있음.
                if self._should_refresh():
                    self._logger.info("Access token is missing or expired. Initiating refresh.")
                    await self._issue_token(http_client)
        
        if not self._access_token:
            self._logger.error("Token refresh logic failed silently.")
            raise AuthError("Failed to retrieve access token.")

        return f"Bearer {self._access_token}"

    def _should_refresh(self) -> bool:
        """토큰 갱신 필요 여부를 판단합니다.

        Returns:
            bool: 갱신이 필요하면 True, 아니면 False.
        """
        if not self._access_token or not self._expires_at:
            return True
        
        # Rationale: 네트워크 지연 등을 고려하여 만료 10분 전(Safety Buffer)에 미리 갱신함.
        threshold_time = datetime.now() + timedelta(minutes=TOKEN_EXPIRATION_BUFFER_MINUTES)
        if threshold_time > self._expires_at:
            self._logger.debug("Token expiring soon. Refresh needed.")
            return True
            
        return False

    @log_decorator(logger_name="KISAuth", suppress_error=False)
    @retry(max_retries=3, base_delay=1.0, exceptions=(NetworkError,))
    async def _issue_token(self, http_client: IHttpClient) -> None:
        """KIS API를 호출하여 새로운 토큰을 발급받습니다.

        주의:
            401/403 등 인증 관련 에러는 설정 문제일 가능성이 높으므로 
            재시도(Retry) 하지 않고 즉시 실패 처리합니다 (Fail-Fast).

        Args:
            http_client (IHttpClient): HTTP 요청 클라이언트.

        Raises:
            AuthError: API 응답 에러(4xx) 또는 재시도 후에도 실패 시(5xx).
        """
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": CONTENT_TYPE_JSON}
        body = {
            "grant_type": GRANT_TYPE_CLIENT_CREDENTIALS,
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            # Rationale: http_client.post는 4xx/5xx 에러 시 NetworkError를 발생시킴.
            # 이 NetworkError를 아래 except 블록에서 잡아 분기 처리함.
            response: Dict[str, Any] = await http_client.post(url, headers=headers, data=body)
            
            self._validate_response(response)
            self._update_state(response)

        except NetworkError as e:
            # [Fail-Fast Logic]
            # 403(Forbidden)이나 401(Unauthorized)는 재시도해도 해결되지 않는 
            # 영구적인 설정(Key/Secret) 오류이므로 즉시 중단해야 함.
            error_msg = str(e)
            if "403" in error_msg or "401" in error_msg:
                self._logger.error(f"Permanent Auth Failure (No Retry): {error_msg}")
                # AuthError를 발생시키면 @retry 데코레이터의 exceptions=(NetworkError,)에 
                # 포함되지 않으므로 재시도 루프를 탈출함.
                raise AuthError(f"Invalid Credentials: {error_msg}") from e
            
            # 500번대 에러나 타임아웃은 일시적 장애일 수 있으므로 
            # NetworkError를 그대로 두어 @retry 데코레이터가 재시도를 수행하게 함.
            raise e

        except Exception as e:
            # Rationale: 그 외 예상치 못한 에러는 구체적인 메시지와 함께 래핑하여 전파.
            raise AuthError(f"Error during token issuance: {str(e)}") from e

    def _validate_response(self, response: Dict[str, Any]) -> None:
        """API 응답 유효성을 검증합니다.

        Args:
            response (Dict[str, Any]): API 응답 데이터.

        Raises:
            AuthError: access_token 필드가 없는 경우.
        """
        if "access_token" not in response:
            raise AuthError("Invalid token response: Missing access_token")

    def _update_state(self, response: Dict[str, Any]) -> None:
        """응답 데이터를 파싱하여 내부 상태(토큰, 만료시간)를 갱신합니다.

        Args:
            response (Dict[str, Any]): 검증된 API 응답 데이터.
        """
        self._access_token = response["access_token"]
        expired_str = response.get("access_token_token_expired")
        
        if expired_str:
            try:
                self._expires_at = datetime.strptime(expired_str, KIS_DATE_FORMAT)
            except ValueError:
                self._logger.warning("Failed to parse expiration date. Using fallback.")
                self._expires_at = datetime.now() + timedelta(hours=DEFAULT_TOKEN_DURATION_HOURS)
        else:
            # 만료 시간이 응답에 없는 경우, 안전하게 Fallback 설정
            self._expires_at = datetime.now() + timedelta(hours=DEFAULT_TOKEN_DURATION_HOURS)