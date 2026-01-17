import pytest
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from unittest.mock import MagicMock, AsyncMock, patch

from src.extractor.adapters.http_client import AsyncHttpAdapter
from src.extractor.domain.exceptions import NetworkError

# --------------------------------------------------------------------------
# 1. Mock Objects & Fixtures (테스트 환경 구성)
# --------------------------------------------------------------------------

@pytest.fixture
def mock_logger():
    """
    [LogManager Mocking]
    실제 LogManager는 초기화 시 YAML 설정 파일을 읽으려 시도합니다.
    단위 테스트 환경에서는 설정 파일이 없거나 경로가 다를 수 있으므로(FileNotFoundError),
    LogManager 전체를 Mocking하여 로깅 로직을 무력화하고 테스트 속도를 높입니다.
    """
    # AsyncHttpAdapter가 임포트하고 있는 LogManager 클래스를 가로챕니다.
    with patch("src.extractor.adapters.http_client.LogManager") as mock_log_mgr:
        logger_instance = MagicMock()
        mock_log_mgr.get_logger.return_value = logger_instance
        yield logger_instance

@pytest.fixture
def mock_response():
    """
    [aiohttp.ClientResponse Mocking]
    HTTP 응답 객체의 행동을 모방합니다.
    .json(), .text() 등의 메서드는 비동기(awaitable)여야 하므로 AsyncMock을 사용합니다.
    """
    response = MagicMock(spec=aiohttp.ClientResponse)
    response.status = 200
    response.headers = {"Content-Type": "application/json"}
    
    # await response.json() 호출 대응
    response.json = AsyncMock(return_value={"key": "value"})
    # await response.text() 호출 대응
    response.text = AsyncMock(return_value='{"key": "value"}')
    # await response.read() 호출 대응
    response.read = AsyncMock(return_value=b'{"key": "value"}')
    
    return response

@pytest.fixture
def mock_session(mock_response):
    """
    [aiohttp.ClientSession Mocking]
    세션 객체와 Context Manager(async with) 패턴을 모방합니다.
    
    [Note on Spec]
    여기서 `spec=aiohttp.ClientSession`을 사용하면, 추후 `patch`와 충돌하여
    'InvalidSpecError'가 발생할 수 있으므로 spec 인자를 제외하고 순수 MagicMock을 사용합니다.
    """
    session = MagicMock()
    session.closed = False
    
    # async with session.get(...) as response: 구문을 처리하기 위한 모킹
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=mock_response)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    
    # get, post 메서드가 호출되면 위에서 만든 Context Manager를 반환
    session.get.return_value = context_manager
    session.post.return_value = context_manager
    
    # close 메서드 호출 시 실제 속성 변경
    async def close_side_effect():
        session.closed = True
    session.close = AsyncMock(side_effect=close_side_effect)
    
    return session

@pytest.fixture
def adapter(mock_session, mock_logger):
    """
    [Target Under Test: AsyncHttpAdapter]
    테스트 대상 인스턴스를 생성합니다.
    
    1. `aiohttp.ClientSession` 생성자를 `mock_session`으로 패치하여 실제 네트워크 연결 차단.
    2. `mock_logger`를 주입하여 설정 파일 로딩 에러 방지.
    """
    # 클래스 내부에서 aiohttp.ClientSession()이 호출될 때 mock_session을 반환하도록 설정
    with patch("aiohttp.ClientSession", return_value=mock_session):
        adapter_instance = AsyncHttpAdapter(timeout=10)
        yield adapter_instance

# --------------------------------------------------------------------------
# 2. Test Cases (테스트 시나리오)
# --------------------------------------------------------------------------

class TestAsyncHttpAdapter:
    """AsyncHttpAdapter의 모든 동작(정상, 예외, 상태 관리)을 검증하는 테스트 스위트"""

    # ==========================================
    # Category 1: Happy Path (정상 흐름)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc001_get_success_json(self, adapter, mock_session, mock_response):
        """[TC-001] GET 요청 성공 시 JSON 데이터가 Dict로 파싱되어 반환되어야 한다."""
        # Given: 서버가 {"id": 1, "name": "test"} JSON을 반환한다고 가정
        url = "http://test.com/json"
        mock_response.json.return_value = {"id": 1, "name": "test"}
        
        # When: Adapter의 get 메서드 호출
        result = await adapter.get(url)
        
        # Then: 결과값 검증 및 내부 세션 호출 확인
        assert result == {"id": 1, "name": "test"}
        mock_session.get.assert_called_once()
        
        # 호출 시 사용된 URL 검증
        args, _ = mock_session.get.call_args
        assert args[0] == url

    @pytest.mark.asyncio
    async def test_tc002_post_success_data(self, adapter, mock_session, mock_response):
        """[TC-002] POST 요청 시 Payload가 올바르게 전송되고 응답이 처리되어야 한다."""
        # Given
        url = "http://test.com/post"
        payload = {"data": "secure"}
        mock_response.status = 201
        
        # When
        await adapter.post(url, data=payload)
        
        # Then: post 메서드 호출 시 'json' 파라미터로 데이터가 전달되었는지 확인
        mock_session.post.assert_called_once()
        _, kwargs = mock_session.post.call_args
        assert kwargs['json'] == payload

    @pytest.mark.asyncio
    async def test_tc003_context_manager_lifecycle(self, adapter, mock_session):
        """[TC-003] async with 구문을 사용할 때 세션이 생성되고, 종료 시 닫혀야 한다."""
        # When: Context Manager 진입 및 탈출
        async with adapter as client:
            # 진입(Enter): 세션이 생성되어 있어야 함
            assert client._session is not None
            assert client._session is mock_session
        
        # Then: 탈출(Exit): 세션의 close()가 호출되어야 함
        mock_session.close.assert_called_once()
        assert mock_session.closed is True

    @pytest.mark.asyncio
    async def test_tc004_text_response(self, adapter, mock_response):
        """[TC-004] Content-Type이 JSON이 아닌 경우(text/html), 텍스트 원문을 반환해야 한다."""
        # Given
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text.return_value = "<html>body</html>"
        
        # When
        result = await adapter.get("http://test.com/html")
        
        # Then: JSON 파싱을 시도하지 않고 Text 반환 확인
        assert result == "<html>body</html>"
        mock_response.json.assert_not_called()

    # ==========================================
    # Category 2: Boundary Analysis (경계값)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc006_malformed_json_fallback(self, adapter, mock_response):
        """[TC-006] 헤더는 JSON이지만 본문이 깨져있는 경우, 에러 없이 Text로 Fallback 해야 한다."""
        # Given
        mock_response.headers = {"Content-Type": "application/json"}
        # json() 호출 시 파싱 에러(ValueError) 발생 시뮬레이션
        mock_response.json.side_effect = ValueError("Expecting value")
        mock_response.text.return_value = "{invalid_json}"
        
        # When
        result = await adapter.get("http://test.com/bad")
        
        # Then
        assert result == "{invalid_json}"

    @pytest.mark.asyncio
    async def test_tc008_optional_params_none(self, adapter, mock_session):
        """[TC-008] headers나 params가 None으로 들어와도 내부 로직이 깨지지 않아야 한다."""
        # Given
        url = "http://test.com/none"
        
        # When
        await adapter.get(url, headers=None, params=None)
        
        # Then: None 그대로 aiohttp에 전달됨 (aiohttp는 이를 허용함)
        mock_session.get.assert_called_once()
        _, kwargs = mock_session.get.call_args
        assert kwargs['headers'] is None
        assert kwargs['params'] is None

    # ==========================================
    # Category 3: Exception Handling (예외 처리)
    # ==========================================

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [400, 404, 500, 503])
    async def test_tc010_http_error_handling(self, adapter, mock_response, status_code):
        """[TC-010, TC-011] HTTP 4xx, 5xx 응답은 도메인 예외인 NetworkError로 변환되어야 한다."""
        # Given
        mock_response.status = status_code
        mock_response.text.return_value = "Error Message"
        
        # When & Then: pytest.raises로 예외 발생 검증
        with pytest.raises(NetworkError) as exc_info:
            await adapter.get("http://test.com/error")
        
        # 예외 메시지에 상태 코드와 서버 메시지가 포함되어 있는지 확인
        assert str(status_code) in str(exc_info.value)
        assert "Error Message" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_tc012_connection_error(self, adapter, mock_session):
        """
        [TC-012] DNS 실패나 서버 다운 같은 물리적 연결 실패 시 NetworkError로 변환되어야 한다.
        [Fix Info] aiohttp.ClientConnectorError는 __str__ 호출 시 내부의 ssl 속성을 참조합니다.
        Mock 객체 생성 시 이를 처리해주지 않으면 AttributeError가 발생하므로, ssl 속성을 가진 더미 키를 주입합니다.
        """
        # Given
        mock_conn_key = MagicMock()
        mock_conn_key.ssl = False  # AttributeError 방지용 더미 속성
        
        conn_err = aiohttp.ClientConnectorError(
            connection_key=mock_conn_key, 
            os_error=OSError("Server Down")
        )
        mock_session.get.side_effect = conn_err
        
        # When & Then
        with pytest.raises(NetworkError) as exc_info:
            await adapter.get("http://test.com/conn-err")
        
        assert "Server Down" in str(exc_info.value) or "failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_tc013_timeout_error(self, adapter, mock_session):
        """[TC-013] 요청 타임아웃(asyncio.TimeoutError) 발생 시 NetworkError로 변환되어야 한다."""
        # Given
        mock_session.get.side_effect = asyncio.TimeoutError
        
        # When & Then
        with pytest.raises(NetworkError) as exc_info:
            await adapter.get("http://test.com/timeout")
            
        assert "failed" in str(exc_info.value)

    # ==========================================
    # Category 4: State & Resource (상태 관리)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc014_session_reuse(self, adapter, mock_session):
        """[TC-014] Connection Pooling을 위해 연속된 요청은 동일한 세션 객체를 재사용해야 한다."""
        # When: 두 번의 요청 수행
        await adapter.get("http://url1")
        session_id_1 = id(adapter._session)
        
        await adapter.post("http://url2")
        session_id_2 = id(adapter._session)
        
        # Then: 세션 객체의 메모리 주소(ID)가 같아야 함
        assert session_id_1 == session_id_2
        assert adapter._session is mock_session

    @pytest.mark.asyncio
    async def test_tc015_auto_reconnect(self, adapter, mock_session):
        """
        [TC-015] 세션이 만료되거나 닫힌 상태(closed=True)라면, 다음 요청 시 자동으로 새 세션을 생성해야 한다.
        [Fix Info] 이미 Fixture 단계에서 aiohttp.ClientSession이 Patch 되어 있으므로,
        여기서 MagicMock에 spec을 지정하면 'InvalidSpecError'가 발생합니다. 단순 MagicMock을 사용합니다.
        """
        # Given: 현재 세션이 닫혀있다고 설정
        adapter._session = mock_session
        mock_session.closed = True
        
        # When: 새로운 요청 시도
        # aiohttp.ClientSession()이 다시 호출될 것이므로, 이를 가로채서 새 Mock 세션을 반환하게 함
        with patch("aiohttp.ClientSession") as mock_cls_new:
            new_session_mock = MagicMock() # spec 제거하여 충돌 방지
            new_session_mock.closed = False
            
            # 새 세션의 get 메서드 Mocking
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(return_value=MagicMock(status=200))
            cm.__aexit__ = AsyncMock()
            new_session_mock.get.return_value = cm
            
            mock_cls_new.return_value = new_session_mock
            
            await adapter.get("http://test.com/reconnect")
            
            # Then
            mock_cls_new.assert_called() # 새 세션 생성자가 호출되었는지
            assert adapter._session is new_session_mock # 어댑터 내부 세션이 새 것으로 교체되었는지