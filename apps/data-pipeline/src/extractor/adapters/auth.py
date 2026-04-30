"""
외부 API(KIS, UPBIT 등) 연동을 위한 인증 토큰의 발급, 갱신, 서명(Signing) 수명 주기를 중앙에서 관리합니다.
API 제공자의 인증 스펙(OAuth2 vs JWT)에 따라 서로 다른 전략 패턴(Strategy Pattern)을 구현하여,
인프라 계층(HTTP Adapter)이나 비즈니스 로직이 인증의 복잡성에 구애받지 않고 투명하게 통신할 수 있도록 돕습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. KIS (Stateful): Client Request -> Check Memory Cache -> (If Expired) Acquire Lock -> HTTP POST -> Update Cache -> Return Access Token
2. UPBIT (Stateless): Client Request -> Create Payload(Nonce, Query Hash) -> Sign with Secret (HMAC) -> Return JWT Token

주요 기능:
- Strategy Pattern: `IAuthStrategy` 인터페이스를 통해 다양한 인증 방식을 추상화하여 OCP(개방-폐쇄 원칙) 준수.
- KIS Support (OAuth2): Access Token의 In-Memory Caching 및 Lazy Refresh를 통한 외부 API 호출 빈도 최적화.
- UPBIT Support (JWT): 매 요청별 고유 Payload 구성(Nonce, Query Hash) 및 즉시 서명(On-demand Signing)을 통한 보안성 확보.
- Fail-Fast Mechanism: 잘못된 인증 키 설정으로 인한 401/403 예외 발생 시, 무의미한 재시도(Retry)를 즉시 중단하여 트래픽 낭비 방지.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. Architectural Pattern: Stateful Manager (KIS) vs Stateless Manufacturer (UPBIT)
   - 장점: 각 API 벤더의 보안 정책(KIS는 토큰 장기 재사용, UPBIT은 매 요청 서명 요구)에 가장 최적화된 리소스 관리가 가능함.
   - 단점: 전략 클래스 간 내부 구현(캐싱 상태 관리 유무 등)이 파편화되어 유지보수 시 인지 부하(Cognitive Load)가 발생할 수 있음.
   - 근거: API 서버의 Rate Limit 제약 준수와 Replay Attack 방지라는 상충되는 요구사항을 동시에 충족하기 위해서는 벤더 맞춤형 생명주기 분리가 필수적임.
2. Refresh Strategy: Lazy Refresh vs Background Daemon (KIS Auth)
   - 장점: 별도의 백그라운드 갱신 스레드 없이 토큰이 필요한 시점에만 갱신하므로 시스템 리소스(CPU/Memory) 사용이 효율적임.
   - 단점: 토큰 만료 직후 유입되는 첫 번째 요청(First Request)에 한해 동기화 락(Lock) 획득 및 외부 통신에 따른 지연(Latency)이 발생함.
   - 근거: KIS 토큰 수명(12시간)이 매우 길어 갱신 빈도가 극히 낮으므로, 워커를 상시 구동하는 것보다 Lazy Refresh 구조가 시스템 복잡도를 낮추는 데 압도적으로 유리함.
3. Fail-Fast on 401/403 (Error Handling)
   - 장점: 인증 정보 오류 시 네트워크 재시도 파이프라인을 우회하여 즉각적으로 시스템에 알람을 발생시킴.
   - 단점: 일시적인 외부 API의 인증 서버 장애도 영구적인 오류로 취급될 위험이 미세하게 존재함.
   - 근거: 대부분의 401/403 에러는 자격 증명(Key/Secret)의 오기입이나 만료로 발생하므로, Exponential Backoff를 수행하는 것은 무의미한 리소스 낭비임.
"""

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import jwt

from src.common.config import ConfigManager
from src.common.decorators import log_decorator, retry
from src.common.exceptions import AuthError, NetworkConnectionError
from src.common.interfaces import IAuthStrategy, IHttpClient

# ==============================================================================
# [Configuration] Constants
# ==============================================================================
# [설계 의도] 토큰 만료 10분 전부터 갱신 대상으로 간주하여, 통신 지연으로 인한 
# 만료 토큰 사용(Unauthorized Error)을 사전 차단(Margin)함.
TOKEN_EXPIRATION_BUFFER_MINUTES: int = 10

# [설계 의도] KIS API 응답에서 만료 일시 파싱 실패 시 적용할 Fail-Safe용 기본 수명(12시간).
DEFAULT_TOKEN_DURATION_HOURS: int = 12

# [설계 의도] KIS API가 제공하는 날짜 문자열 규격.
KIS_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# [설계 의도] 하드코딩 방지를 위한 HTTP/Auth 프로토콜 관련 상수 정의.
CONTENT_TYPE_JSON: str = "application/json"
GRANT_TYPE_CLIENT_CREDENTIALS: str = "client_credentials"
UPBIT_ALGORITHM: str = "HS256"


# ==============================================================================
# [Main Classes] Authentication Strategies
# ==============================================================================
class KISAuthStrategy(IAuthStrategy):
    """한국투자증권(KIS) API 인증 전략 구현체 (Stateful 방식).

    내부적으로 Access Token을 캐싱하며, 만료가 임박했을 때만 비동기 Lock을 
    사용하여 안전하게 토큰을 갱신(Lazy Refresh)합니다.

    Attributes:
        app_key (str): KIS API 연동을 위한 App Key.
        app_secret (str): KIS API 연동을 위한 App Secret.
        base_url (str): KIS API의 Base URL.
    """

    def __init__(self, config: ConfigManager) -> None:
        """KISAuthStrategy 인스턴스를 초기화하고 환경 설정을 주입받습니다.

        Args:
            config (ConfigManager): 애플리케이션 전역 설정 인스턴스.
            
        Raises:
            ValueError: 필수 설정 값(base_url)이 누락된 경우.
        """
        if not config.kis.base_url:
            raise ValueError("KIS API configuration missing: 'base_url' is empty.")

        # [설계 의도] SecretStr 객체에서 평문을 추출하여 메모리에 적재. 
        # 이는 매 서명/통신 시 객체 접근 오버헤드를 줄이기 위함.
        self.app_key: str = config.kis.app_key.get_secret_value()
        self.app_secret: str = config.kis.app_secret.get_secret_value()
        self.base_url: str = config.kis.base_url

        # [설계 의도] AsyncIO 환경에서 다수의 코루틴이 동시에 토큰 갱신을 시도하는 
        # 경합 조건(Race Condition)을 방지하기 위한 뮤텍스(Mutex) 락.
        self._lock: asyncio.Lock = asyncio.Lock()
        self._access_token: Optional[str] = None
        self._expires_at: Optional[datetime] = None

    @log_decorator(logger_name="KISAuth")
    async def get_token(self, http_client: IHttpClient) -> str:
        """유효한 Bearer Access Token을 반환합니다.

        메모리에 캐싱된 토큰의 만료 시간을 검사하고, 유효하지 않을 경우 
        Double-Checked Locking 패턴을 사용하여 단 1회의 외부 API 호출만으로 토큰을 갱신합니다.

        Args:
            http_client (IHttpClient): 외부 API와 통신할 HTTP 클라이언트 인스턴스.

        Returns:
            str: "Bearer {access_token}" 포맷의 인증 헤더용 문자열.
            
        Raises:
            AuthError: 최종적으로 유효한 토큰을 획득하지 못한 경우.
        """
        # [설계 의도] Lock 획득은 비싼 연산이므로, 토큰이 유효한 대부분의 상황에서는 
        # Lock 없이 즉시 반환하도록 최적화(Lock-Free Read).
        if self._should_refresh():
            async with self._lock:
                # [설계 의도] Double-Checked Locking. Lock을 획득하기 위해 대기하는 동안 
                # 다른 코루틴이 이미 갱신을 완료했을 수 있으므로 다시 한번 상태를 검사함.
                if self._should_refresh():
                    await self._issue_token(http_client)
        
        if not self._access_token:
            raise AuthError("접근 토큰(Access Token)을 가져오지 못했습니다.")

        return f"Bearer {self._access_token}"

    def _should_refresh(self) -> bool:
        """현재 캐싱된 토큰의 갱신 필요 여부를 확인합니다.

        Returns:
            bool: 토큰이 없거나, 만료 버퍼 시간(10분) 이내에 진입한 경우 True.
        """
        if not self._access_token or not self._expires_at:
            return True
        
        threshold_time = datetime.now() + timedelta(minutes=TOKEN_EXPIRATION_BUFFER_MINUTES)
        return threshold_time > self._expires_at

    @retry(max_retries=3, base_delay=1.0, exceptions=(NetworkConnectionError,))
    async def _issue_token(self, http_client: IHttpClient) -> None:
        """외부 API를 호출하여 새로운 토큰을 발급받고 내부 상태를 동기화합니다.

        Args:
            http_client (IHttpClient): 외부 API와 통신할 HTTP 클라이언트.

        Raises:
            AuthError: 권한 오류(401/403) 또는 응답 구조 오류가 발생한 경우.
            NetworkConnectionError: 일시적인 네트워크 장애가 발생한 경우 (상단 데코레이터에서 재시도 처리).
        """
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
            # [설계 의도] Fail-Fast 정책. 401(Unauthorized), 403(Forbidden) 에러는 
            # 재시도(Retry)해도 절대 성공하지 않으므로 즉각적으로 파이프라인을 중단시킴.
            if "403" in error_msg or "401" in error_msg:
                raise AuthError(f"유효하지 않은 인증 정보: {error_msg}") from e
            raise e
        except Exception as e:
            raise AuthError(f"토큰 발급 중 예기치 못한 오류 발생: {str(e)}") from e

    def _validate_response(self, response: Dict[str, Any]) -> None:
        """응답 페이로드의 무결성을 검증합니다."""
        if "access_token" not in response:
            raise AuthError("유효하지 않은 토큰 응답: 'access_token' 필드 누락")

    def _update_state(self, response: Dict[str, Any]) -> None:
        """검증된 응답 데이터를 바탕으로 인스턴스의 상태(캐시)를 갱신합니다."""
        self._access_token = response["access_token"]
        expired_str = response.get("access_token_token_expired")
        
        if expired_str:
            try:
                self._expires_at = datetime.strptime(expired_str, KIS_DATE_FORMAT)
            except ValueError:
                # [설계 의도] 시간 포맷 파싱 실패가 전체 파이프라인 중단을 야기하지 않도록 
                # 기본 수명(12시간)을 할당하는 Fail-Safe 메커니즘.
                self._expires_at = datetime.now() + timedelta(hours=DEFAULT_TOKEN_DURATION_HOURS)
        else:
            self._expires_at = datetime.now() + timedelta(hours=DEFAULT_TOKEN_DURATION_HOURS)


class UPBITAuthStrategy(IAuthStrategy):
    """업비트(UPBIT) API 인증 전략 구현체 (Stateless 방식).

    별도의 토큰 캐싱이나 갱신 절차 없이, API 요청이 발생할 때마다 
    고유한 JWT(JSON Web Token)를 즉시 서명(On-demand Signing)하여 반환합니다.

    Attributes:
        access_key (str): UPBIT API Access Key.
        secret_key (str): UPBIT API Secret Key.
        base_url (str): UPBIT API의 Base URL.
    """

    def __init__(self, config: ConfigManager) -> None:
        """UPBITAuthStrategy 인스턴스를 초기화하고 환경 설정을 주입받습니다.

        Args:
            config (ConfigManager): 애플리케이션 전역 설정 인스턴스.
            
        Raises:
            ValueError: 필수 설정 값(base_url, secret_key 등)이 누락된 경우.
        """
        if not config.upbit.base_url:
            raise ValueError("업비트 API 설정 오류: 'base_url'이 비어 있습니다.")
        
        self.access_key: str = config.upbit.api_key.get_secret_value()
        
        # [설계 의도] Config 모델 스키마 변경 등으로 secret_key 속성이 누락될 경우를 대비한 방어적 검증.
        if not hasattr(config.upbit, "secret_key"):
             raise ValueError("업비트 API 설정 오류: 'secret_key' 속성이 누락되었습니다.")
             
        self.secret_key: str = config.upbit.secret_key.get_secret_value()
        self.base_url: str = config.upbit.base_url

    @log_decorator(logger_name="UPBITAuth")
    async def get_token(self, http_client: IHttpClient, **kwargs: Any) -> str:
        """API 요청에 필요한 JWT를 즉시 생성 및 서명하여 반환합니다.

        Args:
            http_client (IHttpClient): 인터페이스 시그니처 준수용 (Stateless이므로 사용하지 않음).
            **kwargs (Any): `query_params` 키워드 인자가 전달될 경우, 이를 해싱하여 JWT Payload에 포함.

        Returns:
            str: "Bearer {jwt_token}" 포맷의 인증 헤더용 문자열.
        """
        # [설계 의도] Nonce(UUID4)를 사용하여 동일한 파라미터 요청이라도 해시값이 달라지게 만들어 
        # 네트워크 스니핑을 통한 재전송 공격(Replay Attack)을 원천 차단함.
        payload = {
            "access_key": self.access_key,
            "nonce": str(uuid.uuid4()),
        }

        # [설계 의도] Query Parameter 변조를 방지하기 위해, 요청 파라미터 전체를 
        # 강력한 암호화 알고리즘(SHA512)으로 해싱하여 JWT 페이로드에 포함시킴.
        query_params = kwargs.get("query_params")
        if query_params:
            query_string = urlencode(query_params)
            m = hashlib.sha512()
            m.update(query_string.encode("utf-8"))
            payload["query_hash"] = m.hexdigest()
            payload["query_hash_alg"] = "SHA512"

        # [설계 의도] JWT 인코딩 시 발생하는 CPU 연산 바운드(Bound) 작업.
        # PyJWT 최신 버전 명세에 따라 HS256 알고리즘을 명시하여 서명 취약점을 방지함.
        jwt_token = jwt.encode(payload, self.secret_key, algorithm=UPBIT_ALGORITHM)

        if isinstance(jwt_token, bytes):
            jwt_token = jwt_token.decode("utf-8")

        return f"Bearer {jwt_token}"