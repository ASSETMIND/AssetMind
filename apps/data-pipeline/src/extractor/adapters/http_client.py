"""
HTTP 클라이언트 어댑터 (HTTP Client Adapter)

이 모듈은 aiohttp 라이브러리를 사용하여 비동기 HTTP 통신을 수행하는 어댑터입니다.
기존 requests 기반 로직을 비동기(Async/Await) 방식으로 전환하며,
도메인 계층의 IHttpClient 인터페이스를 준수하여 외부 라이브러리 의존성을 격리합니다.

주요 기능:
- AsyncIO 기반의 Non-blocking HTTP 요청 (GET, POST)
- Context Manager(async with) 지원을 통한 안전한 리소스 관리
- 세션(Session) 재사용을 통한 커넥션 풀링(Connection Pooling) 최적화
- 타임아웃 및 에러 핸들링의 중앙화 (Domain Exception 변환)
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