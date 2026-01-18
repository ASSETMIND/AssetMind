"""
KIS API Authentication Strategy Module

이 모듈은 한국투자증권(KIS) API 사용을 위한 OAuth2 인증 토큰의 수명 주기를 관리합니다.
디스크 I/O 없이 메모리 내에서 상태를 관리(In-Memory Caching)하며, 만료 시간이 임박했을 때
자동으로 토큰을 갱신하는 'Lazy Refresh' 전략을 사용합니다.

데이터 흐름 (Data Flow):
Client Request -> KISAuthStrategy.get_token() 
               -> Check Memory Cache (Valid?) 
               -> [If Invalid/Expired] -> POST KIS Auth Server 
               -> Parse Response & Update Memory 
               -> Return Access Token

주요 기능:
- OAuth2 Access Token 발급 및 메모리 캐싱
- 만료 시간 자동 감지 및 갱신 (Lazy Loading)
- 안전 버퍼(Safety Buffer)를 둔 선제적 갱신 로직

Trade-off:
- In-Memory Management:
    - 장점: 파일 시스템 의존성 제거로 인한 배포 용이성(Stateless), I/O Latency 제거.
    - 단점: 프로세스 재시작 시 토큰 정보 소실로 인한 불필요한 재발급 요청 발생 가능성.
    - 근거: 트레이딩 시스템은 주로 장시간 실행되는 데몬 형태이므로, 초기 1회 재발급 비용보다 런타임 성능과 배포 단순성이 더 중요함.
- Lazy Refresh vs Background Task:
    - 장점: 별도의 스케줄러나 백그라운드 스레드 없이 요청 시점에 직관적으로 처리 가능.
    - 단점: 갱신 시점의 첫 요청에 Latency가 발생함.
    - 근거: API 호출 빈도가 높지 않거나, 첫 호출의 수백 ms 지연이 치명적이지 않은 환경에서 복잡도를 낮추기 위함.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Framework/Local Imports
# 실제 환경에서는 해당 경로에 인터페이스와 예외 클래스가 정의되어 있어야 합니다.
from ..domain.interfaces import IAuthStrategy, IHttpClient
from ..domain.exceptions import AuthError, NetworkError
from ...common.config import AppConfig

# --- Constants & Configuration ---
# 매직 넘버 방지를 위한 상수 정의
TOKEN_EXPIRATION_BUFFER_MINUTES = 10
DEFAULT_TOKEN_DURATION_HOURS = 12
KIS_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
CONTENT_TYPE_JSON = "application/json"
GRANT_TYPE_CLIENT_CREDENTIALS = "client_credentials"

class KISAuthStrategy(IAuthStrategy):
    """한국투자증권(KIS) API 인증 전략 구현체.

    Attributes:
        app_key (str): KIS API App Key.
        app_secret (str): KIS API App Secret.
        base_url (str): API Base URL (실전/모의투자).
        _access_token (Optional[str]): 캐싱된 접근 토큰.
        _expires_at (Optional[datetime]): 토큰 만료 시각.
        _logger (logging.Logger): 로깅 인스턴스.
    """

    def __init__(self, config: AppConfig) -> None:
        """KISAuthStrategy 인스턴스를 초기화합니다.

        Args:
            config (AppConfig): 애플리케이션 설정 객체. 
                                kis_app_key, kis_app_secret, kis_base_url을 포함해야 함.
        
        Raises:
            ValueError: 필수 설정값이 비어있을 경우 발생.
        """
        # Configuration Validation (Fail Fast)
        if not all([config.kis_app_key, config.kis_app_secret, config.kis_base_url]):
            raise ValueError("KIS API configuration missing (AppKey, Secret, or BaseURL).")

        self.app_key: str = config.kis_app_key
        self.app_secret: str = config.kis_app_secret
        self.base_url: str = config.kis_base_url

        self._lock = asyncio.Lock()

        # State Variables (In-Memory Cache)
        self._access_token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
        
        # Logging 설정
        self._logger = logging.getLogger(self.__class__.__name__)

    async def get_token(self, http_client: IHttpClient) -> str:
        """유효한 Bearer Access Token을 반환합니다.

        토큰이 없거나 만료 시간이 임박(버퍼 시간 내)한 경우,
        자동으로 KIS 서버에 요청하여 토큰을 갱신합니다.

        Args:
            http_client (IHttpClient): HTTP 요청을 수행할 클라이언트 인터페이스.

        Returns:
            str: "Bearer {access_token}" 형태의 인증 문자열.

        Raises:
            AuthError: 토큰 발급 실패 시.
            NetworkError: 네트워크 통신 장애 시.
        """
        # 1차 검사: 락 없이 빠르게 확인 (대부분의 요청은 여기서 통과하여 성능 유지)
        if self._should_refresh():
            # 락 획득 (여기서 대기 발생)
            async with self._lock:
                # 2차 검사: 락을 기다리는 동안 앞선 요청이 갱신했을 수 있으므로 다시 확인
                if self._should_refresh():
                    self._logger.info("Access token is missing or expired. Initiating refresh.")
                    await self._issue_token(http_client)
        
        # 방어적 코딩: 로직상 _issue_token 이후에는 반드시 토큰이 존재해야 함
        if not self._access_token:
            self._logger.error("Token refresh logic failed silently.")
            raise AuthError("Failed to retrieve access token.")

        return f"Bearer {self._access_token}"

    def _should_refresh(self) -> bool:
        """토큰 갱신 필요 여부를 판단합니다.

        설계 의도:
        단순히 현재 시간이 만료 시간을 지났는지 뿐만 아니라, 
        긴 작업 도중 토큰이 만료되는 것을 방지하기 위해 
        Safety Buffer(10분)를 두어 미리 갱신합니다.

        Returns:
            bool: 갱신이 필요하면 True, 아니면 False.
        """
        # 1. 토큰이나 만료 정보가 없는 경우 (초기 상태)
        if not self._access_token or not self._expires_at:
            return True
        
        # 2. 현재 시간 + 버퍼(10분)가 만료 시간을 초과했는지 확인
        # Timezone-naive datetime 사용을 가정 (KIS API 응답 기준)
        threshold_time = datetime.now() + timedelta(minutes=TOKEN_EXPIRATION_BUFFER_MINUTES)
        
        if threshold_time > self._expires_at:
            self._logger.debug(
                f"Token expiring soon (Expires at: {self._expires_at}, Threshold: {threshold_time}). Refresh needed."
            )
            return True
            
        return False

    async def _issue_token(self, http_client: IHttpClient) -> None:
        """KIS API를 호출하여 새로운 토큰을 발급받고 상태를 업데이트합니다.

        Args:
            http_client (IHttpClient): HTTP 요청 클라이언트.

        Raises:
            AuthError: API 응답이 예상과 다르거나 에러가 포함된 경우.
            NetworkError: 네트워크 연결 실패 시.
        """
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": CONTENT_TYPE_JSON}
        body = {
            "grant_type": GRANT_TYPE_CLIENT_CREDENTIALS,
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            self._logger.info(f"Requesting new token from {url}")
            
            # http_client.post는 딕셔너리 형태의 JSON 응답을 반환한다고 가정
            response: Dict[str, Any] = await http_client.post(url, headers=headers, data=body)
            
            self._validate_response(response)
            self._update_state(response)

            self._logger.info(f"Token refreshed successfully. Expires at: {self._expires_at}")

        except NetworkError as e:
            self._logger.error(f"Network error during token issuance: {str(e)}")
            raise AuthError("Failed to connect to KIS Auth Server") from e
        except Exception as e:
            self._logger.error(f"Unexpected error during token issuance: {str(e)}")
            raise AuthError(f"Error during token issuance: {str(e)}") from e

    def _validate_response(self, response: Dict[str, Any]) -> None:
        """API 응답의 유효성을 검증합니다.

        Args:
            response (Dict[str, Any]): API 응답 데이터.

        Raises:
            AuthError: access_token 필드가 없는 경우.
        """
        if "access_token" not in response:
            self._logger.error(f"Invalid token response format: {response}")
            raise AuthError(f"Invalid token response: Missing access_token")

    def _update_state(self, response: Dict[str, Any]) -> None:
        """응답 데이터를 파싱하여 내부 상태(토큰, 만료시간)를 갱신합니다.

        Args:
            response (Dict[str, Any]): 검증된 API 응답 데이터.
        """
        self._access_token = response["access_token"]
        
        # KIS API의 만료 시간 필드명: 'access_token_token_expired'
        expired_str = response.get("access_token_token_expired")
        
        if expired_str:
            try:
                self._expires_at = datetime.strptime(expired_str, KIS_DATE_FORMAT)
            except ValueError:
                self._logger.warning(f"Failed to parse expiration date: {expired_str}. Using fallback duration.")
                self._expires_at = datetime.now() + timedelta(hours=DEFAULT_TOKEN_DURATION_HOURS)
        else:
            # 만료 시간이 응답에 없는 경우, 안전하게 Fallback 설정
            self._logger.warning("Expiration field missing in response. Using fallback duration.")
            self._expires_at = datetime.now() + timedelta(hours=DEFAULT_TOKEN_DURATION_HOURS)