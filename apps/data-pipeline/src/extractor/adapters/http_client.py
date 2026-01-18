"""
HTTP 클라이언트 어댑터 (HTTP Client Adapter)

이 모듈은 aiohttp 라이브러리를 기반으로 비동기(Asynchronous) HTTP 통신을 수행하는 인프라 구현체입니다.
도메인 계층의 IHttpClient 인터페이스를 준수하여, 비즈니스 로직이 외부 통신 라이브러리(aiohttp)에
직접적으로 의존하지 않도록 의존성을 역전(DIP)시킵니다.

데이터 흐름 (Data Flow):
Client Request (URL, Params) -> Session Pool (Get/Reuse) -> Async HTTP Request
-> Status Code Validation (>=400 Error) -> Content-Type Check -> Parse JSON/Text -> Return Data

주요 기능:
- Non-blocking I/O 기반의 고성능 GET/POST 요청 처리
- aiohttp.ClientSession 재사용을 통한 TCP Connection Pooling 및 Handshake 비용 절감
- Context Manager (async with) 지원으로 안전한 리소스(Session) 생성 및 반환 보장
- 라이브러리 종속적인 예외(aiohttp.ClientError)를 도메인 표준 예외(NetworkError)로 변환 및 캡슐화

Trade-off:
- Async Complexity vs Performance:
    - 장점: I/O Bound 작업에서 스레드 블로킹 없이 높은 동시성(Concurrency) 처리 가능.
    - 단점: 호출하는 상위 모듈까지 모두 `async/await` 전파(Function Color Problem)로 인한 복잡도 증가.
    - 근거: 대량의 데이터 수집 및 API 호출이 빈번한 파이프라인 특성상 동기 방식의 Latency는 허용 불가능함.
- Session Pooling Strategy:
    - 장점: 매 요청마다 세션을 생성/파기하지 않고 재사용하여 TCP Handshake 오버헤드 최소화.
    - 단점: 세션 수명 주기 관리 책임 발생 (Context Manager 미사용 시 리소스 누수 위험).
    - 근거: 빈번한 API 호출 환경에서 연결 설정 비용(Connection Overhead)이 전체 성능의 병목이 되므로 풀링 필수.
"""

import aiohttp
import asyncio
import logging
from typing import Dict, Optional, Any, Union
from types import TracebackType

from ..domain.interfaces import IHttpClient
from ..domain.exceptions import NetworkError
from ...common.log import LogManager


class AsyncHttpAdapter(IHttpClient):
    """aiohttp를 사용하는 비동기 HTTP 클라이언트 구현체.

    Context Manager 프로토콜을 지원하여 `async with` 구문 사용을 권장합니다.
    
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
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.logger = LogManager.get_logger("AsyncHttpAdapter")
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "AsyncHttpAdapter":
        """Context Manager 진입: 세션을 미리 생성합니다."""
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
        
        Rationale:
            TCP Handshake 비용을 절감하기 위해 Keep-Alive 연결을 유지하는 
            Session 객체를 재사용(Singleton-like within instance)합니다.

        Returns:
            aiohttp.ClientSession: 비동기 HTTP 세션 객체.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """사용 중인 세션을 명시적으로 종료하여 리소스를 반환합니다."""
        if self._session and not self._session.closed:
            await self._session.close()
            self.logger.info("Async HTTP Session closed.")

    async def get(
        self, 
        url: str, 
        headers: Optional[Dict[str, str]] = None, 
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """비동기 GET 요청을 수행합니다.

        Args:
            url (str): 요청할 대상 URL.
            headers (Optional[Dict]): HTTP 요청 헤더.
            params (Optional[Dict]): URL 쿼리 파라미터.

        Returns:
            Any: 파싱된 응답 데이터 (주로 Dict).

        Raises:
            NetworkError: 네트워크 연결 실패, 타임아웃, 4xx/5xx 에러 시 발생.
        """
        session = await self._get_session()
        try:
            async with session.get(url, headers=headers, params=params) as response:
                return await self._handle_response(response, url, "GET")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.logger.error(f"[GET] Request Failed | URL: {url} | Error: {str(e)}")
            raise NetworkError(f"GET {url} failed: {str(e)}") from e

    async def post(
        self, 
        url: str, 
        headers: Optional[Dict[str, str]] = None, 
        data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """비동기 POST 요청을 수행합니다.

        Args:
            url (str): 요청할 대상 URL.
            headers (Optional[Dict]): HTTP 요청 헤더.
            data (Optional[Dict]): 요청 바디 데이터 (JSON 직렬화).

        Returns:
            Any: 파싱된 응답 데이터.

        Raises:
            NetworkError: 네트워크 연결 실패, 타임아웃, 4xx/5xx 에러 시 발생.
        """
        session = await self._get_session()
        try:
            async with session.post(url, headers=headers, json=data) as response:
                return await self._handle_response(response, url, "POST")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.logger.error(f"[POST] Request Failed | URL: {url} | Error: {str(e)}")
            raise NetworkError(f"POST {url} failed: {str(e)}") from e

    async def _handle_response(
        self, 
        response: aiohttp.ClientResponse, 
        url: str, 
        method: str
    ) -> Any:
        """HTTP 응답을 검증하고 안전하게 파싱합니다.

        Args:
            response (aiohttp.ClientResponse): 원본 응답 객체.
            url (str): 디버깅용 요청 URL.
            method (str): 디버깅용 요청 메서드.

        Returns:
            Any: 파싱된 데이터 (JSON Dict or Text).

        Raises:
            NetworkError: HTTP Status >= 400.
        """
        # 1. HTTP Status 검사
        if response.status >= 400:
            error_body = await response.text()
            self.logger.warning(
                f"[{method}] HTTP Error | Status: {response.status} | URL: {url} | Body: {error_body[:200]}"
            )
            raise NetworkError(f"HTTP {response.status} on {method} {url}: {error_body}")

        # 2. 데이터 파싱 (JSON 우선, 실패 시 Text 반환)
        # Rationale: 헤더가 json이어도 바디가 비어있거나 형식이 잘못된 경우를 방어합니다.
        try:
            content_type = response.headers.get("Content-Type", "").lower()
            if "application/json" in content_type:
                return await response.json()
            return await response.text()
        except (ValueError, aiohttp.ContentTypeError) as e:
            self.logger.warning(
                f"[{method}] JSON Parsing Failed | URL: {url} | Error: {str(e)}. Falling back to text."
            )
            return await response.text()