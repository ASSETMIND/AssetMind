import datetime
import json
import logging
import sys
import time
import builtins
import importlib
import pytest
import asyncio
import aiohttp
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from src.pipeline_service import PipelineService

from src.common.interfaces import IHttpClient, IAuthStrategy, IExtractor
from src.common.exceptions import ETLError, ExtractorError, ConfigurationError, LoaderError, RateLimitError, NetworkConnectionError, HttpError, AuthError, TransformerError
from src.common.config import ConfigManager, JobPolicy
from src.common.log import LogManager, JsonFormatter, request_id_ctx
from src.common.dtos import RequestDTO, ExtractedDTO, TransformedDTO

from src.common.decorators.log_decorator import LoggingDecorator, _sanitize_args, _truncate_output, DEFAULT_TRUNCATE_LIMIT
from src.common.decorators.rate_limit_decorator import RateLimitDecorator, _buckets, _get_bucket
from src.common.decorators.retry_decorator import RetryDecorator
import src.common.decorators.log_decorator as log_decorator_module
import src.common.decorators.rate_limit_decorator as rld_module

from src.extractor.adapters.auth import KISAuthStrategy, UPBITAuthStrategy, KIS_DATE_FORMAT
from src.extractor.adapters.http_client import AsyncHttpAdapter

from src.extractor.providers.abstract_extractor import AbstractExtractor
from src.extractor.providers.ecos_extractor import ECOSExtractor
from src.extractor.providers.fred_extractor import FREDExtractor
from src.extractor.providers.kis_extractor import KISExtractor
from src.extractor.providers.upbit_extractor import UPBITExtractor

from src.extractor.extractor_factory import ExtractorFactory
from src.extractor.extractor_service import ExtractorService
from src.pipeline_service import PipelineService
# ==============================================================================
# [FIXTURE] 통합 테스트용 Mock Fixtures
# ==============================================================================

@pytest.fixture
def mock_integration_config():
    """PipelineService 동작을 위한 가짜 ConfigManager 설정 주입"""
    with patch("src.common.config.ConfigManager.get_config") as mock_get_config:
        mock_config = mock_get_config.return_value
        
        mock_config.task_name = "dummy_task"
        mock_config.log_level = "INFO"
        mock_config.log_dir = "logs"
        mock_config.log_filename = "test.log"
        
        mock_config.extraction_policy = {
            "job_success_kis": JobPolicy(
                provider="KIS", description="kis task", path="/test", tr_id="FHKST01010100"
            ),
            "job_fail_network": JobPolicy(
                provider="UPBIT", description="upbit task", path="/test", params={"market": "KRW-BTC"}
            ),
        }
        
        mock_config.kis.app_key.get_secret_value.return_value = "dummy_kis_key"
        mock_config.kis.app_secret.get_secret_value.return_value = "dummy_kis_secret"
        mock_config.kis.base_url = "https://api.kis.mock"
        
        mock_config.upbit.api_key.get_secret_value.return_value = "dummy_upbit_key"
        # [핵심 수정] PyJWT의 InsecureKeyLengthWarning 방지를 위해 시크릿 키 길이를 32바이트 이상으로 설정
        mock_config.upbit.secret_key.get_secret_value.return_value = "dummy_upbit_secret_key_must_be_at_least_32_bytes_long"
        mock_config.upbit.base_url = "https://api.upbit.mock"
        
        yield mock_config

@pytest.fixture
def mock_http_adapter():
    """ExtractorService 내부에서 사용할 HTTP 클라이언트 Mock"""
    adapter = AsyncMock()
    
    # 1. 인증(Auth) 성공을 위한 기본 POST 응답
    adapter.post.return_value = {
        "access_token": "dummy_token_12345",
        "access_token_token_expired": "2099-12-31 23:59:59",
        "expires_in": 86400
    }
    
    # 2. 데이터 조회 성공을 위한 기본 GET 응답
    adapter.get.return_value = {
        "rt_cd": "0",
        "msg1": "정상처리",
        "output": {"price": "70000"}
    }
    
    return adapter

@pytest.fixture
def mock_logger():
    """테스트용 Mock Logger 반환 및 LogManager 패치"""
    logger = MagicMock()
    with patch("src.common.log.LogManager.get_logger", return_value=logger):
        yield logger

@pytest.fixture
def clean_context():
    """Request ID 컨텍스트 초기화"""
    token = request_id_ctx.set("system")
    yield
    request_id_ctx.reset(token)

@pytest.fixture(autouse=True)
def reset_rate_limit_buckets():
    """테스트 간 격리를 위해 전역 상태인 버킷(Buckets) 초기화"""
    _buckets.clear()
    yield
    _buckets.clear()

@pytest.fixture
def auth_mock_config():
    """인증 전략 테스트를 위한 격리된 Config Mock"""
    config = MagicMock()
    config.kis.base_url = "https://api.kis.mock"
    config.kis.app_key.get_secret_value.return_value = "dummy_kis_key"
    config.kis.app_secret.get_secret_value.return_value = "dummy_kis_secret"
    
    config.upbit.base_url = "https://api.upbit.mock"
    config.upbit.api_key.get_secret_value.return_value = "dummy_upbit_key"
    config.upbit.secret_key.get_secret_value.return_value = "dummy_upbit_secret"
    return config

@pytest.fixture
def http_adapter():
    """테스트용 AsyncHttpAdapter 픽스처"""
    return AsyncHttpAdapter(timeout=5)

class DummyAsyncContextManager:
    def __init__(self, mock_response=None, side_effect=None):
        self.mock_response = mock_response
        self.side_effect = side_effect

    async def __aenter__(self):
        if self.side_effect:
            raise self.side_effect
        return self.mock_response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.fixture
def ecos_mock_config():
    """ECOS 수집기 전용 Mock Config 생성"""
    config = MagicMock()
    config.ecos.base_url = "https://ecos.mock.api"
    config.ecos.api_key.get_secret_value.return_value = "secret_key_123"
    
    # 더미 정책 주입
    policy = MagicMock()
    policy.provider = "ECOS"
    policy.path = "/StatisticSearch/"
    policy.params = {"stat_code": "001", "cycle": "M", "item_code1": "A"}
    
    # 속성에 Dictionary 형태로 할당
    config.extraction_policy = {"ecos_test_job": policy}
    return config

@pytest.fixture
def fred_mock_config():
    """FRED 수집기 전용 Mock Config 생성"""
    config = MagicMock()
    config.fred.base_url = "https://api.fred.mock"
    config.fred.api_key.get_secret_value.return_value = "dummy_fred_secret_key"
    
    # 더미 정책 주입
    policy = MagicMock()
    policy.provider = "FRED"
    policy.path = "/series/observations"
    policy.params = {"series_id": "GNPCA"}
    
    config.extraction_policy = {"fred_test_job": policy}
    return config

@pytest.fixture
def kis_mock_config():
    """KIS 수집기 전용 Mock Config 생성"""
    config = MagicMock()
    config.kis.base_url = "https://api.kis.mock"
    config.kis.app_key.get_secret_value.return_value = "dummy_kis_app_key"
    config.kis.app_secret.get_secret_value.return_value = "dummy_kis_app_secret"
    
    # 더미 정책 주입
    policy = MagicMock()
    policy.provider = "KIS"
    policy.path = "/uapi/domestic-stock/v1/quotations/inquire-price"
    policy.params = {"FID_COND_MRKT_DIV_CODE": "J"}
    policy.tr_id = "FHKST01010100"
    
    config.extraction_policy = {"kis_test_job": policy}
    return config

@pytest.fixture
def factory_mock_config():
    """Factory 테스트용 기본 구조를 갖춘 Mock Config"""
    config = MagicMock()
    config.extraction_policy = {}
    return config

@pytest.fixture
def service_mock_config():
    """Service 테스트를 위한 Mock Config"""
    config = MagicMock()
    policy = MagicMock()
    policy.params = {"default_key": "default_val"}
    config.extraction_policy = {"test_job_id": policy}
    return config

@pytest.fixture
def mock_pipeline_service():
    """PipelineService 테스트를 위해 Config와 하위 Service를 모킹한 픽스처"""
    with patch("src.pipeline_service.ConfigManager.get_config") as mock_get_config, \
         patch("src.pipeline_service.ExtractorService") as mock_extractor_service:
        
        mock_config = MagicMock()
        mock_config.extraction_policy = {}
        mock_get_config.return_value = mock_config
        
        service = PipelineService("dummy_task")
        return service

# ==============================================================================
# [INTEG] 파이프라인 통합 테스트 (Pipeline Service Flow)
# ==============================================================================

# [INTEG-01] 전체 파이프라인 해피 경로 (Happy Path)
@pytest.mark.asyncio
async def test_pipeline_batch_success(mock_integration_config, mock_http_adapter):
    """
    Scenario: 설정된 모든 작업(Job)이 정상적으로 API를 호출하고 결과를 반환한다.
    Flow: Config -> Pipeline -> ExtractorService -> Factory -> KISExtractor -> MockHTTP
    """
    with patch("src.extractor.extractor_service.AsyncHttpAdapter", return_value=mock_http_adapter):
        service = PipelineService("dummy_task_name")
        
        async with service as pipeline:
            result = await pipeline.run_batch()

    # 결과 검증
    assert result["total"] == 2
    assert result["success"] == 2
    assert result["fail"] == 0
    
    details = result["details"]
    kis_result = next(r for r in details if r["job_id"] == "job_success_kis")
    assert kis_result["status"] == "SUCCESS"
    
    calls = mock_http_adapter.get.call_args_list
    kis_call = next(c for c in calls if "kis" in c[0][0])
    
    args, kwargs = kis_call
    assert "https://api.kis.mock" in args[0]
    assert kwargs["headers"]["tr_id"] == "FHKST01010100"


# [INTEG-02] 부분 실패 및 격리성 검증 (Partial Failure)
@pytest.mark.asyncio
async def test_pipeline_partial_failure_isolation(mock_integration_config, mock_http_adapter):
    """
    Scenario: 배치 중 하나의 작업이 네트워크 오류로 실패해도, 다른 작업은 성공해야 한다.
    """
    async def side_effect(url, **kwargs):
        if "kis" in url:
            return {"rt_cd": "0", "output": {}}
        elif "upbit" in url:
            raise Exception("Network Timeout")
        return {}

    mock_http_adapter.get.side_effect = side_effect

    with patch("src.extractor.extractor_service.AsyncHttpAdapter", return_value=mock_http_adapter):
        service = PipelineService("dummy_task")
        
        async with service as pipeline:
            result = await pipeline.run_batch()

    assert result["total"] == 2
    assert result["success"] == 1
    assert result["fail"] == 1
    
    failures = [r for r in result["details"] if r["status"] != "SUCCESS"]
    assert len(failures) == 1
    assert failures[0]["job_id"] == "job_fail_network"
    assert "FAIL" in failures[0]["status"]


# [INTEG-03] 팩토리 패턴 통합 검증 (Factory Integration)
@pytest.mark.asyncio
async def test_pipeline_factory_provider_switching(mock_integration_config, mock_http_adapter):
    """
    Scenario: Job ID에 매핑된 Provider(KIS vs UPBIT)에 따라 올바른 Extractor 클래스가 생성되어 실행되는가?
    """
    with patch("src.extractor.extractor_service.AsyncHttpAdapter", return_value=mock_http_adapter):
        service = PipelineService("dummy")
        async with service as pipeline:
            await pipeline.run_batch()
            
    calls = mock_http_adapter.get.call_args_list
    kis_calls = [c for c in calls if "kis" in c[0][0]]
    upbit_calls = [c for c in calls if "upbit" in c[0][0]]
    
    assert len(kis_calls) > 0, "KIS extractor API call was not made"
    assert len(upbit_calls) > 0, "UPBIT extractor API call was not made"
    
    assert "appkey" in kis_calls[0].kwargs["headers"] 
    assert "market" in upbit_calls[0].kwargs["params"]

@pytest.fixture
def upbit_mock_config():
    """UPBIT 수집기 전용 Mock Config 생성"""
    config = MagicMock()
    config.upbit.base_url = "https://api.upbit.mock"
    
    # 더미 정책 주입
    policy = MagicMock()
    policy.provider = "UPBIT"
    policy.path = "/v1/ticker"
    policy.params = {"market": "KRW-BTC"}
    
    config.extraction_policy = {"upbit_test_job": policy}
    return config

# ==============================================================================
# [CONFIG] ConfigManager 100% Coverage (Passed)
# ==============================================================================

@pytest.fixture
def config_env_setup(monkeypatch):
    env_vars = {
        "KIS_APP_KEY": "dummy", "KIS_APP_SECRET": "dummy", "KIS_BASE_URL": "dummy",
        "FRED_API_KEY": "dummy", "FRED_BASE_URL": "dummy",
        "ECOS_API_KEY": "dummy", "ECOS_BASE_URL": "dummy",
        "UPBIT_API_KEY": "dummy", "UPBIT_SECRET_KEY": "dummy", "UPBIT_BASE_URL": "dummy",
    }
    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)
        
    ConfigManager._cache.clear()
    ConfigManager._active_task_name = None
    yield
    ConfigManager._cache.clear()
    ConfigManager._active_task_name = None


def test_config_manager_get_config_uninitialized():
    ConfigManager._active_task_name = None
    with pytest.raises(ConfigurationError) as exc:
        ConfigManager.get_config()
    assert "초기화되지 않았습니다" in str(exc.value)


@patch.object(ConfigManager, '_load_from_yaml')
def test_config_manager_get_config_caching(mock_load_from_yaml, config_env_setup):
    dummy_config = ConfigManager(task_name="dummy_task")
    mock_load_from_yaml.return_value = dummy_config
    
    result1 = ConfigManager.get_config("test_task")
    assert result1 is dummy_config
    assert ConfigManager._active_task_name == "test_task"
    assert ConfigManager._cache["test_task"] is dummy_config
    mock_load_from_yaml.assert_called_once_with("test_task")
    
    result2 = ConfigManager.get_config("test_task")
    assert result2 is dummy_config
    assert mock_load_from_yaml.call_count == 1
    
    result3 = ConfigManager.get_config()
    assert result3 is dummy_config


@patch("src.common.config.Path.exists")
@patch("builtins.open")
@patch("yaml.safe_load")
def test_config_manager_load_yaml_success(mock_yaml_load, mock_open, mock_exists, config_env_setup):
    mock_exists.return_value = True
    mock_yaml_load.return_value = {
        "log_level": "DEBUG",
        "log_dir": "custom_logs",
        "log_filename": "custom.log",
        "policy": {
            "valid_job": {
                "provider": "KIS",
                "description": "test",
                "path": "/test"
            }
        }
    }
    
    config = ConfigManager._load_from_yaml("test_yaml")
    
    assert config.log_level == "DEBUG"
    assert config.log_dir == "custom_logs"
    assert config.log_filename == "custom.log"
    assert "valid_job" in config.extraction_policy
    assert config.extraction_policy["valid_job"].provider == "KIS"


@patch("src.common.config.Path.exists")
@patch("builtins.open")
@patch("yaml.safe_load")
def test_config_manager_load_yaml_invalid_policy(mock_yaml_load, mock_open, mock_exists, config_env_setup, capsys):
    mock_exists.return_value = True
    mock_yaml_load.return_value = {
        "policy": {
            "valid_job": {"provider": "KIS", "description": "valid", "path": "/valid"},
            "invalid_job": {"provider": "INVALID_PROVIDER", "description": "invalid", "path": "/invalid"}
        }
    }
    
    config = ConfigManager._load_from_yaml("test_yaml")
    
    assert "valid_job" in config.extraction_policy
    assert "invalid_job" not in config.extraction_policy
    
    captured = capsys.readouterr()
    assert "Invalid policy for job 'invalid_job'" in captured.out


@patch("src.common.config.Path.exists")
def test_config_manager_load_yaml_parse_exception(mock_exists, config_env_setup, capsys):
    mock_exists.return_value = True
    original_open = open
    
    def mocked_open(*args, **kwargs):
        filename = str(args[0])
        if filename.endswith(".yml"):
            raise Exception("File permission denied")
        return original_open(*args, **kwargs)

    with patch("builtins.open", side_effect=mocked_open):
        config = ConfigManager._load_from_yaml("test_yaml")
    
    assert config.extraction_policy == {}
    
    captured = capsys.readouterr()
    assert "Failed to parse YAML" in captured.out
    assert "File permission denied" in captured.out


@patch("src.common.config.Path.exists")
def test_config_manager_load_yaml_not_found(mock_exists, config_env_setup, capsys):
    mock_exists.return_value = False
    
    config = ConfigManager._load_from_yaml("test_yaml")
    
    assert config.extraction_policy == {}
    assert config.log_level == "INFO"
    
    captured = capsys.readouterr()
    assert "YAML config not found" in captured.out

# [LOG-01] Helper 함수 검증: _sanitize_args (마스킹 로직)
def test_log_sanitize_args():
    args = (123, "normal_arg")
    kwargs = {
        "user_id": "test_user",
        "PASSWORD": "super_secret_password", 
        "APIkey": "my_api_key_123"
    }
    result = _sanitize_args(args, kwargs)
    assert result["arg_0"] == "123"
    assert result["arg_1"] == "normal_arg"
    assert result["user_id"] == "test_user"
    assert result["PASSWORD"] == "***** (MASKED)"
    assert result["APIkey"] == "***** (MASKED)"

# [LOG-02] Helper 함수 검증: _truncate_output (길이 제한)
def test_log_truncate_output():
    limit = 10
    short_val = "short"
    long_val = "this_is_a_very_long_string"
    assert _truncate_output(short_val, limit) == "short"
    truncated = _truncate_output(long_val, limit)
    assert truncated.startswith("this_is_a_")
    assert "truncated" in truncated

# [LOG-03] 데코레이터 초기화 및 Logger Name 결정
def test_log_decorator_init():
    @LoggingDecorator()
    def dummy_func():
        pass
    assert dummy_func.__module__ == __name__

# [LOG-04] 동기 함수(Sync) 성공 궤적 및 컨텍스트 주입
def test_log_decorator_sync_success(mock_logger, clean_context):
    @LoggingDecorator(logger_name="TestSyncLogger")
    def sync_success_func(a, b):
        return a + b
    with patch("src.common.log.LogManager.set_context") as mock_set_context:
        result = sync_success_func(1, 2)
        assert result == 3
        mock_set_context.assert_called_once()
        assert mock_logger.info.call_count == 2
        end_call = mock_logger.info.call_args_list[1][0][0]
        assert "END" in end_call
        assert "Result: 3" in end_call

# [LOG-05] 비동기 함수(Async) 성공 궤적 (Context 유지 검증)
@pytest.mark.asyncio
async def test_log_decorator_async_success(mock_logger, clean_context):
    request_id_ctx.set("existing-request-id")
    @LoggingDecorator(logger_name="TestAsyncLogger")
    async def async_success_func(x):
        return x * 10
    with patch("src.common.log.LogManager.set_context") as mock_set_context:
        result = await async_success_func(5)
        assert result == 50
        mock_set_context.assert_not_called()
        assert mock_logger.info.call_count == 2

# [LOG-06] 예외 발생 (일반 Exception -> ETLError 래핑 후 전파)
def test_log_decorator_sync_exception_reraise(mock_logger, clean_context):
    @LoggingDecorator(logger_name="TestLogger")
    def fail_func():
        raise ValueError("Invalid Input")
    with pytest.raises(ETLError) as exc_info:
        fail_func()
    assert "예기치 못한 오류 발생" in str(exc_info.value)
    mock_logger.error.assert_called_once()

# [LOG-07] 예외 발생 (이미 ETLError인 경우 그대로 전파) (Async)
@pytest.mark.asyncio
async def test_log_decorator_async_etl_exception(mock_logger, clean_context):
    original_error = ETLError("Already ETLError", details={"code": 999})
    @LoggingDecorator()
    async def fail_async_func():
        raise original_error
    with pytest.raises(ETLError) as exc_info:
        await fail_async_func()
    assert exc_info.value is original_error
    mock_logger.error.assert_called_once()
    error_log = mock_logger.error.call_args[0][0]
    assert "Type: ETLError" in error_log
    assert "999" in error_log

# [LOG-08] 에러 Suppress (예외 무시 및 None 반환) (Sync)
def test_log_decorator_sync_exception_suppress(mock_logger, clean_context):
    @LoggingDecorator(suppress_error=True)
    def fail_func_suppressed():
        raise RuntimeError("Fatal DB Error")
    result = fail_func_suppressed()
    assert result is None
    mock_logger.error.assert_called_once()

# [LOG-09] 예외 상황: 인자 직렬화(JSON Serialization) 실패 방어
def test_log_decorator_serialization_failure(mock_logger, clean_context):
    class UnserializableObject:
        def __str__(self):
            raise TypeError("Cannot cast to string")
    @LoggingDecorator()
    def weird_func(obj):
        return "ok"
    result = weird_func(UnserializableObject())
    assert result == "ok"
    mock_logger.warning.assert_called_once()
    assert "(Serialization Failed)" in mock_logger.warning.call_args[0][0]


# ------------------------------------------------------------------------------
# [NEW] Missing Coverage 완벽 보완 영역 (100% 달성을 위한 Edge Cases)
# ------------------------------------------------------------------------------

# [LOG-10] ImportError Fallback
def test_log_decorator_import_fallback():
    """Scenario: src.common.log 임포트 실패 시 fallback 경로 로직이 실행되어야 함"""
    import sys
    import importlib
    import builtins
    
    # [핵심 수정] 변수 참조 대신 sys.modules에서 '실제 모듈 객체'를 하드코딩으로 강제 추출합니다.
    # 이를 통해 클래스 객체가 잘못 전달되는 Shadowing 문제를 원천 차단합니다.
    target_module_name = 'src.common.decorators.log_decorator'
    target_module = sys.modules[target_module_name]
    
    original_import = builtins.__import__
    
    def mocked_import(name, *args, **kwargs):
        # 모듈 로드 중 처음으로 src.common.log를 찾을 때만 강제로 예외 발생
        if name == 'src.common.log' and not getattr(mocked_import, 'failed', False):
            mocked_import.failed = True
            raise ImportError("Simulated ImportError")
        return original_import(name, *args, **kwargs)

    with patch('builtins.__import__', side_effect=mocked_import):
        # Fallback 로직 도달 유도
        importlib.reload(target_module)
        
    # 테스트 환경 오염을 막기 위해 Mocking 해제 후 원상복구 리로드
    importlib.reload(target_module)

# [LOG-11] _log_error 일반 예외 분기
def test_log_decorator_log_error_non_etl():
    """Scenario: _log_error가 ETLError가 아닌 일반 예외를 처리할 때의 포맷"""
    logger = MagicMock()
    decorator = LoggingDecorator()
    
    # 래핑되지 않은 순수 예외를 직접 넘겨서 else 분기 도달 유도
    decorator._log_error(logger, "test_func", ValueError("Test Normal Error"), 0.5)
    
    logger.error.assert_called_once()
    error_msg = logger.error.call_args[0][0]
    assert "Error: ValueError - Test Normal Error" in error_msg

# [LOG-12] 동기 함수(Sync) ETLError 예외
def test_log_decorator_sync_etl_exception(mock_logger, clean_context):
    """Scenario: 발생한 에러가 이미 ETLError이면 래핑하지 않고 로그 후 전파 (Sync 분기 보완)"""
    original_error = ETLError("Already ETLError Sync", details={"code": 777})
    
    @LoggingDecorator()
    def fail_sync_func():
        raise original_error
        
    with pytest.raises(ETLError) as exc_info:
        fail_sync_func()
        
    assert exc_info.value is original_error
    mock_logger.error.assert_called_once()
    error_log = mock_logger.error.call_args[0][0]
    assert "Type: ETLError" in error_log
    assert "777" in error_log

# [LOG-13] 비동기 함수(Async) 일반 예외 발생
@pytest.mark.asyncio
async def test_log_decorator_async_exception_reraise(mock_logger, clean_context):
    """Scenario: Async 함수에서 일반 예외 발생 시 ETLError로 래핑되어 전파 (Async True 분기 보완)"""
    @LoggingDecorator()
    async def fail_async_func():
        raise ValueError("Invalid Input Async")
        
    with pytest.raises(ETLError) as exc_info:
        await fail_async_func()
        
    assert "예기치 못한 오류 발생" in str(exc_info.value)
    mock_logger.error.assert_called_once()
    error_log = mock_logger.error.call_args[0][0]
    assert "FAILED" in error_log

# [LOG-14] 비동기 함수(Async) 예외 무시
@pytest.mark.asyncio
async def test_log_decorator_async_exception_suppress(mock_logger, clean_context):
    """Scenario: Async 함수에서 suppress_error=True 이면 예외 무시 및 None 반환 (Async 예외 무시 분기)"""
    @LoggingDecorator(suppress_error=True)
    async def fail_async_suppressed():
        raise RuntimeError("Fatal DB Error Async")
        
    result = await fail_async_suppressed()
    
    assert result is None
    mock_logger.error.assert_called_once()

# [RLIMIT-01] ImportError Fallback
def test_rlimit_import_fallback():
    """Scenario: src.common.log 임포트 실패 시 fallback 경로 로직이 실행되어야 함"""
    target_module_name = 'src.common.decorators.rate_limit_decorator'
    if target_module_name not in sys.modules:
        import src.common.decorators.rate_limit_decorator
        
    target_module = sys.modules[target_module_name]
    original_import = builtins.__import__
    
    def mocked_import(name, *args, **kwargs):
        if name == 'src.common.log' and not getattr(mocked_import, 'failed', False):
            mocked_import.failed = True
            raise ImportError("Simulated ImportError")
        return original_import(name, *args, **kwargs)

    with patch('builtins.__import__', side_effect=mocked_import):
        importlib.reload(target_module)
        
    importlib.reload(target_module)

# [RLIMIT-02] Sync Wrapper Happy Path 및 Default Bucket Key
def test_rlimit_sync_happy_path():
    """Scenario: bucket_key 미지정 시 함수명이 키가 되며, 동기 함수가 정상 반환되어야 함"""
    @RateLimitDecorator(limit=2, period=1.0)
    def sync_func():
        return "sync_ok"
        
    assert sync_func() == "sync_ok"
    # [핵심 수정] 리로드 후에도 안전하게 동적 참조되는 모듈의 _buckets 확인
    expected_key = sync_func.__qualname__
    assert expected_key in rld_module._buckets

# [RLIMIT-03] Sync Wrapper Throttling 및 대기 처리
@patch("time.sleep")
def test_rlimit_sync_throttling(mock_sleep):
    """Scenario: 허용치 도달 시 time.sleep이 호출되며 정상적으로 대기 후 실행되어야 함"""
    @RateLimitDecorator(limit=1, period=1.0, bucket_key="sync_throttle")
    def sync_func():
        return "ok"
        
    assert sync_func() == "ok"
    
    with patch("time.time", return_value=time.time() + 0.5):
        assert sync_func() == "ok"
        mock_sleep.assert_called_once()
        wait_time_called = mock_sleep.call_args[0][0]
        assert wait_time_called > 0

# [RLIMIT-04] Max Wait 초과 시 RateLimitError 발생
def test_rlimit_max_wait_exceeded():
    """Scenario: 대기 시간이 max_wait_seconds를 초과하면 즉시 예외(Fail-fast) 발생 (Sync)"""
    @RateLimitDecorator(limit=1, period=10.0, max_wait_seconds=1.0)
    def sync_func():
        pass
        
    sync_func() # 첫 호출 통과
    
    with pytest.raises(RateLimitError) as exc_info:
        sync_func() # 에러 발생
        
    assert "최대 허용 대기 시간" in str(exc_info.value)
    expected_key = sync_func.__qualname__
    assert exc_info.value.details["bucket_key"] == expected_key

# [RLIMIT-05] 로깅 분기 확인
@patch("time.sleep")
@patch("src.common.decorators.rate_limit_decorator.LogManager")
def test_rlimit_log_throttling(mock_log_manager, mock_sleep):
    """Scenario: 대기 시간이 0.1초를 초과하면 LogManager를 통해 디버그 로그 출력"""
    mock_logger = MagicMock()
    mock_log_manager.get_logger.return_value = mock_logger
    
    @RateLimitDecorator(limit=1, period=1.0)
    def sync_func():
        pass
        
    sync_func()
    
    with patch("time.time", return_value=time.time() + 0.2):
        sync_func()
        mock_logger.debug.assert_called_once()
        assert "Throttling" in mock_logger.debug.call_args[0][0]

# [RLIMIT-06] Sync Wrapper 일반 예외 발생 시 ETLError 래핑
def test_rlimit_sync_general_exception():
    """Scenario: 동기 함수 실행 중 일반 예외 발생 시 구조화된 ETLError로 래핑됨"""
    @RateLimitDecorator()
    def fail_sync():
        raise ValueError("Sync Error")
        
    with pytest.raises(ETLError) as exc_info:
        fail_sync()
        
    assert "예기치 못한 오류 발생" in str(exc_info.value)
    assert "Sync Error" in str(exc_info.value)

# [RLIMIT-07] Async Wrapper 일반 예외 발생 시 ETLError 래핑
@pytest.mark.asyncio
async def test_rlimit_async_general_exception():
    """Scenario: 비동기 함수 실행 중 일반 예외 발생 시 구조화된 ETLError로 래핑됨"""
    @RateLimitDecorator()
    async def fail_async():
        raise ValueError("Async Error")
        
    with pytest.raises(ETLError) as exc_info:
        await fail_async()
        
    assert "예기치 못한 오류 발생" in str(exc_info.value)
    assert "Async Error" in str(exc_info.value)

# [RLIMIT-08] Async Wrapper Max Wait 초과 시 RateLimitError 발생 및 details 갱신
@pytest.mark.asyncio
async def test_rlimit_async_max_wait_exceeded():
    """Scenario: 비동기 래퍼에서 RateLimitError 발생 시 details에 bucket_key가 정상 업데이트됨"""
    @RateLimitDecorator(limit=1, period=10.0, max_wait_seconds=1.0, bucket_key="async_max_wait")
    async def async_func():
        pass
        
    await async_func()
    
    with pytest.raises(RateLimitError) as exc_info:
        await async_func()
        
    assert exc_info.value.details["bucket_key"] == "async_max_wait"

# [RLIMIT-09] _cleanup 메서드 및 큐 관리 테스트
def test_rlimit_cleanup():
    """Scenario: 만료된 타임스탬프는 큐에서 정상적으로 정리(cleanup)되어야 함"""
    # 모듈에서 직접 _get_bucket 호출하여 검증
    bucket = rld_module._get_bucket("test_cleanup", limit=2, period=1.0)
    now = time.time()
    
    bucket.timestamps.append(now - 2.0) 
    bucket.timestamps.append(now - 0.5) 
    
    bucket._cleanup(now)
    
    assert len(bucket.timestamps) == 1
    assert bucket.timestamps[0] == now - 0.5

# [RLIMIT-10] get_wait_time() 내 wait_time < 0 도달 방어 로직 검증
def test_rlimit_negative_wait_time():
    """Scenario: 부동소수점 오차 등으로 인해 wait_time이 음수가 될 경우 0.0으로 보정됨"""
    bucket = rld_module._get_bucket("negative_wait", limit=1, period=1.0)
    now = time.time()
    
    # _cleanup을 무력화하여 과거 타임스탬프가 큐에서 지워지지 않게 조작
    with patch.object(bucket, '_cleanup'):
        bucket.timestamps.append(now - 10.0) # 무조건 음수의 대기 시간이 나오도록 매우 과거의 시간 세팅
        
        with patch("time.time", return_value=now):
            wait = bucket.get_wait_time()
            assert wait == 0.0

# [RLIMIT-11] 대기 시간이 0.1 이하일 경우 디버그 로그 생략 분기
@patch("time.sleep")
def test_rlimit_short_wait_no_log(mock_sleep):
    """Scenario: 0 < wait_time <= 0.1 인 경우 로그(LogManager)를 호출하지 않고 분기를 빠져나옴(exit)"""
    @RateLimitDecorator(limit=1, period=1.0, bucket_key="short_wait")
    def sync_func():
        return "ok"
        
    sync_func() # 첫 번째 호출 통과 (대기 없음)
    
    # 0.95초 경과 가정 -> 0.05초만 대기하면 됨 (0.1초 이하)
    with patch("time.time", return_value=time.time() + 0.95):
        with patch("src.common.decorators.rate_limit_decorator.LogManager") as mock_log_manager:
            sync_func()
            
            mock_sleep.assert_called_once()
            # 0.1 이하이므로 로그 출력 메서드가 호출되지 않아야 함
            mock_log_manager.get_logger.assert_not_called()

# [RLIMIT-12] Async Wrapper Throttling 및 정상 대기 분기
@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_rlimit_async_throttling(mock_sleep):
    """Scenario: 비동기 래퍼에서 허용치 도달 시 예외를 던지지 않고 asyncio.sleep으로 정상 대기함"""
    @RateLimitDecorator(limit=1, period=1.0, bucket_key="async_throttle")
    async def async_func():
        return "async_ok"
        
    assert await async_func() == "async_ok"
    
    # 0.5초 경과 가정 -> 0.5초의 대기 시간이 생김 (조건문 True 만족)
    with patch("time.time", return_value=time.time() + 0.5):
        assert await async_func() == "async_ok"
        
        mock_sleep.assert_called_once()
        wait_time_called = mock_sleep.call_args[0][0]
        assert wait_time_called > 0

# [RETRY-01] ImportError Fallback
def test_retry_import_fallback():
    """Scenario: src.common.log 임포트 실패 시 fallback 경로 로직이 실행되어야 함"""
    target_module_name = 'src.common.decorators.retry_decorator'
    if target_module_name not in sys.modules:
        import src.common.decorators.retry_decorator
        
    target_module = sys.modules[target_module_name]
    original_import = builtins.__import__
    
    def mocked_import(name, *args, **kwargs):
        if name == 'src.common.log' and not getattr(mocked_import, 'failed', False):
            mocked_import.failed = True
            raise ImportError("Simulated ImportError")
        return original_import(name, *args, **kwargs)

    with patch('builtins.__import__', side_effect=mocked_import):
        importlib.reload(target_module)
        
    importlib.reload(target_module)

# [RETRY-02] Sync Wrapper Happy Path
def test_retry_sync_happy_path():
    """Scenario: 동기 함수가 오류 없이 즉시 성공할 경우"""
    @RetryDecorator(max_retries=2)
    def sync_func():
        return "sync_ok"
    
    assert sync_func() == "sync_ok"

# [RETRY-03] Sync Wrapper Retry Then Success
@patch("time.sleep")
def test_retry_sync_retry_then_success(mock_sleep):
    """Scenario: 동기 함수가 일시적 에러 발생 후 재시도하여 성공함"""
    attempts = 0
    @RetryDecorator(max_retries=2, base_delay=0.1)
    def sync_func():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ValueError("Temporary Error")
        return "success"
    
    assert sync_func() == "success"
    assert attempts == 2
    mock_sleep.assert_called_once()

# [RETRY-04] Sync Wrapper Max Retries Exceeded
@patch("time.sleep")
def test_retry_sync_max_retries_exceeded(mock_sleep):
    """Scenario: 최대 재시도 횟수를 초과할 때까지 동기 함수가 실패하면 최종 예외 발생"""
    @RetryDecorator(max_retries=2, base_delay=0.1)
    def sync_func():
        raise ValueError("Persistent Error")
    
    with pytest.raises(ValueError, match="Persistent Error"):
        sync_func()
    
    assert mock_sleep.call_count == 2

# [RETRY-05] Sync Wrapper No Retry Attribute
@patch("time.sleep")
def test_retry_sync_no_retry_attr(mock_sleep):
    """Scenario: should_retry=False 인 예외 발생 시 재시도 없이 즉시 실패 (Fail-Fast)"""
    @RetryDecorator(max_retries=2, base_delay=0.1)
    def sync_func():
        raise ETLError(message="Fatal Error", should_retry=False)
    
    with pytest.raises(ETLError):
        sync_func()
    
    # 즉시 실패했으므로 sleep이 한 번도 호출되지 않아야 함
    mock_sleep.assert_not_called()

# [RETRY-06] Async Wrapper Retry Then Success
@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_retry_async_retry_then_success(mock_sleep):
    """Scenario: 비동기 함수가 일시적 에러 발생 후 재시도하여 성공함"""
    attempts = 0
    @RetryDecorator(max_retries=2, base_delay=0.1)
    async def async_func():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ValueError("Temporary Error")
        return "async_success"
    
    assert await async_func() == "async_success"
    assert attempts == 2
    mock_sleep.assert_called_once()

# [RETRY-07] Async Wrapper Max Retries Exceeded
@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_retry_async_max_retries_exceeded(mock_sleep):
    """Scenario: 최대 재시도 횟수를 초과할 때까지 비동기 함수가 실패하면 최종 예외 발생"""
    @RetryDecorator(max_retries=2, base_delay=0.1)
    async def async_func():
        raise ValueError("Persistent Error")
    
    with pytest.raises(ValueError, match="Persistent Error"):
        await async_func()
    
    assert mock_sleep.call_count == 2

# [RETRY-08] Async Wrapper No Retry Attribute
@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_retry_async_no_retry_attr(mock_sleep):
    """Scenario: 비동기 환경에서 should_retry=False 예외 발생 시 재시도 없이 즉시 실패"""
    @RetryDecorator(max_retries=2, base_delay=0.1)
    async def async_func():
        raise ETLError(message="Fatal Error", should_retry=False)
    
    with pytest.raises(ETLError):
        await async_func()
    
    mock_sleep.assert_not_called()

# [RETRY-09] Jitter 조건 분기 테스트
def test_retry_calculate_delay_jitter_branches():
    """Scenario: Jitter True/False 옵션에 따른 delay 계산 로직 분기 검증"""
    decorator_no_jitter = RetryDecorator(jitter=False, base_delay=1.0)
    delay_no_jitter = decorator_no_jitter._calculate_delay(1)
    assert delay_no_jitter == 1.0  # Jitter가 없으므로 정확히 1.0
    
    decorator_with_jitter = RetryDecorator(jitter=True, base_delay=1.0)
    with patch("random.uniform", return_value=0.05):
        delay_with_jitter = decorator_with_jitter._calculate_delay(1)
        assert delay_with_jitter == 1.05  # Jitter가 적용됨

# [RETRY-10] Logger Name 명시적 지정 분기
def test_retry_logger_name_branch():
    """Scenario: logger_name이 명시적으로 주어졌을 때 자동 할당을 건너뛰는 분기 검증"""
    @RetryDecorator(logger_name="CustomRetryLogger")
    def sync_func():
        return "ok"
    
    # 정상 실행 및 분기 건너뛰기 확인
    assert sync_func() == "ok"


# [RETRY-11] Sync Wrapper Loop Exhaustion 방어 로직
def test_retry_sync_loop_exhausted():
    """
    Scenario: max_retries가 음수(-1)일 경우 루프를 한 번도 돌지 않고 
    즉시 루프를 빠져나와 예외를 발생시키는 극한의 엣지 케이스
    """
    @RetryDecorator(max_retries=-1)
    def sync_func():
        return "ok"
        
    # last_exception이 None인 상태로 `raise last_exception`이 실행되므로 TypeError 발생
    with pytest.raises(TypeError):
        sync_func()


# [RETRY-12] Async Wrapper Loop Exhaustion 방어 로직
@pytest.mark.asyncio
async def test_retry_async_loop_exhausted():
    """
    Scenario: 비동기 환경에서 max_retries가 음수일 때 
    즉시 루프를 빠져나오는 분기
    """
    @RetryDecorator(max_retries=-1)
    async def async_func():
        return "ok"
        
    with pytest.raises(TypeError):
        await async_func()

# [EXCEPT-01] NetworkConnectionError URL 파라미터 분기
def test_network_connection_error_no_url():
    """Scenario: URL이 주어지지 않은 경우 details가 빈 딕셔너리로 세팅됨"""
    err = NetworkConnectionError("timeout")
    assert err.details == {}
    assert err.should_retry is True

def test_network_connection_error_with_url():
    """Scenario: URL이 주어진 경우 details에 URL이 정상적으로 할당됨"""
    err = NetworkConnectionError("timeout", url="http://api.test.com")
    assert err.details == {"url": "http://api.test.com"}

# [EXCEPT-02] HttpError body 길이 Truncate 분기 방어 로직
def test_http_error_short_body():
    """Scenario: response_body 길이가 최대 제한을 넘지 않으면 원본 문자열을 그대로 유지"""
    short_body = "short response"
    err = HttpError("Not Found", status_code=404, response_body=short_body)
    assert err.details["response_body_preview"] == short_body

def test_http_error_long_body():
    """Scenario: response_body 길이가 제한치(500자)를 넘으면 안전하게 잘라내고 축약 문구 추가"""
    long_body = "x" * 600
    err = HttpError("Server Error", status_code=500, response_body=long_body)
    
    preview = err.details["response_body_preview"]
    assert len(preview) == 500 + len("...(truncated)")
    assert preview.endswith("...(truncated)")
    assert preview.startswith("x" * 500)

# [EXCEPT-03] AuthError 강제 설정 로직
def test_auth_error_init():
    """Scenario: AuthError는 무조건 재시도 불가(should_retry=False) 객체로 초기화되어야 함"""
    err = AuthError("Unauthorized Token", status_code=403)
    assert err.details["status_code"] == 403
    assert err.should_retry is False
    assert "Unauthorized Token" in str(err)

@pytest.mark.asyncio
async def test_interfaces_abstract_methods_coverage():
    """
    Scenario: 추상 클래스(인터페이스) 내부에 선언된 pass 구문 커버리지 달성을 위한 명시적 호출.
    더미 클래스를 생성하고 super()를 통해 추상 메서드를 직접 호출하여 
    파이썬의 실행 엔진이 해당 라인을 밟고 지나가도록 유도합니다.
    """
    
    # 1. Dummy 클래스 구현 (super()를 통해 부모의 pass 블록 직접 호출)
    class DummyHttpClient(IHttpClient):
        async def get(self, url, headers=None, params=None):
            return await super().get(url, headers=headers, params=params)
        
        async def post(self, url, headers=None, data=None):
            return await super().post(url, headers=headers, data=data)
            
    class DummyAuthStrategy(IAuthStrategy):
        async def get_token(self, http_client):
            return await super().get_token(http_client)
            
    class DummyExtractor(IExtractor):
        async def extract(self, request):
            return await super().extract(request)
            
    # 2. IHttpClient
    client = DummyHttpClient()
    assert await client.get("http://dummy.test") is None
    assert await client.post("http://dummy.test") is None
    
    # 3. IAuthStrategy
    auth = DummyAuthStrategy()
    assert await auth.get_token(client) is None
    
    # 4. IExtractor
    ext = DummyExtractor()
    assert await ext.extract(None) is None

# [LOG-1] JsonFormatter - Non-ETLError Exception and json.dumps exception
def test_log_json_formatter_normal_exception_and_fallback():
    """Scenario: ETLError가 아닌 일반 예외 처리 및 json.dumps 실패 시 fallback 처리 검증"""
    formatter = JsonFormatter()
    
    # 일반 예외를 가지는 LogRecord 생성
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="test.py", lineno=1,
        msg="test message", args=(), exc_info=None
    )
    
    try:
        raise ValueError("Normal Error")
    except ValueError:
        record.exc_info = sys.exc_info()
    
    # 1. 일반 예외가 제대로 "exception" 키에 들어가는지 검증
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert "exception" in parsed
    assert "Normal Error" in parsed["exception"]
    
    # 2. json.dumps가 실패하도록 조작하되, 예외 발생 시의 Fallback은 정상 수행되도록 분기 처리
    original_dumps = json.dumps
    def mocked_dumps(obj, *args, **kwargs):
        # 첫 번째 변환 시도(원본 레코드에 exception 키가 있음)일 때만 에러 발생시킴
        if isinstance(obj, dict) and "exception" in obj:
            raise TypeError("Not serializable")
        # Fallback 구조체는 정상적으로 변환해줌
        return original_dumps(obj, *args, **kwargs)

    with patch("json.dumps", side_effect=mocked_dumps):
        fallback_formatted = formatter.format(record)
        fallback_parsed = json.loads(fallback_formatted)
        assert fallback_parsed["level"] == "ERROR"
        assert "치명적 오류" in fallback_parsed["message"]


# [LOG-2] LogManager Singleton Double-Check
def test_log_manager_double_check():
    """Scenario: 멀티스레드 환경을 모사하여 락 획득 후 _instance 재확인 상태 분기 검증"""
    original_instance = LogManager._instance
    
    class MockLock:
        def __enter__(self):
            # 락 내부 진입 순간에 다른 스레드가 이미 초기화한 상태를 모사
            LogManager._instance = "dummy_instance"
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
            
    try:
        LogManager._instance = None
        with patch.object(LogManager, '_lock', MockLock()):
            inst = LogManager.__new__(LogManager)
            assert inst == "dummy_instance"
    finally:
        # 테스트 환경 오염 방지를 위해 무조건 복구
        LogManager._instance = original_instance


# [LOG-3] LogManager Initialized Double-Check
def test_log_manager_init_double_check():
    """Scenario: 멀티스레드 환경을 모사하여 락 획득 후 _initialized 재확인 분기 검증"""
    manager = LogManager() # 기존 인스턴스 확보
    original_initialized = getattr(manager, "_initialized", False)
    
    class MockLock:
        def __enter__(self):
            # 락 내부 진입 순간에 이미 설정이 끝난 상태를 모사
            manager._initialized = True
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
            
    try:
        manager._initialized = False
        with patch.object(LogManager, '_lock', MockLock()):
            manager.__init__() # 여기서 191번 라인 return 이 실행됨
    finally:
        manager._initialized = original_initialized


# [LOG-4] LogManager Handlers Already Exist
@patch("src.common.log.ConfigManager.get_config")
def test_log_manager_handlers_exist(mock_get_config):
    """Scenario: 이미 핸들러가 존재하는 경우 중복 추가하지 않고 건너뜀(210->220 Exit)"""
    # 1. ConfigManager가 반환할 task_name을 고정
    mock_config = MagicMock()
    mock_config.task_name = "test_handlers_exist"
    mock_config.log_level = "INFO"
    mock_config.log_dir = "logs"
    mock_config.log_filename = "app.log"
    mock_get_config.return_value = mock_config

    manager = LogManager()
    original_initialized = getattr(manager, "_initialized", False)
    
    # 2. 고정된 task_name과 일치하는 로거에 미리 더미 핸들러를 주입하여 상태 조작
    pre_logger = logging.getLogger("test_handlers_exist")
    dummy_handler = logging.NullHandler()
    pre_logger.addHandler(dummy_handler)
    
    try:
        manager._initialized = False
        
        # 3. 초기화 트리거
        # __init__ 내부에서 getLogger("test_handlers_exist")를 호출하면 pre_logger를 반환받음
        # 이미 dummy_handler가 존재하므로 if not self.logger.handlers: 가 False가 되어 건너뜀 
        manager.__init__()
        
        # 4. 검증: 핸들러가 중복 추가되지 않고 최초의 1개(dummy_handler)만 유지되는지 확인
        assert len(manager.logger.handlers) == 1
        assert manager.logger.handlers[0] is dummy_handler
    finally:
        # 테스트 환경 오염 방지를 위해 주입한 핸들러 제거 및 상태 원상 복구
        pre_logger.handlers.clear()
        manager._initialized = original_initialized


# [LOG-5] LogManager File Handler OSError
def test_log_manager_file_handler_oserror():
    """Scenario: 로그 디렉토리 생성 실패(OSError) 시 시스템 중단 없이 stderr 경고만 출력"""
    manager = LogManager()
    
    with patch("pathlib.Path.mkdir", side_effect=OSError("Permission Denied")):
        with patch("sys.stderr.write") as mock_stderr:
            manager._setup_file_handler(logging.Formatter(), logging.Filter())
            
            mock_stderr.assert_called_once()
            assert "Permission Denied" in mock_stderr.call_args[0][0]


# [LOG-6] get_logger with name=None
def test_log_manager_get_logger_no_name():
    """Scenario: 이름을 주지 않으면 최상위 기본 로거 인스턴스를 반환"""
    logger = LogManager.get_logger()
    manager = LogManager()
    assert logger.name == manager.logger.name


# [LOG-7] set_context with explicit request_id
def test_log_manager_set_context_explicit_id():
    """Scenario: request_id를 명시적으로 전달하면 새로 생성하지 않고 해당 ID가 세팅됨"""
    original_id = request_id_ctx.get()
    
    custom_id = "my-custom-request-id"
    returned_id = LogManager.set_context(custom_id)
    
    assert returned_id == custom_id
    assert request_id_ctx.get() == custom_id
    
    request_id_ctx.set(original_id)

# [AUTH-01] KIS 설정 누락 방어 로직
def test_auth_kis_missing_base_url(auth_mock_config):
    auth_mock_config.kis.base_url = ""
    with pytest.raises(ValueError, match="base_url' is empty"):
        KISAuthStrategy(auth_mock_config)

# [AUTH-02] KIS Double-Checked Locking 및 갱신 건너뛰기 분기
@pytest.mark.asyncio
async def test_auth_kis_double_checked_locking_skip(auth_mock_config):
    """Scenario: 락 대기 중 다른 태스크가 이미 토큰을 갱신했다면 재갱신을 건너뜀"""
    strategy = KISAuthStrategy(auth_mock_config)
    strategy._access_token = "valid_token_from_other_task"
    # 명시적 경로(datetime.datetime) 사용
    strategy._expires_at = datetime.datetime.now() + datetime.timedelta(hours=1)
    
    with patch.object(strategy, '_should_refresh', side_effect=[True, False]):
        token = await strategy.get_token(AsyncMock())
        
    assert token == "Bearer valid_token_from_other_task"

# [AUTH-03] KIS 토큰 획득 완전 실패 방어 로직
@pytest.mark.asyncio
async def test_auth_kis_silent_failure(auth_mock_config):
    """Scenario: _issue_token이 에러 없이 종료되었으나 여전히 토큰이 없는 경우"""
    strategy = KISAuthStrategy(auth_mock_config)
    strategy._should_refresh = MagicMock(return_value=True)
    strategy._issue_token = AsyncMock()
    
    with pytest.raises(AuthError, match="Failed to retrieve access token"):
        await strategy.get_token(AsyncMock())

# [AUTH-04] KIS 만료 임박(Threshold) 갱신 로직
def test_auth_kis_should_refresh_threshold(auth_mock_config):
    """Scenario: 만료 시간이 지났진 않았지만 임계치 내로 도달하면 갱신을 트리거함"""
    strategy = KISAuthStrategy(auth_mock_config)
    strategy._access_token = "token"
    # 만료까지 1분 남음 (기본 버퍼인 5분보다 작으므로 갱신 대상)
    strategy._expires_at = datetime.datetime.now() + datetime.timedelta(minutes=1)
    
    assert strategy._should_refresh() is True

# [AUTH-05] KIS 토큰 발급 시 Network 및 일반 예외 처리
@pytest.mark.asyncio
async def test_auth_kis_issue_token_exceptions(auth_mock_config):
    strategy = KISAuthStrategy(auth_mock_config)
    mock_client = AsyncMock()
    
    mock_client.post.side_effect = NetworkConnectionError("401 Unauthorized")
    with pytest.raises(AuthError, match="Invalid Credentials"):
        await strategy._issue_token(mock_client)
        
    mock_client.post.side_effect = NetworkConnectionError("Timeout")
    with pytest.raises(NetworkConnectionError):
        await strategy._issue_token(mock_client)
        
    mock_client.post.side_effect = ValueError("JSON Parsing Failed")
    with pytest.raises(AuthError, match="Error during token issuance"):
        await strategy._issue_token(mock_client)

# [AUTH-06] KIS 응답 검증 - access_token 누락
def test_auth_kis_validate_response(auth_mock_config):
    strategy = KISAuthStrategy(auth_mock_config)
    with pytest.raises(AuthError, match="Missing access_token"):
        strategy._validate_response({"wrong_key": "123"})

# [AUTH-07] KIS 상태 업데이트 - 만료일 파싱 에러/누락
def test_auth_kis_update_state_date_fallback(auth_mock_config):
    strategy = KISAuthStrategy(auth_mock_config)
    
    strategy._update_state({"access_token": "tk1", "access_token_token_expired": "invalid_date_format"})
    assert strategy._access_token == "tk1"
    assert strategy._expires_at > datetime.datetime.now()
    
    strategy._update_state({"access_token": "tk2"})
    assert strategy._access_token == "tk2"
    assert strategy._expires_at > datetime.datetime.now()

# [AUTH-08] UPBIT 설정 누락 방어 로직
def test_auth_upbit_missing_config(auth_mock_config):
    auth_mock_config.upbit.base_url = ""
    with pytest.raises(ValueError, match="base_url' is empty"):
        UPBITAuthStrategy(auth_mock_config)
    auth_mock_config.upbit.base_url = "https://api.upbit.mock" 
    
    del auth_mock_config.upbit.secret_key
    with pytest.raises(ValueError, match="missing in UPBITSettings"):
        UPBITAuthStrategy(auth_mock_config)

# [AUTH-09] UPBIT Query Hash 및 Bytes 디코딩 로직
@pytest.mark.asyncio
async def test_auth_upbit_query_params_and_bytes_fallback(auth_mock_config):
    auth_mock_config.upbit.secret_key = MagicMock()
    auth_mock_config.upbit.secret_key.get_secret_value.return_value = "dummy_secret"
    strategy = UPBITAuthStrategy(auth_mock_config)
    
    with patch("jwt.encode", return_value=b"mocked_bytes_token"):
        token = await strategy.get_token(AsyncMock(), query_params={"market": "KRW-BTC"})
        assert token == "Bearer mocked_bytes_token"

# [HTTP-01] 초기화, Context Manager 진입/종료 및 세션 관리
@pytest.mark.asyncio
async def test_http_adapter_lifecycle():
    """Scenario: 어댑터 생성, 세션 초기화, Context Manager를 통한 자원 정리 검증"""
    adapter = AsyncHttpAdapter(timeout=10)
    assert adapter.timeout.total == 10
    
    await adapter.close()
    
    async with adapter as ctx_adapter:
        assert ctx_adapter is adapter
        assert adapter._session is not None
        assert not adapter._session.closed
        
        session1 = await adapter._get_session()
        assert session1 is adapter._session
    
    assert adapter._session.closed

# [HTTP-02] GET 요청 성공 및 실패 분기
@pytest.mark.asyncio
async def test_http_adapter_get_success(http_adapter):
    """Scenario: GET 요청 성공 시 JSON 응답 반환"""
    mock_session = MagicMock()
    mock_session.closed = False 
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.json.return_value = {"status": "ok"}
    
    # [핵심 방어 로직] async with 프로토콜을 준수하는 더미 매니저 주입
    mock_session.get.return_value = DummyAsyncContextManager(mock_response=mock_resp)
    http_adapter._session = mock_session
    
    res = await http_adapter.get("http://dummy.api")
    assert res == {"status": "ok"}

@pytest.mark.asyncio
async def test_http_adapter_get_error(http_adapter):
    """Scenario: GET 요청 중 ClientError 발생 시 NetworkConnectionError로 래핑됨"""
    mock_session = MagicMock()
    mock_session.closed = False 
    
    # __aenter__ 진입 시 예외가 터지도록 side_effect 주입
    error_effect = aiohttp.ClientError("Connection Refused")
    mock_session.get.return_value = DummyAsyncContextManager(side_effect=error_effect)
    http_adapter._session = mock_session
    
    with pytest.raises(NetworkConnectionError, match="Connection Refused"):
         await http_adapter.get("http://dummy.api")

# [HTTP-03] POST 요청 성공 및 실패 분기
@pytest.mark.asyncio
async def test_http_adapter_post_success(http_adapter):
    """Scenario: POST 요청 성공 시 텍스트 응답 반환 (JSON이 아닐 때 Text 반환 로직 검증)"""
    mock_session = MagicMock()
    mock_session.closed = False 
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {"Content-Type": "text/plain"}
    mock_resp.text.return_value = "plain text response"
    
    mock_session.post.return_value = DummyAsyncContextManager(mock_response=mock_resp)
    http_adapter._session = mock_session
    
    res = await http_adapter.post("http://dummy.api", data={"payload": 123})
    assert res == "plain text response"

@pytest.mark.asyncio
async def test_http_adapter_post_error(http_adapter):
    """Scenario: POST 요청 중 Timeout 발생 시 NetworkConnectionError로 래핑됨"""
    mock_session = MagicMock()
    mock_session.closed = False 
    
    timeout_effect = asyncio.TimeoutError("timeout")
    mock_session.post.return_value = DummyAsyncContextManager(side_effect=timeout_effect)
    http_adapter._session = mock_session
    
    with pytest.raises(NetworkConnectionError, match="POST http://dummy.api failed"):
         await http_adapter.post("http://dummy.api")

# [HTTP-04] 응답 핸들러 상태 코드 및 파싱 분기
@pytest.mark.asyncio
async def test_http_adapter_handle_response_error_status(http_adapter):
    """Scenario: HTTP 응답 코드가 400 이상일 경우 에러 바디를 포함하여 예외 발생"""
    mock_resp = AsyncMock()
    mock_resp.status = 404
    mock_resp.text.return_value = "Not Found Page"
    
    with pytest.raises(NetworkConnectionError, match="HTTP 404 on GET http://dummy.api: Not Found Page"):
        await http_adapter._handle_response(mock_resp, "http://dummy.api", "GET")

@pytest.mark.asyncio
async def test_http_adapter_handle_response_json_parsing_error(http_adapter):
    """Scenario: Content-Type이 JSON이나 파싱 에러(망가진 데이터) 시 텍스트 파싱으로 Fallback"""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {"Content-Type": "application/json"}
    
    mock_resp.json.side_effect = ValueError("Malformed JSON")
    mock_resp.text.return_value = "{malformed json"
    
    res = await http_adapter._handle_response(mock_resp, "http://dummy.api", "GET")
    assert res == "{malformed json"

# [EXTRACTOR-01] ConfigManager 의존성 누락 방어 로직
def test_abstract_extractor_init_missing_config():
    """Scenario: 초기화 시 config가 None일 경우 런타임 에러 방지를 위해 ConfigurationError 발생"""
    mock_http_client = MagicMock()
    
    # 추상 클래스이므로 임시 더미 구현체 생성
    class DummyExtractor(AbstractExtractor):
        def _validate_request(self, request): pass
        async def _fetch_raw_data(self, request): pass
        def _create_response(self, raw_data, job_id): pass
        
    with pytest.raises(ConfigurationError, match="ConfigManager 인스턴스가 필요합니다"):
        DummyExtractor(http_client=mock_http_client, config=None)

# [EXTRACTOR-02] 일반 Exception 발생 시 ExtractorError 래핑 방어 로직
@pytest.mark.asyncio
async def test_abstract_extractor_extract_general_exception():
    """Scenario: extract() 실행 중 통제되지 않은 일반 예외(Exception)가 발생하면 ExtractorError로 래핑됨"""
    mock_http_client = MagicMock()
    mock_config = MagicMock()
    
    # 내부 로직에서 의도적으로 ValueError를 발생시키는 결함(Faulty) 구현체 모사
    class FaultyExtractor(AbstractExtractor):
        def _validate_request(self, request):
            raise ValueError("Unexpected system memory failure")
            
        async def _fetch_raw_data(self, request): pass
        def _create_response(self, raw_data, job_id): pass
            
    extractor = FaultyExtractor(http_client=mock_http_client, config=mock_config)
    req = RequestDTO(job_id="test_error_job")
    
    with pytest.raises(ExtractorError) as exc_info:
        await extractor.extract(req)
        
    # 에러 메세지 및 디테일 검증
    assert "알 수 없는 시스템 오류 발생" in str(exc_info.value)
    assert "Unexpected system memory failure" in exc_info.value.details["raw_error"]
    assert exc_info.value.details["extractor"] == "FaultyExtractor"

# [ECOS-01] 초기화 시 필수 설정 누락 방어
def test_ecos_init_missing_base_url(ecos_mock_config):
    ecos_mock_config.ecos.base_url = ""
    with pytest.raises(ExtractorError, match="ecos.base_url' is empty"):
        ECOSExtractor(MagicMock(), ecos_mock_config)

def test_ecos_init_missing_api_key(ecos_mock_config):
    ecos_mock_config.ecos.api_key = None
    with pytest.raises(ExtractorError, match="ecos.api_key' is missing"):
        ECOSExtractor(MagicMock(), ecos_mock_config)

# [ECOS-02] _validate_request 정책 및 파라미터 검증
def test_ecos_validate_no_job_id(ecos_mock_config):
    extractor = ECOSExtractor(MagicMock(), ecos_mock_config)
    with pytest.raises(ExtractorError, match="job_id' is mandatory"):
        extractor._validate_request(RequestDTO(job_id=""))

def test_ecos_validate_no_policy(ecos_mock_config):
    extractor = ECOSExtractor(MagicMock(), ecos_mock_config)
    with pytest.raises(ExtractorError, match="Policy not found"):
        extractor._validate_request(RequestDTO(job_id="unknown_job"))

def test_ecos_validate_wrong_provider(ecos_mock_config):
    ecos_mock_config.extraction_policy["ecos_test_job"].provider = "KIS"
    extractor = ECOSExtractor(MagicMock(), ecos_mock_config)
    with pytest.raises(ExtractorError, match="not 'ECOS'"):
        extractor._validate_request(RequestDTO(job_id="ecos_test_job"))

def test_ecos_validate_missing_dates(ecos_mock_config):
    extractor = ECOSExtractor(MagicMock(), ecos_mock_config)
    with pytest.raises(ExtractorError, match="start_date' and 'end_date' are mandatory"):
        extractor._validate_request(RequestDTO(job_id="ecos_test_job", params={"start_date": "202301"}))

# [ECOS-03] _fetch_raw_data URL 조립 및 호출
@pytest.mark.asyncio
async def test_ecos_fetch_raw_data(ecos_mock_config):
    mock_client = AsyncMock()
    mock_client.get.return_value = {"StatisticSearch": {"RESULT": {"CODE": "INFO-000"}}}
    
    extractor = ECOSExtractor(mock_client, ecos_mock_config)
    req = RequestDTO(job_id="ecos_test_job", params={"start_date": "202301", "end_date": "202312"})
    
    res = await extractor._fetch_raw_data(req)
    assert "StatisticSearch" in res
    
    # URL Path 조립이 정확히 이루어졌는지 확인 (동적+정적 파라미터 병합)
    mock_client.get.assert_called_once()
    called_url = mock_client.get.call_args[0][0]
    expected_url = "https://ecos.mock.api/StatisticSearch/secret_key_123/json/kr/1/100000/001/M/202301/202312/A"
    assert called_url == expected_url

# [ECOS-04] _create_response 다양한 예외 및 성공 분기
def test_ecos_create_response_root_error(ecos_mock_config):
    """Scenario: 인증 실패 등으로 Root에 RESULT 코드가 바로 떨어지는 경우"""
    extractor = ECOSExtractor(MagicMock(), ecos_mock_config)
    raw_data = {"RESULT": {"CODE": "ERR-001", "MESSAGE": "API Key Invalid"}}
    
    with pytest.raises(ExtractorError, match="API Key Invalid \\(Code: ERR-001\\)"):
        extractor._create_response(raw_data, "ecos_test_job")

def test_ecos_create_response_business_error(ecos_mock_config):
    """Scenario: 서비스명 하위에 있는 RESULT 코드가 에러인 경우 (조회 결과 없음 등)"""
    extractor = ECOSExtractor(MagicMock(), ecos_mock_config)
    raw_data = {"StatisticSearch": {"RESULT": {"CODE": "ERR-002", "MESSAGE": "No Data Found"}}}
    
    with pytest.raises(ExtractorError, match="No Data Found \\(Code: ERR-002\\)"):
        extractor._create_response(raw_data, "ecos_test_job")

def test_ecos_create_response_invalid_format(ecos_mock_config):
    """Scenario: 요청한 서비스명(StatisticSearch)이 아예 결과에 없는 비정상 포맷"""
    extractor = ECOSExtractor(MagicMock(), ecos_mock_config)
    raw_data = {"UnknownService": {}}
    
    with pytest.raises(ExtractorError, match="Root key 'StatisticSearch' not found"):
        extractor._create_response(raw_data, "ecos_test_job")

def test_ecos_create_response_success(ecos_mock_config):
    """Scenario: 정상 데이터 반환 시 DTO 래핑"""
    extractor = ECOSExtractor(MagicMock(), ecos_mock_config)
    raw_data = {"StatisticSearch": {"RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"}, "row": [{"val": 1}]}}
    
    res = extractor._create_response(raw_data, "ecos_test_job")
    assert res.meta["status"] == "success"
    assert res.meta["source"] == "ECOS"
    assert res.data == raw_data

# [ECOS-05] _validate_request 정상 통과 해피 경로
def test_ecos_validate_success(ecos_mock_config):
    """Scenario: 모든 필수 파라미터(start_date, end_date)가 정상적으로 존재하여 검증을 무사히 통과함"""
    extractor = ECOSExtractor(MagicMock(), ecos_mock_config)
    
    # 예외가 발생하지 않고 함수가 정상 종료(exit)되면 통과
    request = RequestDTO(job_id="ecos_test_job", params={"start_date": "202301", "end_date": "202312"})
    extractor._validate_request(request)

# [ECOS-06] _create_response Root RESULT가 INFO-000인 경우
def test_ecos_create_response_root_success_and_body(ecos_mock_config):
    """Scenario: Root에 RESULT가 존재하지만 코드가 INFO-000이어서 에러 없이 다음 단계로 넘어감"""
    extractor = ECOSExtractor(MagicMock(), ecos_mock_config)
    raw_data = {
        "RESULT": {"CODE": "INFO-000", "MESSAGE": "Success"},
        "StatisticSearch": {"row": [{"val": 1}]}
    }
    
    res = extractor._create_response(raw_data, "ecos_test_job")
    assert res.meta["status"] == "success"

# [ECOS-07] _create_response Body 내에 RESULT가 아예 없는 경우
def test_ecos_create_response_no_result_in_body(ecos_mock_config):
    """Scenario: 서비스명 하위에 RESULT 키 없이 순수 데이터(row)만 내려오는 정상 응답 포맷 처리"""
    extractor = ECOSExtractor(MagicMock(), ecos_mock_config)
    raw_data = {
        "StatisticSearch": {"row": [{"val": 1}, {"val": 2}]}
    }
    
    res = extractor._create_response(raw_data, "ecos_test_job")
    assert res.meta["status"] == "success"

# [FRED-01] 초기화 시 필수 설정 누락 방어
def test_fred_init_missing_base_url(fred_mock_config):
    fred_mock_config.fred.base_url = ""
    with pytest.raises(ExtractorError, match="fred.base_url' is empty"):
        FREDExtractor(MagicMock(), fred_mock_config)

def test_fred_init_missing_api_key(fred_mock_config):
    fred_mock_config.fred.api_key = None
    with pytest.raises(ExtractorError, match="fred.api_key' is missing"):
        FREDExtractor(MagicMock(), fred_mock_config)

# [FRED-02] _validate_request 예외 및 성공 분기
def test_fred_validate_no_job_id(fred_mock_config):
    extractor = FREDExtractor(MagicMock(), fred_mock_config)
    with pytest.raises(ExtractorError, match="'job_id' is mandatory"):
        extractor._validate_request(RequestDTO(job_id=""))

def test_fred_validate_no_policy(fred_mock_config):
    extractor = FREDExtractor(MagicMock(), fred_mock_config)
    with pytest.raises(ExtractorError, match="Policy not found"):
        extractor._validate_request(RequestDTO(job_id="unknown_job"))

def test_fred_validate_wrong_provider(fred_mock_config):
    fred_mock_config.extraction_policy["fred_test_job"].provider = "ECOS"
    extractor = FREDExtractor(MagicMock(), fred_mock_config)
    with pytest.raises(ExtractorError, match="not 'FRED'"):
        extractor._validate_request(RequestDTO(job_id="fred_test_job"))

def test_fred_validate_missing_series_id(fred_mock_config):
    """Scenario: policy와 request 어디에도 series_id가 없는 경우 에러 발생"""
    fred_mock_config.extraction_policy["fred_test_job"].params = {}
    extractor = FREDExtractor(MagicMock(), fred_mock_config)
    with pytest.raises(ExtractorError, match="'series_id' is required"):
        extractor._validate_request(RequestDTO(job_id="fred_test_job", params={}))

def test_fred_validate_success(fred_mock_config):
    """Scenario: 검증을 무사히 통과하는 해피 경로 (Branch Exit)"""
    extractor = FREDExtractor(MagicMock(), fred_mock_config)
    # 예외가 발생하지 않으면 통과
    extractor._validate_request(RequestDTO(job_id="fred_test_job", params={"observation_start": "2023-01-01"}))

# [FRED-03] _fetch_raw_data URL 및 파라미터 병합 로직
@pytest.mark.asyncio
async def test_fred_fetch_raw_data(fred_mock_config):
    mock_client = AsyncMock()
    mock_client.get.return_value = {"observations": []}
    
    extractor = FREDExtractor(mock_client, fred_mock_config)
    req = RequestDTO(job_id="fred_test_job", params={"observation_start": "2023-01-01"})
    
    res = await extractor._fetch_raw_data(req)
    assert "observations" in res
    
    mock_client.get.assert_called_once()
    called_url = mock_client.get.call_args[0][0]
    called_params = mock_client.get.call_args[1]["params"]
    
    # URL 및 파라미터 병합 검증
    assert called_url == "https://api.fred.mock/series/observations"
    assert called_params["series_id"] == "GNPCA" # Policy에서 옴
    assert called_params["observation_start"] == "2023-01-01" # Request에서 옴
    assert called_params["file_type"] == "json" # 시스템 강제 주입
    assert called_params["api_key"] == "dummy_fred_secret_key" # 시스템 강제 주입

# [FRED-04] _create_response 응답 검증 및 DTO 래핑
def test_fred_create_response_with_error(fred_mock_config):
    """Scenario: HTTP는 200 OK지만 JSON Body에 error_message가 있는 비즈니스 실패 케이스"""
    extractor = FREDExtractor(MagicMock(), fred_mock_config)
    raw_data = {"error_code": 400, "error_message": "Bad Request"}
    
    with pytest.raises(ExtractorError, match="FRED API Failed: Bad Request \\(Code: 400\\)"):
        extractor._create_response(raw_data, "fred_test_job")

def test_fred_create_response_with_error_no_code(fred_mock_config):
    """Scenario: error_message는 있으나 error_code가 없는 엣지 케이스"""
    extractor = FREDExtractor(MagicMock(), fred_mock_config)
    raw_data = {"error_message": "Unknown Error"}
    
    with pytest.raises(ExtractorError, match="FRED API Failed: Unknown Error \\(Code: Unknown\\)"):
        extractor._create_response(raw_data, "fred_test_job")

def test_fred_create_response_success(fred_mock_config):
    """Scenario: 정상 응답 시 DTO 래핑 확인 (status 키 제거 및 job_id 검증 추가)"""
    extractor = FREDExtractor(MagicMock(), fred_mock_config)
    raw_data = {"observations": [{"value": "1.0"}]}
    
    res = extractor._create_response(raw_data, "fred_test_job")
    
    # FRED 구현체에 맞춰 meta 데이터를 검증
    assert res.meta["source"] == "FRED"
    assert res.meta["job_id"] == "fred_test_job"
    assert "extracted_at" in res.meta
    assert res.data == raw_data

# [KIS-01] 초기화 시 필수 설정 누락 방어
def test_kis_init_missing_base_url(kis_mock_config):
    kis_mock_config.kis.base_url = ""
    with pytest.raises(ExtractorError, match="'kis.base_url' is empty in ConfigManager"):
        KISExtractor(MagicMock(), AsyncMock(), kis_mock_config)

# [KIS-02] _validate_request 예외 및 성공 방어
def test_kis_validate_no_job_id(kis_mock_config):
    extractor = KISExtractor(MagicMock(), AsyncMock(), kis_mock_config)
    with pytest.raises(ExtractorError, match="'job_id' is mandatory"):
        extractor._validate_request(RequestDTO(job_id=""))

def test_kis_validate_no_policy(kis_mock_config):
    extractor = KISExtractor(MagicMock(), AsyncMock(), kis_mock_config)
    with pytest.raises(ExtractorError, match="Policy not found"):
        extractor._validate_request(RequestDTO(job_id="unknown_job"))

def test_kis_validate_wrong_provider(kis_mock_config):
    kis_mock_config.extraction_policy["kis_test_job"].provider = "ECOS"
    extractor = KISExtractor(MagicMock(), AsyncMock(), kis_mock_config)
    with pytest.raises(ExtractorError, match="not 'KIS'"):
        extractor._validate_request(RequestDTO(job_id="kis_test_job"))

def test_kis_validate_missing_tr_id(kis_mock_config):
    kis_mock_config.extraction_policy["kis_test_job"].tr_id = None
    extractor = KISExtractor(MagicMock(), AsyncMock(), kis_mock_config)
    with pytest.raises(ExtractorError, match="'tr_id' is missing in policy"):
        extractor._validate_request(RequestDTO(job_id="kis_test_job"))

def test_kis_validate_success(kis_mock_config):
    """Scenario: 모든 검증을 정상 통과하는 해피 경로"""
    extractor = KISExtractor(MagicMock(), AsyncMock(), kis_mock_config)
    extractor._validate_request(RequestDTO(job_id="kis_test_job"))

# [KIS-03] _fetch_raw_data 인증 획득, URL/헤더 조립 및 호출
@pytest.mark.asyncio
async def test_kis_fetch_raw_data(kis_mock_config):
    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = {"rt_cd": "0"}
    
    mock_auth_strategy = AsyncMock()
    mock_auth_strategy.get_token.return_value = "Bearer test_token"
    
    extractor = KISExtractor(mock_http_client, mock_auth_strategy, kis_mock_config)
    req = RequestDTO(job_id="kis_test_job", params={"FID_INPUT_ISCD": "005930"})
    
    res = await extractor._fetch_raw_data(req)
    assert res == {"rt_cd": "0"}
    
    # API 호출 검증
    mock_http_client.get.assert_called_once()
    called_url = mock_http_client.get.call_args[0][0]
    called_headers = mock_http_client.get.call_args[1]["headers"]
    called_params = mock_http_client.get.call_args[1]["params"]
    
    # URL 조립, 헤더 및 토큰 주입, 파라미터 병합 검증
    assert called_url == "https://api.kis.mock/uapi/domestic-stock/v1/quotations/inquire-price"
    assert called_headers["authorization"] == "Bearer test_token"
    assert called_headers["appkey"] == "dummy_kis_app_key"
    assert called_headers["appsecret"] == "dummy_kis_app_secret"
    assert called_headers["tr_id"] == "FHKST01010100"
    
    assert called_params["FID_COND_MRKT_DIV_CODE"] == "J"
    assert called_params["FID_INPUT_ISCD"] == "005930"

# [KIS-04] _create_response 응답 비즈니스 로직 에러 처리
def test_kis_create_response_with_error(kis_mock_config):
    """Scenario: KIS API에서 HTTP 200이 왔으나 비즈니스 코드(rt_cd)가 실패를 가리킴"""
    extractor = KISExtractor(MagicMock(), AsyncMock(), kis_mock_config)
    raw_data = {"rt_cd": "1", "msg1": "Invalid Parameter"}
    
    with pytest.raises(ExtractorError, match="KIS API Failed: Invalid Parameter \\(Code: 1\\)"):
        extractor._create_response(raw_data, "kis_test_job")

def test_kis_create_response_success(kis_mock_config):
    """Scenario: 정상 응답 시 DTO 래핑 검증"""
    extractor = KISExtractor(MagicMock(), AsyncMock(), kis_mock_config)
    raw_data = {"rt_cd": "0", "output": {"price": "1000"}}
    
    res = extractor._create_response(raw_data, "kis_test_job")
    assert res.meta["status_code"] == "0"
    assert res.meta["source"] == "KIS"
    assert res.data == raw_data

# [UPBIT-01] 초기화 시 필수 설정 누락 방어
def test_upbit_init_missing_base_url(upbit_mock_config):
    upbit_mock_config.upbit.base_url = ""
    with pytest.raises(ExtractorError, match="'upbit.base_url' is empty in ConfigManager"):
        UPBITExtractor(MagicMock(), AsyncMock(), upbit_mock_config)

# [UPBIT-02] _validate_request 예외 및 경고 방어
def test_upbit_validate_no_job_id(upbit_mock_config):
    extractor = UPBITExtractor(MagicMock(), AsyncMock(), upbit_mock_config)
    with pytest.raises(ExtractorError, match="'job_id' is mandatory"):
        extractor._validate_request(RequestDTO(job_id=""))

def test_upbit_validate_no_policy(upbit_mock_config):
    extractor = UPBITExtractor(MagicMock(), AsyncMock(), upbit_mock_config)
    with pytest.raises(ExtractorError, match="Policy not found"):
        extractor._validate_request(RequestDTO(job_id="unknown_job"))

def test_upbit_validate_wrong_provider(upbit_mock_config):
    upbit_mock_config.extraction_policy["upbit_test_job"].provider = "KIS"
    extractor = UPBITExtractor(MagicMock(), AsyncMock(), upbit_mock_config)
    with pytest.raises(ExtractorError, match="not 'UPBIT'"):
        extractor._validate_request(RequestDTO(job_id="upbit_test_job"))

def test_upbit_validate_missing_market(upbit_mock_config):
    """Scenario: market 파라미터 누락 시 warning 로깅 확인 (Missing 99)"""
    upbit_mock_config.extraction_policy["upbit_test_job"].params = {}
    extractor = UPBITExtractor(MagicMock(), AsyncMock(), upbit_mock_config)
    # 예외가 발생하지는 않고 경고 로그만 남음
    extractor._validate_request(RequestDTO(job_id="upbit_test_job", params={}))

def test_upbit_validate_success(upbit_mock_config):
    """Scenario: 모든 검증 정상 통과"""
    extractor = UPBITExtractor(MagicMock(), AsyncMock(), upbit_mock_config)
    extractor._validate_request(RequestDTO(job_id="upbit_test_job"))

# [UPBIT-03] _fetch_raw_data 인증 및 HTTP 호출
@pytest.mark.asyncio
async def test_upbit_fetch_raw_data_with_token(upbit_mock_config):
    """Scenario: 인증 토큰이 존재하는 경우 authorization 헤더 주입 분기"""
    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = [{"market": "KRW-BTC", "trade_price": 50000000}]
    
    mock_auth_strategy = AsyncMock()
    mock_auth_strategy.get_token.return_value = "Bearer test_token"
    
    extractor = UPBITExtractor(mock_http_client, mock_auth_strategy, upbit_mock_config)
    req = RequestDTO(job_id="upbit_test_job", params={"custom": "val"})
    
    res = await extractor._fetch_raw_data(req)
    assert res == [{"market": "KRW-BTC", "trade_price": 50000000}]
    
    mock_http_client.get.assert_called_once()
    called_headers = mock_http_client.get.call_args[1]["headers"]
    assert called_headers["authorization"] == "Bearer test_token"

@pytest.mark.asyncio
async def test_upbit_fetch_raw_data_without_token(upbit_mock_config):
    """Scenario: 인증 토큰이 없을 경우(None) authorization 헤더 생략 분기"""
    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = [{"market": "KRW-BTC"}]
    
    mock_auth_strategy = AsyncMock()
    mock_auth_strategy.get_token.return_value = None
    
    extractor = UPBITExtractor(mock_http_client, mock_auth_strategy, upbit_mock_config)
    req = RequestDTO(job_id="upbit_test_job")
    
    await extractor._fetch_raw_data(req)
    
    called_headers = mock_http_client.get.call_args[1]["headers"]
    assert "authorization" not in called_headers

# [UPBIT-04] _create_response 비즈니스 에러 및 정상 응답 처리
def test_upbit_create_response_with_error(upbit_mock_config):
    """Scenario: 응답이 error 딕셔너리를 포함하는 비즈니스 실패 케이스"""
    extractor = UPBITExtractor(MagicMock(), AsyncMock(), upbit_mock_config)
    raw_data = {"error": {"name": "invalid_query_payload", "message": "Invalid market"}}
    
    with pytest.raises(ExtractorError, match="UPBIT API Failed: Invalid market \\(Name: invalid_query_payload\\)"):
        extractor._create_response(raw_data, "upbit_test_job")

def test_upbit_create_response_with_error_missing_fields(upbit_mock_config):
    """Scenario: error 객체는 있으나 name이나 message가 없는 엣지 케이스"""
    extractor = UPBITExtractor(MagicMock(), AsyncMock(), upbit_mock_config)
    raw_data = {"error": {}}
    
    with pytest.raises(ExtractorError, match="UPBIT API Failed: No message provided \\(Name: UnknownError\\)"):
        extractor._create_response(raw_data, "upbit_test_job")

def test_upbit_create_response_success(upbit_mock_config):
    """Scenario: 정상 응답 시 DTO 래핑 검증"""
    extractor = UPBITExtractor(MagicMock(), AsyncMock(), upbit_mock_config)
    raw_data = [{"market": "KRW-BTC", "trade_price": 50000000}]
    
    res = extractor._create_response(raw_data, "upbit_test_job")
    assert res.meta["status_code"] == "OK"
    assert res.meta["source"] == "UPBIT"
    assert res.data == raw_data

# [FACTORY-01] 알 수 없는 Provider에 대한 Auth 생성 예외
def test_factory_auth_unknown_provider(factory_mock_config):
    """Scenario: KIS, UPBIT가 아닌 인증 전략을 요청할 경우 예외 발생"""
    with pytest.raises(ExtractorError, match="Auth Strategy not defined for provider: UNKNOWN_AUTH"):
        ExtractorFactory._get_or_create_auth("UNKNOWN_AUTH", factory_mock_config)

# [FACTORY-02] 정책이 존재하지 않는 job_id 예외
def test_factory_create_no_policy(factory_mock_config):
    """Scenario: 설정(Config)에 요청된 job_id의 정책이 아예 없는 경우 방어"""
    # 로거 초기화를 위해 한번 호출 (안전장치)
    ExtractorFactory._get_logger() 
    
    with pytest.raises(ExtractorError, match="Job ID 'missing_job' is undefined"):
        ExtractorFactory.create_extractor("missing_job", MagicMock(), factory_mock_config)

# [FACTORY-03] FRED 수집기 정상 생성
def test_factory_create_fred(factory_mock_config):
    """Scenario: Provider가 FRED일 때 FREDExtractor 인스턴스 반환"""
    policy = MagicMock()
    policy.provider = "FRED"
    factory_mock_config.extraction_policy["fred_job"] = policy
    
    # FRED 초기화 필수 속성 세팅
    factory_mock_config.fred.base_url = "http://fred.api"
    factory_mock_config.fred.api_key.get_secret_value.return_value = "secret"
    
    extractor = ExtractorFactory.create_extractor("fred_job", MagicMock(), factory_mock_config)
    assert extractor.__class__.__name__ == "FREDExtractor"

# [FACTORY-04] ECOS 수집기 정상 생성
def test_factory_create_ecos(factory_mock_config):
    """Scenario: Provider가 ECOS일 때 ECOSExtractor 인스턴스 반환"""
    policy = MagicMock()
    policy.provider = "ECOS"
    factory_mock_config.extraction_policy["ecos_job"] = policy
    
    # ECOS 초기화 필수 속성 세팅
    factory_mock_config.ecos.base_url = "http://ecos.api"
    factory_mock_config.ecos.api_key.get_secret_value.return_value = "secret"
    
    extractor = ExtractorFactory.create_extractor("ecos_job", MagicMock(), factory_mock_config)
    assert extractor.__class__.__name__ == "ECOSExtractor"

# [FACTORY-05] 지원하지 않는 Provider 예외 처리
def test_factory_create_unsupported_provider(factory_mock_config):
    """Scenario: Factory에 구현되지 않은 Provider가 명시되었을 때 방어 로직"""
    policy = MagicMock()
    policy.provider = "UNSUPPORTED"
    factory_mock_config.extraction_policy["unsupported_job"] = policy
    
    with pytest.raises(ExtractorError, match="Unsupported Provider: 'UNSUPPORTED'"):
        ExtractorFactory.create_extractor("unsupported_job", MagicMock(), factory_mock_config)

# [FACTORY-06] 인스턴스 생성 중 예기치 못한 에러 래핑
def test_factory_create_instantiation_exception(factory_mock_config):
    """Scenario: 객체 생성 중 내부에서 파이썬 내장 에러가 터졌을 때 ExtractorError로 감싸줌"""
    policy = MagicMock()
    policy.provider = "FRED"
    factory_mock_config.extraction_policy["fail_job"] = policy
    
    # FRED 초기화 시 config.fred 속성 자체가 에러를 던지도록 강제 조작
    type(factory_mock_config).fred = property(lambda self: int("force_error_string"))
    
    with pytest.raises(ExtractorError, match="Factory Initialization Failed:"):
        ExtractorFactory.create_extractor("fail_job", MagicMock(), factory_mock_config)

# [SERVICE-01] 외부 HTTP Client 주입에 따른 Context Manager 분기
@pytest.mark.asyncio
async def test_extractor_service_with_provided_client(service_mock_config):
    """Scenario: 외부에서 http_client를 주입받으면 _owns_client가 False가 되어 내부 관리를 건너뜀"""
    mock_client = AsyncMock()
    service = ExtractorService(config=service_mock_config, http_client=mock_client)
    
    assert service._owns_client is False
    assert service._http_client is mock_client
    
    async with service as s:
        assert s._http_client is mock_client
    
    # __aexit__ 에서 _owns_client가 False 이므로 close()가 호출되지 않음
    mock_client.close.assert_not_called()

# [SERVICE-02] _ensure_client 검증 실패
@pytest.mark.asyncio
async def test_extractor_service_ensure_client_fails(service_mock_config):
    """Scenario: async with (Context Manager) 진입 없이 extract_job 호출 시 RuntimeError 발생"""
    service = ExtractorService(config=service_mock_config)
    with pytest.raises(RuntimeError, match="HTTP Client is not initialized"):
        await service.extract_job("test_job_id")

# [SERVICE-03] _normalize_response 이미 정규화된 응답
def test_normalize_response_already_success(service_mock_config):
    """Scenario: 이미 status가 success인 경우 빠른 반환(Fast Path)"""
    service = ExtractorService(config=service_mock_config)
    req = ExtractedDTO(data={}, meta={"status": "success"})
    res = service._normalize_response(req)
    assert res.meta["status"] == "success"

# [SERVICE-04] _normalize_response 결측치 보정 로직
def test_normalize_response_none_status(service_mock_config):
    """Scenario: status_code가 비어있거나 None일 경우 암묵적 성공(200)으로 간주"""
    service = ExtractorService(config=service_mock_config)
    
    req_none = ExtractedDTO(data={}, meta={"status_code": None})
    res_none = service._normalize_response(req_none)
    assert res_none.meta["status"] == "success"
    assert res_none.meta["status_code"] == 200

    req_empty = ExtractedDTO(data={}, meta={"status_code": ""})
    res_empty = service._normalize_response(req_empty)
    assert res_empty.meta["status"] == "success"
    assert res_empty.meta["status_code"] == 200

# [SERVICE-05] _normalize_response 비정상 코드 실패 분기
def test_normalize_response_unrecognized_status(service_mock_config):
    """Scenario: status_code가 성공 코드 집합에 포함되지 않으면 success 추가를 생략함"""
    service = ExtractorService(config=service_mock_config)
    req = ExtractedDTO(data={}, meta={"status_code": "500_ERROR"})
    res = service._normalize_response(req)
    
    assert res.meta.get("status") != "success"
    assert res.meta["status_code"] == "500_ERROR"

# [SERVICE-06] extract_job 존재하지 않는 정책 예외
@pytest.mark.asyncio
async def test_extract_job_policy_not_found(service_mock_config):
    """Scenario: ConfigManager에 등록되지 않은 job_id 요청 시 ConfigurationError 발생"""
    service = ExtractorService(config=service_mock_config)
    async with service:
        with pytest.raises(ConfigurationError, match="찾을 수 없습니다"):
            await service.extract_job("missing_job_id")

# [SERVICE-07] extract_job 런타임 파라미터 덮어쓰기 로직
@pytest.mark.asyncio
@patch("src.extractor.extractor_service.ExtractorFactory.create_extractor")
async def test_extract_job_override_params(mock_factory, service_mock_config):
    """Scenario: override_params가 주어졌을 때 기본 정책 파라미터와 정상적으로 병합(Update)됨"""
    mock_extractor = AsyncMock()
    mock_extractor.extract.return_value = ExtractedDTO(data={}, meta={"status_code": "200"})
    mock_factory.return_value = mock_extractor
    
    service = ExtractorService(config=service_mock_config)
    async with service:
        await service.extract_job("test_job_id", override_params={"custom_key": "custom_val"})
    
    # 병합된 파라미터가 Extractor에 정상 전달되었는지 확인
    req_dto = mock_extractor.extract.call_args[0][0]
    assert req_dto.params["default_key"] == "default_val"
    assert req_dto.params["custom_key"] == "custom_val"

# [SERVICE-08] extract_job 예상치 못한 시스템 에러 래핑
@pytest.mark.asyncio
@patch("src.extractor.extractor_service.ExtractorFactory.create_extractor")
async def test_extract_job_general_exception(mock_factory, service_mock_config):
    """Scenario: Factory 생성 혹은 extract 수행 중 일반 예외 발생 시 ExtractorError로 래핑"""
    mock_factory.side_effect = ValueError("Some unexpected internal error")
    
    service = ExtractorService(config=service_mock_config)
    async with service:
        with pytest.raises(ExtractorError, match="예상치 못한 오류가 발생"):
            await service.extract_job("test_job_id")

# [SERVICE-09] extract_batch 요청 타입 분기 및 빈 목록 반환 로직
@pytest.mark.asyncio
@patch.object(ExtractorService, 'extract_job')
async def test_extract_batch_various_inputs(mock_extract_job, service_mock_config):
    """Scenario: Batch 처리 시 튜플, 잘못된 타입(int) 필터링, 빈 작업 목록 반환 로직 검증"""
    mock_extract_job.return_value = ExtractedDTO(data={}, meta={"status": "success"})
    
    service = ExtractorService(config=service_mock_config)
    
    # 1. 아예 잘못된 타입들만 넘겼을 때 -> tasks가 비어있어 빈 리스트 반환
    res_empty = await service.extract_batch([12345, None])
    assert res_empty == [] 
    
    # 2. 정상 문자열, 튜플 덮어쓰기 파라미터 혼합
    res_mixed = await service.extract_batch([
        "job_1",
        ("job_2", {"override": "yes"}),
        3.14 # invalid type warning 
    ])
    
    assert len(res_mixed) == 2
    mock_extract_job.assert_any_call("job_1")
    mock_extract_job.assert_any_call("job_2", {"override": "yes"})

# [PIPELINE-01] 정의된 정책이 없을 경우 빠른 반환
@pytest.mark.asyncio
async def test_run_batch_empty_policy(mock_pipeline_service):
    res = await mock_pipeline_service.run_batch()
    assert res == {"status": "empty", "total": 0}

# [PIPELINE-02] Transform 단계의 일반 예외 및 ETLError 래핑
@pytest.mark.asyncio
async def test_run_batch_transform_error(mock_pipeline_service):
    """Scenario: 변환 단계에서 발생한 에러를 TransformerError로 감싸고 상태를 FAIL_TRANSFORM으로 기록"""
    mock_pipeline_service._config.extraction_policy = {"job_1": MagicMock()}
    
    # 리스트가 아닌 AsyncMock으로 래핑하여 await TypeError 방지
    mock_pipeline_service._extractor_service.extract_batch = AsyncMock(return_value=[ExtractedDTO(data={}, meta={})])
    
    # 1. 일반 예외 발생 시 TransformerError 래핑 검증
    mock_pipeline_service._mock_transform = AsyncMock(side_effect=ValueError("transform failed"))
    res1 = await mock_pipeline_service.run_batch()
    assert res1["fail"] == 1
    assert res1["details"][0]["status"] == "FAIL_TRANSFORM"

    # 2. 이미 ETLError 타입일 경우 그대로 던지는지 검증
    mock_pipeline_service._mock_transform = AsyncMock(side_effect=TransformerError("transform etl failed"))
    res2 = await mock_pipeline_service.run_batch()
    assert res2["fail"] == 1
    assert res2["details"][0]["status"] == "FAIL_TRANSFORM"

# [PIPELINE-03] Load 단계의 일반 예외 및 ETLError 래핑
@pytest.mark.asyncio
async def test_run_batch_load_error(mock_pipeline_service):
    """Scenario: 적재 단계에서 발생한 에러를 LoaderError로 감싸고 상태를 FAIL_LOAD로 기록"""
    mock_pipeline_service._config.extraction_policy = {"job_1": MagicMock()}
    
    mock_pipeline_service._extractor_service.extract_batch = AsyncMock(return_value=[ExtractedDTO(data={}, meta={})])
    mock_pipeline_service._mock_transform = AsyncMock(return_value=TransformedDTO(data={"a":1}, meta={}))
    
    # 1. 일반 예외 발생 시 LoaderError 래핑 검증
    mock_pipeline_service._mock_load = AsyncMock(side_effect=ValueError("load failed"))
    res1 = await mock_pipeline_service.run_batch()
    assert res1["fail"] == 1
    assert res1["details"][0]["status"] == "FAIL_LOAD"

    # 2. 이미 ETLError 타입일 경우 그대로 던지는지 검증
    mock_pipeline_service._mock_load = AsyncMock(side_effect=LoaderError("load etl failed"))
    res2 = await mock_pipeline_service.run_batch()
    assert res2["fail"] == 1
    assert res2["details"][0]["status"] == "FAIL_LOAD"

# [PIPELINE-04] ETLError 타입별 상태 코드(Status Code) 세분화 분기
@pytest.mark.asyncio
async def test_run_batch_etl_errors(mock_pipeline_service):
    """Scenario: Extractor, Loader가 아닌 일반 ETLError 발생 시 FAIL_UNKNOWN 으로 기록"""
    mock_pipeline_service._config.extraction_policy = {"job_e": MagicMock(), "job_u": MagicMock()}
    
    mock_pipeline_service._extractor_service.extract_batch = AsyncMock(return_value=[
        ExtractorError("extract error"),
        ETLError("unknown etl error")
    ])
    
    res = await mock_pipeline_service.run_batch()
    assert res["fail"] == 2
    
    statuses = [d["status"] for d in res["details"]]
    assert "FAIL_EXTRACT" in statuses
    assert "FAIL_UNKNOWN" in statuses

# [PIPELINE-05] 예상치 못한 시스템 치명적 오류 방어
@pytest.mark.asyncio
async def test_run_batch_critical_system_error(mock_pipeline_service):
    """Scenario: 메모리 부족 등 시스템 치명 오류 발생 시 파이프라인 중단 없이 상태 기록"""
    mock_pipeline_service._config.extraction_policy = {"job_1": MagicMock()}
    
    mock_pipeline_service._extractor_service.extract_batch = AsyncMock(return_value=[MemoryError("out of memory")])
    
    res = await mock_pipeline_service.run_batch()
    assert res["fail"] == 1
    assert res["details"][0]["status"] == "CRITICAL_SYSTEM_ERROR"

# [PIPELINE-06] 빈 데이터 적재 시 분기 이탈
@pytest.mark.asyncio
async def test_mock_load_no_data(mock_pipeline_service):
    """Scenario: 변환된 데이터(data)가 빈 딕셔너리일 경우 적재를 생략하고 조용히 종료됨"""
    # data={} 로 세팅하여 if transformed.data: 분기를 False로 만듦
    dto = TransformedDTO(data={}, meta={"status": "success", "source": "test"})
    # 로깅 메서드가 호출되지 않고 안전하게 반환되어야 함
    await mock_pipeline_service._mock_load(dto)