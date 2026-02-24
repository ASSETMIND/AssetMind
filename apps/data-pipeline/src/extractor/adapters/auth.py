"""
API 인증 전략 모듈 (API Authentication Strategy Module)

외부 API(KIS, UPBIT 등) 사용을 위한 인증 토큰의 발급, 갱신, 서명(Signing) 수명 주기를 관리합니다.
API 제공자의 인증 방식(OAuth2 vs JWT)에 따라 서로 다른 전략 패턴을 구현하여,
인프라 계층(Adapter)이 비즈니스 로직과 무관하게 인증을 처리할 수 있도록 돕습니다.

데이터 흐름 (Data Flow):
1. KIS (Stateful):
   Client -> Get Token -> Check Cache -> (If Expired) -> Http Post -> Update Cache -> Return Token
2. UPBIT (Stateless):
   Client -> Get Token -> Create Payload(Nonce) -> Sign(HMAC) -> Return Token

주요 기능:
- Strategy Pattern: `IAuthStrategy` 인터페이스를 통해 다양한 인증 방식 추상화.
- KIS Support (OAuth2): Access Token의 In-Memory Caching 및 Lazy Refresh (Thread-Safe).
- UPBIT Support (JWT): 요청 별 Payload 구성(Nonce, Query Hash) 및 즉시 서명(On-demand Signing).
- Fail-Fast: 잘못된 설정(Key/Secret)으로 인한 401/403 에러 발생 시 불필요한 재시도 방지.

Trade-off:
1. Architectural Pattern: Stateful Manager (KIS) vs Stateless Manufacturer (UPBIT)
   - KIS (OAuth2): '관리자(Manager)' 역할. 토큰의 생명주기(발급, 유지, 만료)를 관리해야 하므로
     상태 동기화(Locking)와 캐싱 로직이 필요하지만, API 서버의 부하를 줄일 수 있음.
   - UPBIT (JWT): '생산자(Manufacturer)' 역할. 상태 저장 없이 요청 시점마다 토큰을 즉시 생산하므로
     구현이 간결하고 확장성(Scalability)이 높으나, 클라이언트의 CPU 연산 비용이 발생함.

2. Refresh Strategy: Lazy Refresh (KIS) vs On-demand Creation (UPBIT)
   - KIS: 별도의 백그라운드 스레드 없이, 요청이 들어올 때 만료 여부를 체크(Lazy)하여 갱신함.
     장점은 구조가 단순해지나, 단점은 토큰 만료 직후 첫 요청에 지연(Latency)이 발생함.
   - UPBIT: 갱신 개념이 없으며, 매 요청마다 새로운 Nonce(UUID)를 포함하여 서명함.
     장점은 보안성(Replay Attack 방지)이 높으나, 매번 암호화 연산(SHA512)이 필요함.

3. Failure Handling:
   - 공통: 인증 키 설정 오류로 인한 401/403 응답은 재시도(Retry)해도 해결되지 않으므로,
     즉시 예외를 발생시켜(Fail-Fast) 불필요한 트래픽 낭비를 방지함.
"""

import hashlib
import uuid
import jwt  # Dependency: pyjwt
import asyncio
import logging
from urllib.parse import urlencode
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from src.common.interfaces import IAuthStrategy, IHttpClient
from src.common.exceptions import AuthError, NetworkConnectionError
from src.common.config import ConfigManager
from src.common.decorators import log_decorator, retry

# --- Constants & Configuration ---
TOKEN_EXPIRATION_BUFFER_MINUTES = 10
DEFAULT_TOKEN_DURATION_HOURS = 12
KIS_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
CONTENT_TYPE_JSON = "application/json"
GRANT_TYPE_CLIENT_CREDENTIALS = "client_credentials"
UPBIT_ALGORITHM = "HS256"


class KISAuthStrategy(IAuthStrategy):
    """한국투자증권(KIS) API 인증 전략 구현체 (Stateful).

    Attributes:
        app_key (str): KIS API App Key.
        app_secret (str): KIS API App Secret.
        base_url (str): API Base URL.
        _lock (asyncio.Lock): 토큰 갱신 경합 조건(Race Condition) 방지를 위한 락.
        _access_token (Optional[str]): 현재 유효한 Access Token.
        _expires_at (Optional[datetime]): 토큰 만료 예정 시각.
        _logger (logging.Logger): 클래스 전용 로거.
    """

    def __init__(self, config: ConfigManager) -> None:
        """KISAuthStrategy 인스턴스를 초기화합니다.

        Args:
            config (ConfigManager): 애플리케이션 전역 설정 객체.
        Raises:
            ValueError: 필수 설정(base_url)이 누락된 경우.
        """
        if not config.kis.base_url:
            raise ValueError("KIS API configuration missing: 'base_url' is empty.")

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
        """
        # Lock 획득 비용을 줄이기 위해, 유효한 토큰이 있으면 즉시 반환 (Lock-Free Read).
        if self._should_refresh():
            async with self._lock:
                # 대기 중 다른 스레드가 이미 갱신했을 수 있으므로 재확인 (Double-Checked Locking).
                if self._should_refresh():
                    self._logger.info("Access token is missing or expired. Initiating refresh.")
                    await self._issue_token(http_client)
        
        if not self._access_token:
            self._logger.error("Token refresh logic failed silently.")
            raise AuthError("Failed to retrieve access token.")

        return f"Bearer {self._access_token}"

    def _should_refresh(self) -> bool:
        """토큰 갱신 필요 여부를 판단합니다."""
        if not self._access_token or not self._expires_at:
            return True
        
        threshold_time = datetime.now() + timedelta(minutes=TOKEN_EXPIRATION_BUFFER_MINUTES)
        if threshold_time > self._expires_at:
            self._logger.debug("Token expiring soon. Refresh needed.")
            return True
        return False

    @log_decorator(logger_name="KISAuth", suppress_error=False)
    @retry(max_retries=3, base_delay=1.0, exceptions=(NetworkConnectionError,))
    async def _issue_token(self, http_client: IHttpClient) -> None:
        """KIS API를 호출하여 새로운 토큰을 발급받습니다."""
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": CONTENT_TYPE_JSON}
        body = {
            "grant_type": GRANT_TYPE_CLIENT_CREDENTIALS,
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            response: Dict[str, Any] = await http_client.post(url, headers=headers, data=body)
            self._validate_response(response)
            self._update_state(response)

        except NetworkConnectionError as e:
            error_msg = str(e)
            # Rationale: 인증 정보 오류(401/403)는 재시도해도 해결되지 않으므로 즉시 에러를 전파(Fail-Fast).
            if "403" in error_msg or "401" in error_msg:
                self._logger.error(f"Permanent Auth Failure (No Retry): {error_msg}")
                raise AuthError(f"Invalid Credentials: {error_msg}") from e
            raise e
        except Exception as e:
            raise AuthError(f"Error during token issuance: {str(e)}") from e

    def _validate_response(self, response: Dict[str, Any]) -> None:
        if "access_token" not in response:
            raise AuthError("Invalid token response: Missing access_token")

    def _update_state(self, response: Dict[str, Any]) -> None:
        self._access_token = response["access_token"]
        expired_str = response.get("access_token_token_expired")
        
        if expired_str:
            try:
                self._expires_at = datetime.strptime(expired_str, KIS_DATE_FORMAT)
            except ValueError:
                self._logger.warning("Failed to parse expiration date. Using fallback.")
                self._expires_at = datetime.now() + timedelta(hours=DEFAULT_TOKEN_DURATION_HOURS)
        else:
            self._expires_at = datetime.now() + timedelta(hours=DEFAULT_TOKEN_DURATION_HOURS)


class UPBITAuthStrategy(IAuthStrategy):
    """업비트(UPBIT) API 인증 전략 구현체 (Stateless).

    Attributes:
        access_key (str): UPBIT API Access Key.
        secret_key (str): UPBIT API Secret Key.
        base_url (str): API Base URL.
        _logger (logging.Logger): 클래스 전용 로거.
    """

    def __init__(self, config: ConfigManager) -> None:
        """UPBITAuthStrategy 인스턴스를 초기화합니다.

        Args:
            config (ConfigManager): 애플리케이션 전역 설정 객체.
        Raises:
            ValueError: Access Key, Secret Key, Base URL 설정이 누락된 경우.
        """
        if not config.upbit.base_url:
            raise ValueError("UPBIT API configuration missing: 'base_url' is empty.")
        
        self.access_key: str = config.upbit.api_key.get_secret_value()
        
        # secret_key가 Config 모델에 정의되지 않은 경우를 대비한 방어적 프로그래밍.
        if not hasattr(config.upbit, "secret_key"):
             raise ValueError("Configuration Error: 'secret_key' is missing in UPBITSettings.")
             
        self.secret_key: str = config.upbit.secret_key.get_secret_value()
        self.base_url: str = config.upbit.base_url
        self._logger = logging.getLogger(self.__class__.__name__)

    async def get_token(self, http_client: IHttpClient, **kwargs) -> str:
        """API 요청에 필요한 JWT(JSON Web Token)를 즉시 생성하여 반환합니다.

        KIS와 달리 서버 통신이나 캐싱 없이, 호출 시점에 즉시 서명된 토큰을 생성합니다.

        Args:
            http_client: 인터페이스 준수용 (사용 안함).
            **kwargs: 'query_params' 전달 시 해싱하여 Payload에 포함.

        Returns:
            str: "Bearer {jwt_token}"
        """
        # Nonce를 사용하여 재전송 공격(Replay Attack)을 방지.
        payload = {
            "access_key": self.access_key,
            "nonce": str(uuid.uuid4()),
        }

        # Query Parameter가 변조되지 않았음을 보장하기 위해 SHA512 해시를 Payload에 포함.
        query_params = kwargs.get("query_params")
        if query_params:
            query_string = urlencode(query_params)
            m = hashlib.sha512()
            m.update(query_string.encode("utf-8"))
            payload["query_hash"] = m.hexdigest()
            payload["query_hash_alg"] = "SHA512"

        # JWT 서명 (Stateless Creation, CPU Bound)
        jwt_token = jwt.encode(payload, self.secret_key, algorithm=UPBIT_ALGORITHM)

        if isinstance(jwt_token, bytes):
            jwt_token = jwt_token.decode("utf-8")

        return f"Bearer {jwt_token}"