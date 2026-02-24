import pytest
import asyncio
import json
import threading
import sys
import logging
import io
from unittest.mock import MagicMock, patch
from pathlib import Path

# [Target Modules]
from src.common.log import LogManager, JsonFormatter

# ========================================================================================
# [Mocks & Stubs]
# ========================================================================================

class MockConfig:
    def __init__(self, log_level="DEBUG", task_name="TEST_APP", log_dir="logs", **kwargs):
        self.log_level = log_level
        self.task_name = task_name
        self.log_dir = log_dir
        self.log_filename = "test.log"
        for k, v in kwargs.items():
            setattr(self, k, v)

# 테스트용 가짜 커스텀 예외 정의 (ETLError 구조 모방)
class MockETLError(Exception):
    def to_dict(self):
        return {
            "error_code": "ETL-TEST-001",
            "context": "Data Pipeline Failure"
        }

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture(autouse=True)
def setup_testing_env():
    mock_cfg = MockConfig()
    patcher = patch("src.common.config.ConfigManager.get_config", return_value=mock_cfg)
    mock_get_config = patcher.start()

    LogManager._instance = None
    LogManager._initialized = False
    _clear_logger()

    yield mock_get_config

    patcher.stop()
    LogManager._instance = None
    LogManager._initialized = False
    _clear_logger()

def _clear_logger():
    logger = logging.getLogger("TEST_APP")
    handlers = logger.handlers[:]
    for handler in handlers:
        try:
            handler.close()
            logger.removeHandler(handler)
        except Exception:
            pass

@pytest.fixture
def log_stream():
    return io.StringIO()

@pytest.fixture
def log_manager(log_stream):
    with patch("sys.stdout", new=log_stream):
        manager = LogManager()
        return manager

@pytest.fixture
def capture_json_log(log_manager, log_stream):
    def _get_log():
        for handler in log_manager.logger.handlers:
            handler.flush()
        
        output = log_stream.getvalue().strip()
        if not output:
            return None
        
        last_line = output.split('\n')[-1]
        try:
            return json.loads(last_line)
        except json.JSONDecodeError:
            return last_line 
    return _get_log

# ========================================================================================
# 1. 초기화 및 멱등성 (Initialization & Idempotency)
# ========================================================================================

def test_init_01_configuration_loading(setup_testing_env):
    setup_testing_env.return_value = MockConfig(log_level="ERROR")
    manager = LogManager()
    assert manager.logger.level == logging.ERROR
    assert len(manager.logger.handlers) >= 1

def test_idem_01_singleton_reinitialization(log_manager):
    initial_handlers_count = len(log_manager.logger.handlers)
    manager2 = LogManager()
    assert manager2 is log_manager
    assert len(manager2.logger.handlers) == initial_handlers_count

# ========================================================================================
# 2. 포맷팅 및 데이터 무결성 (Formatting & Data Integrity)
# ========================================================================================

def test_fmt_01_json_structure(log_manager, capture_json_log):
    log_manager.logger.info("structure_test")
    log_data = capture_json_log()
    assert log_data is not None
    assert log_data["message"] == "structure_test"
    assert "time" in log_data
    assert "korean_time" in log_data

def test_fmt_02_failsafe_serialization(log_manager, capture_json_log):
    log_manager.logger.info({"data": {1, 2, 3}})
    log_data = capture_json_log()
    assert "{1, 2, 3}" in str(log_data["message"])

def test_fmt_03_boundary_values(log_manager, capture_json_log):
    log_manager.logger.info("Test\nNew\tLine")
    log_data = capture_json_log()
    assert log_data["message"] == "Test\nNew\tLine"

def test_fmt_04_critical_serialization_failure():
    formatter = JsonFormatter()
    record = logging.LogRecord("name", logging.INFO, "path", 10, "msg", args=(), exc_info=None)
    
    with patch("json.dumps", side_effect=[TypeError("Fail"), '{"fallback": "ok"}']):
        result = formatter.format(record)
        assert result == '{"fallback": "ok"}'

def test_fmt_05_etl_error_integration(log_manager, capture_json_log):
    """
    [FMT-05] ETLError(커스텀 예외) 발생 시 구조화된 데이터가 로그에 병합되는지 검증
    Coverage Goal: JsonFormatter 내부의 `if isinstance(exc_value, ETLError):` 분기 커버
    """
    # src.common.log 모듈이 임포트한 ETLError 클래스를 MockETLError로 교체
    with patch("src.common.log.ETLError", new=MockETLError):
        try:
            raise MockETLError("ETL Process Failed")
        except MockETLError:
            log_manager.logger.error("Error occurred", exc_info=True)
            
    log_data = capture_json_log()
    
    # 1. MockETLError.to_dict() 내용이 최상위 필드에 병합되었는지 확인
    assert log_data["error_code"] == "ETL-TEST-001"
    assert log_data["context"] == "Data Pipeline Failure"
    # 2. 스택 트레이스가 별도 필드로 분리되었는지 확인
    assert "stack_trace" in log_data
    assert "exception" not in log_data  # ETLError는 exception 대신 stack_trace 사용

def test_branch_fmt_generic_error():
    formatter = JsonFormatter()
    record = logging.LogRecord("name", logging.INFO, "path", 10, "msg", args=(), exc_info=None)
    
    with patch("json.dumps", side_effect=ValueError("Random Json Error")):
        with pytest.raises(ValueError, match="Random Json Error"):
            formatter.format(record)

# ========================================================================================
# 3. 컨텍스트 격리 (Context Management)
# ========================================================================================

def test_ctx_01_explicit_context_id(log_manager, capture_json_log):
    req_id = "TEST-REQ-123"
    LogManager.set_context(req_id)
    log_manager.logger.info("context check")
    log_data = capture_json_log()
    assert log_data["request_id"] == req_id

def test_ctx_02_auto_generated_id(log_manager, capture_json_log):
    generated_id = LogManager.set_context(None)
    log_manager.logger.info("auto id check")
    log_data = capture_json_log()
    assert len(generated_id) == 36

# ========================================================================================
# 4. 예외 처리 및 견고성 (Exception & Robustness)
# ========================================================================================

def test_exc_01_exception_traceback(log_manager, capture_json_log):
    try:
        raise ValueError("Test Error")
    except ValueError:
        log_manager.logger.exception("Error occurred")
    
    log_data = capture_json_log()
    assert "ValueError: Test Error" in log_data["exception"]

def test_file_01_permission_error_failsafe(capsys):
    """[FILE-01] 로그 파일 디렉토리 생성(mkdir) 실패(OSError) 시 앱이 죽지 않는지 검증"""
    with patch("src.common.log.Path.mkdir", side_effect=OSError("Permission Denied")):
        LogManager()
        captured = capsys.readouterr()
        assert "치명적 오류" in captured.err or "Permission Denied" in captured.err

def test_file_02_handler_setup_os_error(capsys):
    """
    [FILE-02] 디렉토리 생성은 성공했으나, TimedRotatingFileHandler 초기화에서 OSError 발생 시 검증
    Coverage Goal: _setup_file_handler 내부의 try-except 블록을 핸들러 초기화 시점에서 트리거
    """
    with patch("src.common.log.Path.mkdir"), \
         patch("src.common.log.TimedRotatingFileHandler", side_effect=OSError("Disk Full or Locked")):
        
        LogManager()
        
        captured = capsys.readouterr()
        assert "치명적 오류" in captured.err
        assert "Disk Full" in captured.err

# ========================================================================================
# 5. 동시성 및 분기 커버리지 (Concurrency & Branch)
# ========================================================================================

def test_conc_01_multithread_singleton():
    LogManager._instance = None
    LogManager._initialized = False
    instances = []
    
    def get_instance():
        try:
            instances.append(LogManager())
        except Exception:
            pass

    threads = [threading.Thread(target=get_instance) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert len(instances) == 10
    assert all(inst is instances[0] for inst in instances)

@pytest.mark.asyncio
async def test_conc_02_async_context_isolation(log_manager):
    results = {}
    
    async def task_logic(name, req_id):
        LogManager.set_context(req_id)
        await asyncio.sleep(0.01)
        from src.common.log import request_id_ctx
        results[name] = request_id_ctx.get()

    await asyncio.gather(task_logic("A", "ID-A"), task_logic("B", "ID-B"))
    assert results["A"] == "ID-A"
    assert results["B"] == "ID-B"

def test_branch_get_logger_with_name():
    logger_root = LogManager.get_logger()
    assert logger_root.name == "TEST_APP"
    logger_child = LogManager.get_logger("CHILD")
    assert logger_child.name == "TEST_APP.CHILD"

def test_init_skip_handlers_if_exists(setup_testing_env):
    logger = logging.getLogger("TEST_APP")
    dummy_handler = logging.NullHandler()
    logger.addHandler(dummy_handler)
    
    manager = LogManager()
    assert len(manager.logger.handlers) == 1
    assert manager.logger.handlers[0] is dummy_handler

def test_branch_init_config_failure():
    with patch("src.common.config.ConfigManager.get_config", side_effect=RuntimeError("Config Load Error")):
        with pytest.raises(RuntimeError, match="Config Load Error"):
            LogManager()

def test_branch_logger_name_type_safety():
    with pytest.raises(TypeError):
        LogManager.get_logger(999)

def test_branch_init_generic_error(capsys):
    """
    [BRANCH-05] 파일 핸들러 설정 중 예상치 못한 에러(ValueError) 발생 시 전파되는지 검증.
    (OSError는 잡지만 ValueError는 잡지 않는 로직 확인)
    """
    # Fix: 존재하지 않는 FileHandler 패치 코드를 삭제하고, TimedRotatingFileHandler만 패치
    with patch("src.common.log.TimedRotatingFileHandler", side_effect=ValueError("Generic Setup Error")):
        # ValueError는 내부에서 잡지 않으므로 밖으로 던져져야 함 (Fail-Fast)
        try:
            LogManager()
        except ValueError:
            return # 정상적으로 에러가 전파됨

        # 만약 에러를 잡아서 삼켜버렸다면 테스트 실패
        pytest.fail("ValueError should have been propagated")

def test_race_condition_new_creation():
    LogManager._instance = None
    LogManager._initialized = False
    fake_instance = MagicMock()
    
    with patch("src.common.log.LogManager._lock") as mock_lock:
        def simulate_race_condition():
            LogManager._instance = fake_instance
            return True
        mock_lock.__enter__.side_effect = simulate_race_condition
        
        instance = LogManager()
        assert instance is fake_instance

def test_race_condition_init_execution():
    LogManager._instance = None
    LogManager._initialized = False
    manager = LogManager() 
    manager._initialized = False
    
    with patch.object(manager, "_lock") as mock_lock:
        def simulate_init_race():
            manager._initialized = True
            return True
        mock_lock.__enter__.side_effect = simulate_init_race
        
        manager.__init__()
        assert manager._initialized is True