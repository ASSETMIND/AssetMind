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
- Connection Pooling: 세션(ClientSession) 객체의 재사용을 통한 TCP Handshake 및 SSL/TLS Negotiation 오버헤드 최소화.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 장점: 비즈니스 로직(순수 데이터 수집)과 횡단 관심사(로깅, 재시도, 커넥션 관리)를 데코레이터와 어댑터 패턴으로 완벽히 분리하여 응집도를 극대화함. 외부 라이브러리 교체 시 도메인 코드 수정이 불필요함.
- 단점: 데코레이터 체이닝 및 비동기 컨텍스트 스위칭으로 인해 호출 스택(Call Stack)이 깊어지고 미세한 Reflection 오버헤드가 발생함.
- 근거: 외부 API(KIS, FRED 등) 통신 시 필연적으로 발생하는 네트워크 I/O 지연(수십~수백 ms)에 비하면 데코레이터 오버헤드(수 us)는 무시할 수 있는 수준임. 분산 파이프라인 환경에서는 미세한 성능 최적화보다 운영 안정성(Observability & Fault Tolerance) 확보가 압도적으로 중요함.
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

    def __init__(self, timeout: int = 30) -> None:
        """AsyncHttpAdapter 인스턴스를 초기화합니다.

        Args:
            timeout (int, optional): 전체 요청 타임아웃 시간(초). Defaults to 30.
        """
        # [설계 의도] 대용량 데이터 수집이나 외부 API의 일시적 지연을 고려하여 
        # 넉넉한 타임아웃(기본 30초)을 설정함으로써 불필요한 실패를 방지함.
        self.timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(total=timeout)
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
        """현재 활성화된 커넥션 세션을 반환하거나, 없을 경우 새로 생성합니다.
        
        Returns:
            aiohttp.ClientSession: 초기화 및 연결 대기 중인 HTTP 세션.
        """
        # [설계 의도] 매 요청마다 새로운 세션을 만들면 TCP Handshake 비용이 심각하게 발생함.
        # 인스턴스 내에서 Singleton-like하게 연결 풀을 유지(Keep-Alive)하여 성능을 극대화함.
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
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
        params: Optional[Dict[str, Any]] = None
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