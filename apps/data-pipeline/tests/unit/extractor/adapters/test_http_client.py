import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

# 실제 파일 경로에 맞게 Import
from src.extractor.adapters.http_client import AsyncHttpAdapter
from src.common.exceptions import NetworkConnectionError

# ========================================================================================
# [Fixtures] 테스트 환경 설정 및 Mocking
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_external_deps():
    """모든 테스트에 공통적으로 적용되는 Mock 설정"""
    with patch("src.extractor.adapters.http_client.LogManager.get_logger") as mock_logger, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        yield

@pytest.fixture
def mock_session():
    """aiohttp.ClientSession 동작 모방"""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.closed = False
    session.close = AsyncMock()
    
    mock_response = AsyncMock(spec=aiohttp.ClientResponse)
    mock_response.status = 200
    mock_response.headers = {}
    mock_response.json = AsyncMock(return_value={})
    mock_response.text = AsyncMock(return_value="")
    mock_response.__aenter__.return_value = mock_response
    mock_response.__aexit__.return_value = None

    session.get.return_value = mock_response
    session.post.return_value = mock_response
    return session

@pytest.fixture
def adapter(mock_session):
    """ClientSession 생성을 Mocking하여 주입한 AsyncHttpAdapter 인스턴스"""
    with patch("src.extractor.adapters.http_client.aiohttp.ClientSession", return_value=mock_session):
        adapter_instance = AsyncHttpAdapter(timeout=30)
        yield adapter_instance

# ========================================================================================
# 1. 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_default_config():
    """[INIT-01] 기본 설정으로 초기화 시 타임아웃 30초 설정 확인"""
    adapter = AsyncHttpAdapter()
    assert adapter.timeout.total == 30
    assert adapter._session is None

def test_init_02_custom_config():
    """[INIT-02] 사용자 정의 타임아웃(60초) 설정 확인 (BVA)"""
    adapter = AsyncHttpAdapter(timeout=60)
    assert adapter.timeout.total == 60

# ========================================================================================
# 2. 생명주기 테스트 (Lifecycle)
# ========================================================================================

@pytest.mark.asyncio
async def test_life_01_context_manager(adapter, mock_session):
    """[LIFE-01] Context Manager(async with) 진입/탈출 시 세션 생성 및 종료 검증"""
    mock_session.close.return_value = None 

    async with adapter as active_adapter:
        assert active_adapter._session is mock_session
        assert not mock_session.close.called
    
    mock_session.close.assert_called_once()

@pytest.mark.asyncio
async def test_life_02_lazy_loading(adapter, mock_session):
    """[LIFE-02] 초기 상태에서 _get_session 호출 시 새로운 세션 생성"""
    adapter._session = None
    session = await adapter._get_session()
    
    assert session is mock_session
    assert adapter._session is mock_session

@pytest.mark.asyncio
async def test_life_03_session_pooling(adapter, mock_session):
    """[LIFE-03] 이미 세션이 존재하면 기존 세션을 재사용 (Pooling)"""
    await adapter._get_session() 
    existing_session_id = id(adapter._session)
    
    session = await adapter._get_session() 
    
    assert id(session) == existing_session_id

@pytest.mark.asyncio
async def test_life_04_resurrection(adapter, mock_session):
    """[LIFE-04] 세션이 닫힌(closed) 상태라면 새로 생성하여 복구"""
    old_session = MagicMock() 
    old_session.closed = True
    adapter._session = old_session
    
    new_session = await adapter._get_session()
    
    assert new_session is not old_session
    assert new_session is mock_session 
    assert not new_session.closed

@pytest.mark.asyncio
async def test_life_05_close_idempotency(adapter, mock_session):
    """[LIFE-05] close() 메서드의 멱등성 검증"""
    adapter._session = None
    await adapter.close() # No Error
    
    mock_session.closed = True
    adapter._session = mock_session
    await adapter.close()
    
    mock_session.close.assert_not_called()

# ========================================================================================
# 3. 요청 처리 테스트 (Request Handling)
# ========================================================================================

@pytest.mark.asyncio
async def test_req_01_get_args(adapter, mock_session):
    """[REQ-01] GET 요청 시 URL, Header, Params가 올바르게 전달되는지 검증"""
    url = "https://api.test.com/data"
    headers = {"Auth": "Token"}
    params = {"q": "search"}
    
    await adapter.get(url, headers=headers, params=params)
    mock_session.get.assert_called_once_with(url, headers=headers, params=params)

@pytest.mark.asyncio
async def test_req_02_post_args(adapter, mock_session):
    """[REQ-02] POST 요청 시 URL, Header, JSON Data가 올바르게 전달되는지 검증"""
    url = "https://api.test.com/submit"
    data = {"key": "value"}
    
    await adapter.post(url, data=data)
    mock_session.post.assert_called_once_with(url, headers=None, json=data)

# ========================================================================================
# 4. 데이터 파싱 및 MC/DC 테스트 (Data Parsing & Robustness)
# ========================================================================================

@pytest.mark.asyncio
async def test_data_01_json_parsing(adapter, mock_session):
    """[DATA-01] 응답 헤더가 JSON이고 바디가 유효하면 Dict 반환"""
    mock_resp = mock_session.get.return_value.__aenter__.return_value
    mock_resp.headers = {"Content-Type": "application/json; charset=utf-8"}
    mock_resp.json.return_value = {"result": "success"}
    
    result = await adapter.get("url")
    assert result == {"result": "success"}

@pytest.mark.asyncio
async def test_data_02_text_parsing(adapter, mock_session):
    """[DATA-02] 응답 헤더가 JSON이 아니면 Text 반환"""
    mock_resp = mock_session.get.return_value.__aenter__.return_value
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.text.return_value = "<html>OK</html>"
    
    result = await adapter.get("url")
    assert result == "<html>OK</html>"

@pytest.mark.asyncio
async def test_data_03_mcdc_broken_json(adapter, mock_session):
    """[DATA-03] [MC/DC] 헤더는 JSON이나 바디가 깨진 경우 -> Text 반환 (Fail-Safe)"""
    mock_resp = mock_session.get.return_value.__aenter__.return_value
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.json.side_effect = ValueError("Broken JSON")
    mock_resp.text.return_value = "{broken:"
    
    result = await adapter.get("url")
    assert result == "{broken:" 

@pytest.mark.asyncio
async def test_data_04_mcdc_missing_header(adapter, mock_session):
    """[DATA-04] [MC/DC] Content-Type 헤더가 아예 없는 경우 -> Text 반환"""
    mock_resp = mock_session.get.return_value.__aenter__.return_value
    mock_resp.headers = {} 
    mock_resp.text.return_value = "Just Text"
    
    result = await adapter.get("url")
    assert result == "Just Text"

# ========================================================================================
# 5. 에러 핸들링 테스트 (Error Handling)
# ========================================================================================

@pytest.mark.asyncio
async def test_err_01_http_404(adapter, mock_session):
    """[ERR-01] HTTP 404 응답 시 NetworkConnectionError 발생"""
    mock_resp = mock_session.get.return_value.__aenter__.return_value
    mock_resp.status = 404
    mock_resp.text.return_value = "Not Found"
    
    with pytest.raises(NetworkConnectionError) as exc_info:
        await adapter.get("url")
    
    assert "404" in str(exc_info.value)

@pytest.mark.asyncio
async def test_err_02_http_500(adapter, mock_session):
    """[ERR-02] HTTP 500 응답 시 NetworkConnectionError 발생"""
    mock_resp = mock_session.post.return_value.__aenter__.return_value
    mock_resp.status = 500
    mock_resp.text.return_value = "Server Error"
    
    with pytest.raises(NetworkConnectionError) as exc_info:
        await adapter.post("url")
    assert "500" in str(exc_info.value)

@pytest.mark.asyncio
async def test_err_03_connection_error_get(adapter, mock_session):
    """[ERR-03] GET 연결 실패 시 NetworkConnectionError로 래핑"""
    mock_session.get.side_effect = aiohttp.ClientConnectorError(
        connection_key=MagicMock(), os_error=OSError("Refused")
    )
    
    with pytest.raises(NetworkConnectionError) as exc_info:
        await adapter.get("url")
    assert "failed" in str(exc_info.value)

@pytest.mark.asyncio
async def test_err_04_timeout_error(adapter, mock_session):
    """[ERR-04] 타임아웃 시 NetworkConnectionError로 래핑"""
    mock_session.get.side_effect = asyncio.TimeoutError
    
    with pytest.raises(NetworkConnectionError) as exc_info:
        await adapter.get("url")
    assert "failed" in str(exc_info.value)

@pytest.mark.asyncio
async def test_err_05_post_connection_error(adapter, mock_session):
    """[ERR-05] POST 연결 실패(ClientError) 시 NetworkConnectionError로 래핑 검증 (Missing Line Coverage)"""
    # Given
    mock_session.post.side_effect = aiohttp.ClientError("Post Failed")
    
    # When & Then
    with pytest.raises(NetworkConnectionError) as exc_info:
        await adapter.post("https://api.test.com/submit", data={"k": "v"})
        
    assert "POST" in str(exc_info.value)
    assert "Post Failed" in str(exc_info.value)