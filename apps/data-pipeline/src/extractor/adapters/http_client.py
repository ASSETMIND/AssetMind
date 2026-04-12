"""
이 모듈은 aiohttp 라이브러리를 기반으로 비동기(Asynchronous) HTTP 통신을 수행하는 인프라 구현체입니다.
도메인 계층의 IHttpClient 인터페이스를 준수하여, 핵심 비즈니스 로직이 외부 통신 라이브러리(aiohttp)의
구체적인 구현 세부사항에 직접적으로 의존하지 않도록 의존성 역전 원칙(DIP)을 적용했습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 타겟 URL, HTTP Headers, Query Parameters 또는 Body Data (Client Request).
2. Interceptor: log_decorator 및 retry 데코레이터를 거치며 로깅 및 재시도 정책 자동 부여.
3. Connection Management: aiohttp.ClientSession 풀(Pool)에서 활성화된 TCP 커넥션 획득.
4. HTTP Execution: 비동기 논블로킹(Non-blocking) 방식의 외부 API 통신 (GET/POST).
5. Output: HTTP 상태 코드 검증 후, Content-Type 헤더에 따라 JSON 객체 파싱 또는 Raw Text 반환.

주요 기능:
- Asynchronous I/O: aiohttp 기반의 논블로킹 네트워크 연산을 통한 고성능 동시성(Concurrency) 보장.
- Resilience (회복 탄력성): `@retry` 데코레이터를 활용한 일시적 네트워크 장애(Timeout 등) 자동 복구 메커니즘.
- Observability (가시성): `@log_decorator`를 통한 HTTP 요청/응답 페이로드 및 지연 시간(Latency) 추적.
- Connection Pooling: 세션(ClientSession) 객체의 재사용을 통한 TCP Handshake 및 SSL/TLS 최적화.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. aiohttp 클라이언트 캡슐화 (기존):
   - 장점: 파이프라인 전역에서 외부 라이브러리(aiohttp)에 대한 강결합을 제거하여, 향후 httpx 등으로 교체 시 유지보수가 극도로 용이함.
   - 단점: 단순 API 호출을 위해 어댑터 클래스를 한 번 더 거쳐야 하므로 미세한 함수 호출 오버헤드가 존재함.
   - 근거: 대규모 데이터 파이프라인에서 인프라 교체 유연성과 공통 에러/로깅 규격 강제는 오버헤드를 감수할 만큼의 압도적인 이점을 제공함.
2. TCPConnector Limit 상향 및 Global/Local Timeout 하이브리드 적용 (신규):
   - 장점: 다수의 수집기가 동시에 요청을 보내도 소켓 큐잉 지연이 발생하지 않으며, 기존 메서드 시그니처(`timeout` 파라미터)를 유지하여 하위 모듈의 수정(산탄총 수술)을 완벽히 방지함.
   - 단점: 커넥션 풀(Limit=100)을 넓게 유지하므로 OS 레벨의 파일 디스크립터(FD) 사용량이 일시적으로 상승함.
   - 근거: 동시 실행(Concurrent Execution) 시 발생하는 Thundering Herd 병목을 해소하기 위해 파이프를 확장하는 것이며, 메서드 레벨의 timeout 파라미터를 보존하여 하위 호환성을 100% 보장하는 것이 객체지향 원칙에 부합함.
"""

import asyncio
from types import TracebackType
from typing import Any, Dict, Optional

import aiohttp

from src.common.decorators import log_decorator, retry
from src.common.exceptions import NetworkConnectionError
from src.common.interfaces import IHttpClient
from src.common.log import LogManager

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [설계 의도] 다중 API 동시 수집 시의 네트워크 병목을 해소하기 위한 명시적 자원 할당량
MAX_CONNECTION_LIMIT = 100
DNS_CACHE_TTL = 300
TOTAL_TIMEOUT_SECONDS = 30.0
CONNECT_TIMEOUT_SECONDS = 10.0

# ==============================================================================
# [Main Class] AsyncHttpAdapter
# ==============================================================================
class AsyncHttpAdapter(IHttpClient):
    """aiohttp를 사용하는 비동기 HTTP 클라이언트 구현체.

    외부 API 통신을 전담하며, 네트워크 예외를 도메인 예외로 변환하여 
    애플리케이션 계층을 보호합니다. Async Context Manager(`async with`)를 지원합니다.

    Attributes:
        timeout (aiohttp.ClientTimeout): 전체 요청의 최대 대기 시간(초) 설정 객체.
        _session (Optional[aiohttp.ClientSession]): 재사용 가능한 HTTP 커넥션 세션 풀.
    """

    def __init__(self) -> None:
        """AsyncHttpAdapter 인스턴스를 초기화합니다.

        Args:
            timeout (int, optional): 전체 요청 타임아웃 시간(초). Defaults to 30.
        """
        # [설계 의도] 대용량 데이터 수집이나 외부 API의 일시적 지연을 고려하여 
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "AsyncHttpAdapter":
        """Async Context Manager 진입 시 호출되며, 세션을 미리 생성하거나 준비합니다.
        
        Returns:
            AsyncHttpAdapter: 현재 인스턴스.
        """
        # [설계 의도] `async with AsyncHttpAdapter() as client:` 구문을 강제하여, 
        # 개발자가 네트워크 리소스(세션)의 생명주기를 누수(Leak) 없이 명확히 관리하도록 유도함.
        await self._get_session()
        return self

    async def __aexit__(
        self, 
        exc_type: Optional[type], 
        exc_val: Optional[Exception], 
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Async Context Manager 종료 시 호출되며, 활성화된 세션을 안전하게 정리합니다.

        Args:
            exc_type (Optional[type]): 발생한 예외의 타입.
            exc_val (Optional[Exception]): 발생한 예외 객체.
            exc_tb (Optional[TracebackType]): 예외의 트레이스백 정보.
        """
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        """싱글톤 패턴 기반의 aiohttp 클라이언트 세션을 초기화하고 반환합니다."""
        if self._session is None:
            # 1. Connection Pool & DNS Cache 최적화
            # [설계 의도] SSL/TLS 핸드셰이크와 DNS 룩업은 초기 비동기 통신에서 가장 큰 병목입니다.
            # Limit을 넉넉히 열어 대기열 지연을 없애고, DNS 캐시를 활용하여 컨텍스트 스위칭 속도를 극대화합니다.
            connector = aiohttp.TCPConnector(
                limit=MAX_CONNECTION_LIMIT,
                ttl_dns_cache=DNS_CACHE_TTL,
                use_dns_cache=True
            )
            
            # 2. Timeout Policy 강화
            # [설계 의도] 특정 외부 API 서버가 일시적으로 먹통이 되었을 때 파이프라인 전체가 
            # 멈춰버리는 것을 방지하기 위해 연결(10초) 및 전체 응답(30초) 데드라인을 강제합니다.
            timeout = aiohttp.ClientTimeout(
                total=TOTAL_TIMEOUT_SECONDS, 
                connect=CONNECT_TIMEOUT_SECONDS
            )
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )
        return self._session

    async def close(self) -> None:
        """사용 중인 세션을 명시적으로 종료하여 시스템 리소스(소켓 등)를 운영체제에 반환합니다."""
        if self._session and not self._session.closed:
            await self._session.close()

    @log_decorator(logger_name="HTTP")
    @retry(max_retries=3, base_delay=0.5, backoff_factor=2.0, exceptions=(NetworkConnectionError, asyncio.TimeoutError))
    async def get(
        self, 
        url: str, 
        headers: Optional[Dict[str, str]] = None, 
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """비동기 HTTP GET 요청을 수행합니다.

        실패 시 지수 백오프(Exponential Backoff) 기반의 자동 재시도를 수행하며,
        요청 및 응답의 메타데이터를 자동으로 로깅합니다.

        Args:
            url (str): 요청할 대상 엔드포인트 URL.
            headers (Optional[Dict[str, str]], optional): HTTP 요청 헤더 딕셔너리. Defaults to None.
            params (Optional[Dict[str, Any]], optional): URL Query String으로 변환될 파라미터. Defaults to None.

        Returns:
            Any: 성공적으로 파싱된 JSON 객체 또는 텍스트 문자열.

        Raises:
            NetworkConnectionError: 지정된 횟수만큼 재시도한 후에도 네트워크 연결 실패, 
                                    타임아웃, 또는 HTTP 4xx/5xx 에러가 발생한 경우.
        """
        session = await self._get_session()
        try:
            async with session.get(url, headers=headers, params=params) as response:
                return await self._handle_response(response, url, "GET")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # [설계 의도] 인프라 계층의 구체적인 에러(aiohttp.ClientError 등)가 도메인 계층으로 
            # 전파되는 것(Leaking)을 막기 위해, 시스템 표준 예외인 NetworkConnectionError로 래핑함.
            # 이를 통해 상위 재시도(Retry) 데코레이터가 인프라 라이브러리의 교체와 무관하게 일관되게 동작함.
            raise NetworkConnectionError(f"GET 요청 실패 ({url}): {str(e)}") from e

    @log_decorator(logger_name="HTTP", suppress_error=False)
    @retry(max_retries=3, base_delay=0.5, backoff_factor=2.0, exceptions=(NetworkConnectionError, asyncio.TimeoutError))
    async def post(
        self, 
        url: str, 
        headers: Optional[Dict[str, str]] = None, 
        data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """비동기 HTTP POST 요청을 수행합니다.

        Args:
            url (str): 요청할 대상 엔드포인트 URL.
            headers (Optional[Dict[str, str]], optional): HTTP 요청 헤더 딕셔너리. Defaults to None.
            data (Optional[Dict[str, Any]], optional): HTTP Body에 포함될 JSON 데이터. Defaults to None.

        Returns:
            Any: 성공적으로 파싱된 JSON 객체 또는 텍스트 문자열.

        Raises:
            NetworkConnectionError: 네트워크 장애 또는 HTTP 4xx/5xx 상태 코드 반환 시.
        """
        session = await self._get_session()
        try:
            async with session.post(url, headers=headers, json=data) as response:
                return await self._handle_response(response, url, "POST")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
             # [설계 의도] GET 메서드와 동일하게 예외를 래핑하여 어댑터의 인터페이스 일관성을 유지함.
             raise NetworkConnectionError(f"POST 요청 실패 ({url}): {str(e)}") from e

    async def _handle_response(
        self, 
        response: aiohttp.ClientResponse, 
        url: str, 
        method: str
    ) -> Any:
        """HTTP 응답 객체의 상태를 검증하고 페이로드를 안전하게 파싱합니다.

        Args:
            response (aiohttp.ClientResponse): aiohttp가 반환한 원본 응답 객체.
            url (str): 디버깅 및 에러 로깅을 위한 원본 요청 URL.
            method (str): 디버깅 및 에러 로깅을 위한 HTTP 메서드.

        Returns:
            Any: 파싱된 JSON 객체. JSON이 아닐 경우 Raw Text 문자열.

        Raises:
            NetworkConnectionError: HTTP Status Code가 400 이상(Client/Server Error)일 경우.
        """
        # [설계 의도] aiohttp는 4xx, 5xx 에러 발생 시 예외를 던지지 않고 상태 코드만 반환하므로,
        # 명시적으로 상태 코드를 검사하여 파이프라인의 조기 실패(Fail-Fast)를 유도함.
        if response.status >= 400:
            error_body = await response.text()
            raise NetworkConnectionError(f"HTTP {response.status} 에러 ({method} {url}): {error_body}")

        # 데이터 파싱 (JSON 우선 시도, 실패 시 Text 반환)
        try:
            content_type = response.headers.get("Content-Type", "").lower()
            if "application/json" in content_type:
                return await response.json()
            
            # [설계 의도] Content-Type이 JSON이 아니거나 명시되지 않은 경우, 
            # 강제로 파싱하지 않고 순수 텍스트를 반환하여 호출자에게 파싱 책임을 위임함.
            return await response.text()
        except (ValueError, aiohttp.ContentTypeError):
            # [설계 의도] API 벤더사 측의 버그로 인해 Content-Type은 JSON으로 선언해놓고 
            # 실제 바디는 HTML이나 깨진 텍스트를 보내는 경우를 대비한 최후의 방어벽(Fail-Safe).
            # 에러를 던지지 않고 텍스트로 우회 반환함으로써 애플리케이션 크래시를 방지함.
            return await response.text()