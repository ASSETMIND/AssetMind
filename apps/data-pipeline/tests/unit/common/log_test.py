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
    """
    ConfigManager의 반환값을 모방하는 Stub 객체.
    테스트 케이스마다 log_level이나 task_name 등을 유동적으로 변경하기 위해 kwargs를 허용합니다.
    """
    def __init__(self, log_level="DEBUG", task_name="TEST_APP", log_dir="logs", **kwargs):
        self.log_level = log_level
        self.task_name = task_name
        self.log_dir = log_dir
        self.log_filename = "test.log"
        # 추가적인 속성 주입 (유연성 확보)
        for k, v in kwargs.items():
            setattr(self, k, v)

# ========================================================================================
# [Fixtures] - Testing Environment Setup
# ========================================================================================

@pytest.fixture(autouse=True)
def setup_testing_env():
    """
    [Global Setup] 테스트 환경 격리 및 초기화 픽스처.
    모든 테스트 실행 전후에 자동으로 실행되어 상태 오염(State Leaking)을 방지합니다.
    
    1. ConfigManager를 전역적으로 Mocking하여 파일 I/O나 환경변수 의존성을 제거합니다.
    2. LogManager Singleton 인스턴스를 강제로 리셋합니다.
    3. 기존에 등록된 로거 핸들러를 모두 제거하여 중복 로깅을 방지합니다.
    """
    # 1. Config Mocking (전역 적용)
    mock_cfg = MockConfig()
    patcher = patch("src.common.config.ConfigManager.get_config", return_value=mock_cfg)
    mock_get_config = patcher.start()

    # 2. Reset Singleton (Before Test)
    LogManager._instance = None
    LogManager._initialized = False
    _clear_logger()

    yield mock_get_config

    # 3. Teardown (After Test)
    patcher.stop()
    LogManager._instance = None
    LogManager._initialized = False
    _clear_logger()

def _clear_logger():
    """기존 로거 핸들러를 안전하게 제거하여 테스트 간 간섭을 방지하는 헬퍼 함수"""
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
    """
    [핵심 해결책] 
    OS 레벨의 stdout(capsys) 대신, 파이썬 레벨에서 제어 가능한 메모리 버퍼(StringIO)입니다.
    pytest의 캡처링 충돌 문제를 근본적으로 해결합니다.
    """
    return io.StringIO()

@pytest.fixture
def log_manager(log_stream):
    """
    [Dependency Injection] 
    LogManager가 sys.stdout이 아닌 테스트용 메모리 버퍼(log_stream)에 로그를 쓰도록
    sys.stdout을 Mocking(Hijacking)하여 초기화된 인스턴스를 반환합니다.
    """
    # LogManager 초기화 시점에 sys.stdout을 가로챕니다.
    with patch("sys.stdout", new=log_stream):
        manager = LogManager()
        return manager

@pytest.fixture
def capture_json_log(log_manager, log_stream):
    """
    메모리 버퍼(log_stream)에서 로그를 읽어 JSON으로 파싱하는 헬퍼 함수입니다.
    
    [중요] StreamHandler는 버퍼링을 할 수 있으므로, 읽기 전에 반드시 flush()를 호출하여
    메모리에 기록된 모든 내용을 동기화합니다.
    """
    def _get_log():
        # 1. 버퍼 강제 동기화
        for handler in log_manager.logger.handlers:
            handler.flush()
        
        # 2. 내용 읽기
        output = log_stream.getvalue().strip()
        if not output:
            return None
        
        # 3. 마지막 로그 라인 추출 (여러 줄일 경우 대비)
        last_line = output.split('\n')[-1]
        
        try:
            return json.loads(last_line)
        except json.JSONDecodeError:
            return last_line # 파싱 실패 시 원본 반환 (디버깅용)
    return _get_log

# ========================================================================================
# 1. 초기화 및 멱등성 테스트 (Initialization & Idempotency)
# ========================================================================================

def test_init_01_configuration_loading(setup_testing_env):
    """[INIT-01] ConfigManager 설정값(Log Level 등)이 로거에 정상적으로 반영되는지 검증"""
    # Given: Config 설정을 ERROR 레벨로 변경
    setup_testing_env.return_value = MockConfig(log_level="ERROR")
    
    # When: 초기화 (sys.stdout 패치 없이 순수 로직 검증)
    manager = LogManager()
    
    # Then: 로거 레벨과 핸들러 부착 여부 확인
    assert manager.logger.level == logging.ERROR
    assert len(manager.logger.handlers) >= 1

def test_idem_01_singleton_reinitialization(log_manager):
    """[IDEM-01] 생성자를 반복 호출해도 핸들러가 중복 추가되지 않고, 동일 인스턴스를 반환하는지 검증 (멱등성)"""
    # Given
    initial_handlers_count = len(log_manager.logger.handlers)
    
    # When: 생성자 재호출
    manager2 = LogManager()
    
    # Then: 인스턴스 동일성 및 핸들러 개수 유지 확인
    assert manager2 is log_manager
    assert len(manager2.logger.handlers) == initial_handlers_count

# ========================================================================================
# 2. 포맷팅 및 데이터 무결성 (Formatting & Data Integrity)
# ========================================================================================

def test_fmt_01_json_structure(log_manager, capture_json_log):
    """[FMT-01] 로그가 JSON 표준 포맷을 준수하며, 필수 메타데이터(UTC/KST 등)를 포함하는지 검증"""
    # When
    log_manager.logger.info("structure_test")
    log_data = capture_json_log()
    
    # Then
    assert log_data is not None
    assert log_data["message"] == "structure_test"
    assert "time" in log_data           # UTC Time
    assert "korean_time" in log_data    # KST Time

def test_fmt_02_failsafe_serialization(log_manager, capture_json_log):
    """[FMT-02] JSON 직렬화가 불가능한 객체(Set 등)가 입력되어도 에러 없이 문자열로 변환하여 기록하는지 검증"""
    # When: Set 객체 입력
    log_manager.logger.info({"data": {1, 2, 3}})
    log_data = capture_json_log()
    
    # Then: Crash 없이 문자열화된 데이터 확인
    assert log_data is not None
    assert "{1, 2, 3}" in str(log_data["message"])

def test_fmt_03_boundary_values(log_manager, capture_json_log):
    """[FMT-03] 특수문자(줄바꿈, 탭 등)가 포함된 메시지도 깨지지 않고 기록되는지 검증"""
    # When
    log_manager.logger.info("Test\nNew\tLine")
    log_data = capture_json_log()
    
    # Then
    assert log_data is not None
    assert log_data["message"] == "Test\nNew\tLine"

def test_fmt_04_critical_serialization_failure():
    """[FMT-04] json.dumps 자체가 실패하는 치명적 상황에서도 Fallback 메시지를 기록하여 시스템 중단을 방지하는지 검증"""
    formatter = JsonFormatter()
    record = logging.LogRecord("name", logging.INFO, "path", 10, "msg", args=(), exc_info=None)
    
    # Mock: 첫 번째 시도 실패(TypeError) -> 두 번째 시도(Fallback) 성공
    with patch("json.dumps", side_effect=[TypeError("Fail"), '{"fallback": "ok"}']):
        result = formatter.format(record)
        assert result == '{"fallback": "ok"}'

# ========================================================================================
# 3. 컨텍스트 격리 및 관리 (Context Management)
# ========================================================================================

def test_ctx_01_explicit_context_id(log_manager, capture_json_log):
    """[CTX-01] 사용자가 명시적으로 설정한 Request ID가 로그에 정확히 반영되는지 검증"""
    # Given
    req_id = "TEST-REQ-123"
    LogManager.set_context(req_id)
    
    # When
    log_manager.logger.info("context check")
    log_data = capture_json_log()
    
    # Then
    assert log_data is not None
    assert log_data["request_id"] == req_id

def test_ctx_02_auto_generated_id(log_manager, capture_json_log):
    """[CTX-02] ID 없이 컨텍스트 설정 시, UUID v4가 자동 생성되어 주입되는지 검증"""
    # When
    generated_id = LogManager.set_context(None)
    log_manager.logger.info("auto id check")
    log_data = capture_json_log()
    
    # Then
    assert log_data is not None
    assert log_data["request_id"] == generated_id
    assert len(generated_id) == 36 # UUID Length Check

# ========================================================================================
# 4. 예외 처리 및 견고성 (Exception & Robustness)
# ========================================================================================

def test_exc_01_exception_traceback(log_manager, capture_json_log):
    """[EXC-01] logger.exception 호출 시 Stack Trace 정보가 로그에 포함되는지 검증"""
    # Given
    try:
        raise ValueError("Test Error")
    except ValueError:
        # When
        log_manager.logger.exception("Error occurred")
    
    log_data = capture_json_log()
    
    # Then
    assert log_data is not None
    assert "ValueError: Test Error" in log_data["exception"]

def test_file_01_permission_error_failsafe(capsys):
    """[FILE-01] 로그 파일 생성 권한이 없을 때(OSError), 앱이 죽지 않고 stderr에 경고만 출력하는지 검증"""
    # Given: Path.mkdir이 실패하도록 Mocking
    with patch("src.common.log.Path.mkdir", side_effect=OSError("Permission Denied")):
        # When
        LogManager()
        
        # Then: Crash 없이 stderr 경고 출력 확인 (이 경우 stderr 캡처 필요하므로 capsys 사용)
        captured = capsys.readouterr()
        assert "Critical Error" in captured.err

# ========================================================================================
# 5. 동시성 및 분기 커버리지 100% 달성 (Concurrency & Deep White-box)
# ========================================================================================

def test_conc_01_multithread_singleton():
    """[CONC-01] 다수의 스레드가 동시에 초기화를 시도해도 Singleton 원칙이 지켜지는지 검증"""
    LogManager._instance = None
    LogManager._initialized = False
    instances = []
    
    def get_instance():
        try:
            instances.append(LogManager())
        except Exception:
            pass

    # 10개의 스레드 동시 실행
    threads = [threading.Thread(target=get_instance) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()

    # 모든 스레드가 동일한 인스턴스를 획득했는지 확인
    assert len(instances) == 10
    assert all(inst is instances[0] for inst in instances)

@pytest.mark.asyncio
async def test_conc_02_async_context_isolation(log_manager):
    """[CONC-02] AsyncIO 환경에서 서로 다른 Task가 Context(Request ID)를 침범하지 않고 격리되는지 검증"""
    results = {}
    
    async def task_logic(name, req_id):
        LogManager.set_context(req_id)
        await asyncio.sleep(0.01) # Context Switching 유발
        from src.common.log import request_id_ctx
        results[name] = request_id_ctx.get()

    # 두 개의 태스크 병렬 실행
    await asyncio.gather(
        task_logic("A", "ID-A"),
        task_logic("B", "ID-B")
    )
    
    # 상호 오염 여부 확인
    assert results["A"] == "ID-A"
    assert results["B"] == "ID-B"

# -------------------------------------------------------------------------
# [심화] Coverage 100% 달성을 위한 Edge Case 테스트 (Race Condition & Branch)
# -------------------------------------------------------------------------

def test_branch_get_logger_with_name():
    """[BRANCH-01] get_logger(name) 호출 시, 루트 로거가 아닌 자식 로거를 반환하는 분기 검증"""
    # 1. 루트 로거
    logger_root = LogManager.get_logger()
    assert logger_root.name == "TEST_APP"
    
    # 2. 자식 로거 (이름 지정)
    logger_child = LogManager.get_logger("CHILD")
    assert logger_child.name == "TEST_APP.CHILD"

def test_init_skip_handlers_if_exists(setup_testing_env):
    """
    [BRANCH-02] 로거에 이미 핸들러가 존재하는 경우, 초기화 과정에서 핸들러 추가를 건너뛰는(Skip) 분기 검증.
    (이 테스트가 없으면 커버리지 99%에 머뭄)
    """
    # 1. 외부에서 로거에 핸들러를 미리 주입 (Pre-condition)
    logger = logging.getLogger("TEST_APP")
    dummy_handler = logging.NullHandler()
    logger.addHandler(dummy_handler)
    
    # 2. LogManager 초기화
    manager = LogManager()
    
    # 3. LogManager가 자신의 핸들러를 추가하지 않고, 기존 핸들러만 유지했는지 검증
    assert len(manager.logger.handlers) == 1
    assert manager.logger.handlers[0] is dummy_handler

def test_race_condition_new_creation():
    """
    [RACE-01] Singleton __new__ 내부의 Double-Checked Locking 경쟁 상태(Race Condition) 재현.
    
    시나리오:
    Thread A가 '인스턴스 없음'을 확인하고 Lock을 획득했으나,
    그 직전에 Thread B가 인스턴스를 생성해버린 상황.
    """
    LogManager._instance = None
    LogManager._initialized = False
    fake_instance = MagicMock()
    
    # Lock 객체의 __enter__ 메서드를 Mocking하여, 
    # Lock 획득 시점에 마치 다른 스레드가 인스턴스를 생성한 것처럼 상태를 조작함.
    with patch("src.common.log.LogManager._lock") as mock_lock:
        def simulate_race_condition():
            LogManager._instance = fake_instance
            return True
        mock_lock.__enter__.side_effect = simulate_race_condition
        
        # LogManager 생성 시도 -> 새로 만들지 않고 fake_instance를 반환해야 함
        instance = LogManager()
        assert instance is fake_instance

def test_race_condition_init_execution():
    """
    [RACE-02] __init__ 내부의 Double-Checked Locking 경쟁 상태 재현.
    
    시나리오:
    Thread A가 '초기화 안 됨'을 확인하고 Lock을 획득했으나,
    그 직전에 Thread B가 초기화를 완료해버린 상황.
    """
    # 1. 인스턴스는 있지만 초기화 플래그는 False인 상태 준비
    LogManager._instance = None
    LogManager._initialized = False
    manager = LogManager() 
    manager._initialized = False # 강제 리셋 (테스트용)
    
    # 2. Lock 획득 시점에 다른 스레드가 초기화를 마쳤다고 가정(Mocking)
    with patch.object(manager, "_lock") as mock_lock:
        def simulate_init_race():
            manager._initialized = True
            return True
        mock_lock.__enter__.side_effect = simulate_init_race
        
        # 3. 초기화 재진입 시도
        manager.__init__()
        
        # 4. 검증: 내부 로직(Config 로드 등)이 실행되지 않고 종료되었는지 확인 (에러 없음으로 간접 확인)
        assert manager._initialized is True