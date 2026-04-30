"""
src.common.log 대상 BDD (Behavior Driven Development) 기반 통합/단위 테스트 코드.
오버 엔지니어링을 배제하고 모든 분기(Branch) 및 예외 처리(Fail-Safe) 로직에 대해
100% Coverage 달성을 목표로 작성된 SDET 표준 테스트 스위트입니다.

[주요 수정 사항]
- JsonFormatter 의 Fall-Safe 테스트 진행 시 발생하는 `json.dumps` 2차 호출 실패 수정 (Coverage 반영)
- ColorFormatter 의 INFO, ERROR 이외의 분기(WARNING, DEBUG) 테스트 추가 (Coverage 반영)
- LogManager.__init__ 내부 이중 검증(Double-Checked Locking) 경합 분기 커버 추가 (Coverage 반영)
"""

import pytest
import logging
import json
import sys
import threading
from unittest.mock import patch, MagicMock
from pathlib import Path
from logging import LogRecord

# [Target Modules]
from src.common.log import (
    LogManager, JsonFormatter, ColorFormatter, ContextFilter,
    request_id_ctx, CTX_KEY_REQUEST_ID, KST_TIMEZONE
)

# ========================================================================================
# [Mocks & Test Doubles]
# ========================================================================================

class MockConfig:
    """테스트용 설정 객체 Mock"""
    def __init__(self, log_level="DEBUG", task_name="TEST_APP", log_dir="logs", **kwargs):
        self.log_level = log_level
        self.task_name = task_name
        self.log_dir = log_dir
        self.log_filename = "test.log"
        for k, v in kwargs.items():
            setattr(self, k, v)

class MockETLError(Exception):
    """도메인 에러(ETLError) 동작을 흉내내는 Mock Class"""
    def to_dict(self):
        return {"error_code": "ETL-001", "context": "Data Context"}

# ========================================================================================
# [Fixtures for Environment Control]
# ========================================================================================

@pytest.fixture(autouse=True)
def reset_singleton_and_logger():
    """
    [CRITICAL] 매 테스트마다 Singleton 상태와 Logger 핸들러를 완벽히 초기화하여 격리성을 보장합니다.
    Root Cause Resolution 원칙에 따라 테스트 간 간섭(Flaky Test)을 원천 차단합니다.
    """
    # GIVEN: 이전 테스트로 인해 오염될 수 있는 전역 상태
    LogManager._instance = None
    LogManager._initialized = False
    
    logger = logging.getLogger("TEST_APP")
    handlers = logger.handlers[:]
    for handler in handlers:
        handler.close()
        logger.removeHandler(handler)
    
    request_id_ctx.set("system")
    
    yield
    
    # THEN: Teardown
    LogManager._instance = None
    LogManager._initialized = False
    logger.handlers.clear()

@pytest.fixture
def mock_config_manager():
    with patch("src.common.config.ConfigManager") as mock_cm:
        yield mock_cm

# ========================================================================================
# 1. Filter & Context Isolation Tests
# ========================================================================================

def test_context_filter_injection():
    """[FLT-01] ContextFilter가 LogRecord에 request_id와 korean_time을 올바르게 주입하는지 검증"""
    # GIVEN: request_id 셋팅 및 빈 LogRecord 생성
    request_id_ctx.set("REQ-TEST-123")
    filter_obj = ContextFilter()
    record = LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test_msg", args=(), exc_info=None)
    
    # WHEN: 필터링 실행
    result = filter_obj.filter(record)
    
    # THEN: 반환값 및 주입된 속성 검증
    assert result is True
    assert hasattr(record, "request_id")
    assert record.request_id == "REQ-TEST-123"
    assert hasattr(record, "korean_time")
    assert isinstance(record.korean_time, str)

# ========================================================================================
# 2. JsonFormatter Data Integrity & Fail-Safe Tests
# ========================================================================================

def test_json_formatter_format_time():
    """[JFMT-01] formatTime 메서드가 UTC 기반 ISO 8601 문자열('Z' 치환)을 정확히 반환하는지 검증"""
    # GIVEN: 포매터 인스턴스 및 타임스탬프 고정
    formatter = JsonFormatter()
    record = LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="", args=(), exc_info=None)
    record.created = 1609459200.0  # 2021-01-01 00:00:00 UTC
    
    # WHEN: 포맷 적용
    time_str = formatter.formatTime(record)
    
    # THEN: 시간 정합성 확인
    assert time_str == "2021-01-01T00:00:00Z"

def test_json_formatter_with_domain_etl_error():
    """[JFMT-02] ETLError 발생 시 to_dict() 페이로드가 로그 최상위에 병합되는지 검증"""
    # GIVEN: 도메인 에러 발생 상황 구성
    formatter = JsonFormatter()
    try:
        raise MockETLError("Pipeline Failed")
    except MockETLError:
        exc_info = sys.exc_info()
        
    record = LogRecord(name="test", level=logging.ERROR, pathname="", lineno=0, msg="Error", args=(), exc_info=exc_info)
    
    # Mocking: 로직 내부에서 ETLError 인스턴스 판단 수행
    with patch("src.common.log.ETLError", MockETLError):
        # WHEN: Json 포맷팅 수행
        json_str = formatter.format(record)
        log_data = json.loads(json_str)
        
        # THEN: 에러 속성 병합 및 Stack Trace 기록 검증
        assert log_data["error_code"] == "ETL-001"
        assert log_data["context"] == "Data Context"
        assert "stack_trace" in log_data

def test_json_formatter_with_generic_error():
    """[JFMT-03] 일반 예외 발생 시 exception 필드에 스택 트레이스가 기록되는지 검증"""
    # GIVEN: 시스템 및 알 수 없는 예외 발생 상황 구성
    formatter = JsonFormatter()
    try:
        raise ValueError("Standard Exception")
    except ValueError:
        exc_info = sys.exc_info()
        
    record = LogRecord(name="test", level=logging.ERROR, pathname="", lineno=0, msg="Error", args=(), exc_info=exc_info)
    
    with patch("src.common.log.ETLError", MockETLError):
        # WHEN: Json 포맷팅 수행
        json_str = formatter.format(record)
        log_data = json.loads(json_str)
        
        # THEN: Exception 항목에 에러 메세지 기록 검증
        assert "exception" in log_data
        assert "ValueError: Standard Exception" in log_data["exception"]

def test_json_formatter_failsafe_serialization_crash():
    """[JFMT-04] 극한 상황: json.dumps 첫 호출 실패 시 메인 프로세스 중단 없이 백업 메시지가 출력되는지 검증"""
    # GIVEN: 직렬화 예외 가능 레코드
    formatter = JsonFormatter()
    record = LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="Critical Data", args=(), exc_info=None)
    
    # WHEN: 첫 번째 json.dumps는 Exception을 던지고, except 블록 내부의 두 번째 호출은 성공하도록 분리
    mock_fallback_json = '{"level": "ERROR", "message": "치명적 오류: 로그 메시지 직렬화 실패", "raw_message": "Critical Data"}'
    
    with patch("json.dumps", side_effect=[Exception("Fatal Memory Error"), mock_fallback_json]):
        json_str = formatter.format(record)
        
    # THEN: 애플리케이션 크래시 없이 백업 직렬화 데이터가 정상 반환되어야 함
    log_data = json.loads(json_str)
    assert log_data["level"] == "ERROR"
    assert "치명적 오류" in log_data["message"]
    assert log_data["raw_message"] == "Critical Data"

# ========================================================================================
# 3. ColorFormatter Visual Logic Tests
# ========================================================================================

def test_color_formatter_pascal_case():
    """[CFMT-01] 스네이크 케이스 및 단일 단어 모듈명이 파스칼 케이스로 올바르게 변환되는지 검증"""
    # GIVEN
    formatter = ColorFormatter()
    
    # WHEN & THEN
    assert formatter._format_name_to_pascal("pipeline_service") == "PipelineService"
    assert formatter._format_name_to_pascal("app") == "App"
    assert formatter._format_name_to_pascal("KISAuth") == "KISAuth"
    assert formatter._format_name_to_pascal("") == ""

def test_color_formatter_format_logic():
    """[CFMT-02] 로깅 레벨 및 특정 키워드(START, END, 요약)에 따른 ANSI 색상 분기 검증"""
    # GIVEN: 임의 레코드 생성 헬퍼 함수
    formatter = ColorFormatter()
    
    def create_record(level, msg, req_id="system"):
        rec = LogRecord("test.module", level, "", 0, msg, (), None)
        rec.request_id = req_id
        rec.korean_time = "2026-03-24 12:00:00"
        return rec

    # WHEN
    res_error = formatter.format(create_record(logging.ERROR, "에러발생"))
    res_info_summary = formatter.format(create_record(logging.INFO, "작업 요약 정보"))
    res_info_start = formatter.format(create_record(logging.INFO, "Process START"))
    res_info_end = formatter.format(create_record(logging.INFO, "Process END | Done"))
    res_info_reqid = formatter.format(create_record(logging.INFO, "일반메시지", "1234567890-UUID"))
    
    # THEN
    assert formatter.COLORS["ERROR"] in res_error
    assert formatter.SUMMARY_COLOR in res_info_summary
    assert formatter.START_COLOR in res_info_start
    assert formatter.END_COLOR in res_info_end
    # 긴 UUID는 8자리로 단축되는지 확인
    assert "[12345678]" in res_info_reqid

def test_color_formatter_other_levels():
    """[CFMT-03] WARNING, DEBUG 레벨 로깅 시 메시지 원본 우회(Bypass) 분기 커버리지 검증"""
    # GIVEN: 조건 분기가 존재하지 않는 기타 레벨
    formatter = ColorFormatter()
    rec_warn = LogRecord("test", logging.WARNING, "", 0, "경고 메시지", (), None)
    rec_debug = LogRecord("test", logging.DEBUG, "", 0, "디버그 메시지", (), None)
    
    # WHEN
    res_warn = formatter.format(rec_warn)
    res_debug = formatter.format(rec_debug)
    
    # THEN: 별도의 조작 없이 메시지 텍스트가 올바르게 렌더링 되어야 함
    assert "경고 메시지" in res_warn
    assert "디버그 메시지" in res_debug

# ========================================================================================
# 4. LogManager Initialization & Concurrency Tests
# ========================================================================================

def test_log_manager_singleton_and_skip_init(mock_config_manager):
    """[INIT-01] 싱글톤 반환 보장 및 __init__ 재호출 방어 로직 검증"""
    # GIVEN: 빈 캐시로 ConfigManager 초기화 유도
    mock_config_manager._cache = {}
    mock_config_manager.return_value = MockConfig()
    
    # WHEN: 연속 호출
    manager1 = LogManager()
    manager2 = LogManager()
    
    # THEN: 동일 객체 검증 및 불필요한 초기화 회피(config 로딩 1회 호출)
    assert manager1 is manager2
    assert manager1._initialized is True
    mock_config_manager.assert_called_once()

def test_log_manager_init_with_config_cache(mock_config_manager):
    """[INIT-02] ConfigManager._cache에 데이터가 있을 경우 인스턴스를 새로 생성하지 않고 꺼내 쓰는지 검증"""
    # GIVEN: 사전에 초기화된 캐시 주입
    cached_config = MockConfig(task_name="CACHE_APP")
    mock_config_manager._cache = {"config": cached_config}
    
    # WHEN: 매니저 초기화
    manager = LogManager()
    
    # THEN: ConfigManager() 클래스가 신규 생성되지 않고 캐시된 설정이 적용됨
    assert manager.task_name == "CACHE_APP"
    mock_config_manager.assert_not_called()

def test_log_manager_duplicate_handler_defense(mock_config_manager):
    """[INIT-03] 로거에 이미 핸들러가 부착된 경우 중복 부착을 방지하는 분기 검증"""
    # GIVEN
    mock_config_manager._cache = {}
    mock_config_manager.return_value = MockConfig()
    
    # 인위적으로 핸들러 하나를 미리 부착
    logger = logging.getLogger("TEST_APP")
    logger.addHandler(logging.NullHandler())
    
    # WHEN
    manager = LogManager()
    
    # THEN: NullHandler 1개만 유지되며 Console/File Handler가 중복 추가되지 않아야 함
    assert len(manager.logger.handlers) == 1
    assert isinstance(manager.logger.handlers[0], logging.NullHandler)

def test_log_manager_init_race_condition_inside_lock(mock_config_manager):
    """[INIT-04] __init__ 내부 Lock 획득 후 이미 초기화 된 경우(_initialized=True) 분기 방어 검증"""
    # GIVEN: 매니저 객체 임의 생성
    manager = LogManager.__new__(LogManager)
    manager._initialized = False
    
    # WHEN: Lock을 획득하는 찰나 타 스레드가 이미 초기화를 끝마쳤다고 가정
    with patch.object(manager, "_lock") as mock_lock:
        def simulate_race(*args, **kwargs):
            manager._initialized = True
            return MagicMock()
        mock_lock.__enter__.side_effect = simulate_race
        
        manager.__init__()
        
    # THEN: Lock 획득 후 _initialized 검사에 의해 하위 Config 관련 로직은 호출되지 않아야 함
    mock_config_manager.assert_not_called()

def test_log_manager_file_handler_os_error(mock_config_manager, capsys):
    """[FILE-01] 권한 문제 등 OSError 발생 시 앱 중단 없이 sys.stderr로 전파하는 Fail-Safe 검증"""
    # GIVEN
    mock_config_manager._cache = {}
    mock_config_manager.return_value = MockConfig()
    
    # WHEN: 디렉토리 생성(mkdir) 시 OSError 발생 강제
    with patch.object(Path, "mkdir", side_effect=OSError("Permission Denied")):
        LogManager()
        
    # THEN: Exception이 상위로 던져지지 않고 표준 에러(stderr)에 기록됨
    captured = capsys.readouterr()
    assert "치명적 오류" in captured.err
    assert "Permission Denied" in captured.err

def test_log_manager_concurrency_lock():
    """[CONC-02] 멀티스레드 경합 상태에서 Double-Checked Locking의 두 번째 분기(__new__ 생성 간섭) 검증"""
    # GIVEN
    LogManager._instance = None
    fake_instance = MagicMock()
    
    # WHEN: Lock을 획득하고 진입했을 때, 이미 다른 스레드가 인스턴스를 생성한 상황 모방
    with patch.object(LogManager, "_lock") as mock_lock:
        def simulate_race(*args, **kwargs):
            LogManager._instance = fake_instance
            return MagicMock()
        
        mock_lock.__enter__.side_effect = simulate_race
        instance = LogManager()
        
    # THEN: 새 인스턴스를 만들지 않고 기존(fake) 인스턴스를 반환해야 함
    assert instance is fake_instance

# ========================================================================================
# 5. LogManager Utilities (Context, Logger Hierarchy)
# ========================================================================================

def test_log_manager_get_logger(mock_config_manager):
    """[LOG-01, LOG-02] get_logger 메서드의 계층 구조(Root vs Child) 생성 검증"""
    # GIVEN
    mock_config_manager._cache = {}
    mock_config_manager.return_value = MockConfig(task_name="BASE")
    
    # WHEN
    root_logger = LogManager.get_logger()
    child_logger = LogManager.get_logger("DB_MODULE")
    
    # THEN: 마침표 기반의 계층 네임스페이스 확인
    assert root_logger.name == "BASE"
    assert child_logger.name == "BASE.DB_MODULE"

def test_log_manager_set_context():
    """[CTX-01, CTX-02] set_context 파라미터 유무에 따른 고유 ID 생성 분기 검증"""
    # WHEN 1: 명시적 ID 제공
    explicit_id = LogManager.set_context("MY-REQ-001")
    
    # THEN 1
    assert explicit_id == "MY-REQ-001"
    assert request_id_ctx.get() == "MY-REQ-001"
    
    # WHEN 2: 파라미터 미제공 (UUID 자동 생성)
    auto_id = LogManager.set_context()
    
    # THEN 2
    assert auto_id != "MY-REQ-001"
    assert len(auto_id) == 36  # UUID v4 문자열 길이
    assert request_id_ctx.get() == auto_id