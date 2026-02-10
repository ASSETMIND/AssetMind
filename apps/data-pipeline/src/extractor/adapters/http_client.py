"""
HTTP 클라이언트 어댑터 (HTTP Client Adapter)

이 모듈은 aiohttp 라이브러리를 기반으로 비동기(Asynchronous) HTTP 통신을 수행하는 인프라 구현체입니다.
도메인 계층의 IHttpClient 인터페이스를 준수하여, 비즈니스 로직이 외부 통신 라이브러리(aiohttp)에
직접적으로 의존하지 않도록 의존성을 역전(DIP)시킵니다.

데이터 흐름 (Data Flow):
Client Request (URL, Params) -> [Decorator: Log -> Retry] -> Session Pool -> Async HTTP Request
-> Status Code Validation -> Return Data

주요 기능:
- Non-blocking I/O 기반의 고성능 GET/POST 요청 처리
- Decorator를 통한 자동 재시도(Retry) 및 로깅(Logging) 적용
- aiohttp.ClientSession 재사용을 통한 TCP Connection Pooling

Trade-off:
- Decorator Overhead vs Clean Code:
    - 장점: 비즈니스 로직(순수 통신)과 운영 로직(재시도, 로깅)의 완벽한 분리.
    - 단점: 함수 호출 스택 깊이가 깊어지나, 네트워크 I/O Latency 대비 무시할 수 있는 수준임.
    - 근거: 네트워크 불안정성에 대한 방어 로직을 일관성 있게 적용하는 것이 성능보다 운영 안정성에 훨씬 중요함.
"""

import aiohttp
import asyncio
from typing import Dict, Optional, Any
from types import TracebackType

from ..domain.interfaces import IHttpClient
from ..domain.exceptions import NetworkError
from ...common.log import LogManager
from ...common.decorators import log_decorator, retry


class AsyncHttpAdapter(IHttpClient):
    """aiohttp를 사용하는 비동기 HTTP 클라이언트 구현체.

    Attributes:
        timeout (aiohttp.ClientTimeout): 요청 타임아웃 설정.
        logger (logging.Logger): 로거 인스턴스.
        _session (Optional[aiohttp.ClientSession]): 재사용 가능한 HTTP 세션.
    """

    def __init__(self, timeout: int = 30):
        """AsyncHttpAdapter를 초기화합니다.

        Args:
            timeout (int): 전체 요청 타임아웃 시간(초). 기본값은 30초.
        """
        # Rationale: 네트워크 지연을 고려하여 넉넉한 타임아웃 설정 (Default: 30s)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.logger = LogManager.get_logger("AsyncHttpAdapter")
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "AsyncHttpAdapter":
        """Context Manager 진입: 세션을 미리 생성합니다.
        
        Rationale: 'async with' 구문을 통해 리소스(세션)의 생명주기를 명확히 관리하기 위함.
        """
        await self._get_session()
        return self

    async def __aexit__(
        self, 
        exc_type: Optional[type], 
        exc_val: Optional[Exception], 
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Context Manager 종료: 세션을 안전하게 정리합니다."""
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        """현재 활성화된 세션을 반환하거나, 없으면 새로 생성합니다.
        
        Rationale: TCP Handshake 비용을 절감하기 위해 Keep-Alive 연결을 유지하는 
        Session 객체를 재사용(Singleton-like within instance)합니다.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """사용 중인 세션을 명시적으로 종료하여 리소스를 반환합니다."""
        if self._session and not self._session.closed:
            await self._session.close()
            self.logger.info("Async HTTP Session closed.")

    @log_decorator(logger_name="HTTP", suppress_error=False)
    @retry(max_retries=3, base_delay=0.5, backoff_factor=2.0, exceptions=(NetworkError, asyncio.TimeoutError))
    async def get(
        self, 
        url: str, 
        headers: Optional[Dict[str, str]] = None, 
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """비동기 GET 요청을 수행합니다. (Retry & Log 적용)

        Args:
            url (str): 요청할 대상 URL.
            headers (Optional[Dict]): HTTP 요청 헤더.
            params (Optional[Dict]): URL 쿼리 파라미터.

        Returns:
            Any: 파싱된 응답 데이터 (주로 Dict).

        Raises:
            NetworkError: 네트워크 연결 실패, 타임아웃, 4xx/5xx 에러 시 발생 (재시도 실패 후).
        """
        session = await self._get_session()
        try:
            async with session.get(url, headers=headers, params=params) as response:
                return await self._handle_response(response, url, "GET")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # Rationale: 원본 에러(aiohttp specific)를 래핑하여 
            # 상위 도메인 로직이 인프라 구현 세부사항(aiohttp)에 의존하지 않도록 함.
            # 또한 RetryDecorator가 감지할 수 있는 예외(NetworkError)로 변환함.
            raise NetworkError(f"GET {url} failed: {str(e)}") from e

    @log_decorator(logger_name="HTTP", suppress_error=False)
    @retry(max_retries=3, base_delay=0.5, backoff_factor=2.0, exceptions=(NetworkError, asyncio.TimeoutError))
    async def post(
        self, 
        url: str, 
        headers: Optional[Dict[str, str]] = None, 
        data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """비동기 POST 요청을 수행합니다. (Retry & Log 적용)

        Args:
            url (str): 요청할 대상 URL.
            headers (Optional[Dict]): HTTP 요청 헤더.
            data (Optional[Dict]): 요청 바디 데이터 (JSON 직렬화).

        Returns:
            Any: 파싱된 응답 데이터.

        Raises:
            NetworkError: 네트워크 연결 실패, 타임아웃, 4xx/5xx 에러 시 발생 (재시도 실패 후).
        """
        session = await self._get_session()
        try:
            async with session.post(url, headers=headers, json=data) as response:
                return await self._handle_response(response, url, "POST")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
             # Rationale: GET과 동일하게 예외를 래핑하여 일관된 에러 인터페이스 제공.
             raise NetworkError(f"POST {url} failed: {str(e)}") from e

    async def _handle_response(
        self, 
        response: aiohttp.ClientResponse, 
        url: str, 
        method: str
    ) -> Any:
        """HTTP 응답을 검증하고 안전하게 파싱합니다.

        Args:
            response (aiohttp.ClientResponse): aiohttp 응답 객체.
            url (str): 요청 URL (로깅용).
            method (str): 요청 메서드 (로깅용).

        Returns:
            Any: 파싱된 JSON 객체 또는 텍스트.

        Raises:
            NetworkError: HTTP Status가 400 이상일 경우.
        """
        # 1. HTTP Status 검사
        if response.status >= 400:
            error_body = await response.text()
            self.logger.warning(
                f"[{method}] HTTP Error | Status: {response.status} | URL: {url} | Body: {error_body[:200]}"
            )
            # Rationale: 4xx/5xx 에러는 정상 응답이 아니므로 예외를 발생시켜 흐름을 제어함.
            raise NetworkError(f"HTTP {response.status} on {method} {url}: {error_body}")

        # 2. 데이터 파싱 (JSON 우선, 실패 시 Text 반환)
        try:
            content_type = response.headers.get("Content-Type", "").lower()
            if "application/json" in content_type:
                return await response.json()
            # Rationale: Content-Type이 JSON이 아니거나 명시되지 않은 경우 텍스트로 반환.
            return await response.text()
        except (ValueError, aiohttp.ContentTypeError) as e:
            # Rationale: JSON 헤더가 있어도 바디가 깨져있는 경우에 대한 방어 코드.
            self.logger.warning(
                f"[{method}] JSON Parsing Failed | URL: {url} | Error: {str(e)}. Falling back to text."
            )
            return await response.text()