"""
로깅 모듈 단위 테스트 (Unit Test for Logging Module)

이 테스트 모듈은 src.common.log의 LogManager 및 관련 클래스들이 
설계된 대로 정확히 동작하는지 검증합니다.

주요 검증 포인트:
1. Singleton Pattern: LogManager가 전역에서 유일한 인스턴스를 유지하는지.
2. Configuration Integration: ConfigManager의 설정값(task_name 등)을 제대로 반영하는지.
3. Context Awareness: 비동기 작업 식별을 위한 Request ID가 로그에 주입되는지.
4. JSON Formatting: 로그 출력이 유효한 JSON 포맷인지.
5. File I/O: 지정된 경로에 로그 파일이 실제로 생성되는지.
"""

import pytest
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

# 테스트 대상 모듈 임포트
from src.common.log import LogManager, JsonFormatter

# ==============================================================================
# Fixtures: 테스트 환경 격리 및 Mocking
# ==============================================================================

@pytest.fixture
def mock_config(tmp_path):
    """ConfigManager.get_config()를 Mocking하여 가짜 설정 객체를 주입합니다.

    실제 .env 파일이나 .yml 파일을 읽지 않고, 메모리 상에서 통제 가능한
    설정 값을 제공함으로써 테스트의 결정성(Determinism)을 보장합니다.

    Args:
        tmp_path: pytest가 제공하는 임시 디렉토리 경로. (테스트 후 자동 삭제됨)

    Yields:
        MagicMock: AppConfig를 흉내 내는 Mock 객체.
    """
    with patch("src.common.log.get_config") as mock_get:
        # 가짜 AppConfig 객체 생성
        mock_conf = MagicMock()
        
        # [중요] src/common/log.py 코드에서 사용하는 속성명과 일치시켜야 함
        mock_conf.task_name = "TestTask"      # 로거 이름으로 사용됨
        mock_conf.log_level = "DEBUG"         # 로그 레벨
        mock_conf.log_dir = str(tmp_path / "logs")  # 로그 저장 경로
        
        mock_get.return_value = mock_conf
        yield mock_conf


@pytest.fixture
def reset_singleton():
    """LogManager의 Singleton 상태를 강제로 초기화합니다.

    싱글톤 패턴은 프로세스 내내 상태가 유지되므로, 
    이전 테스트의 로거 설정이 다음 테스트에 영향을 주지 않도록(Test Isolation)
    테스트 실행 전후로 내부 변수를 초기화해야 합니다.
    """
    # Setup: 테스트 시작 전 초기화
    LogManager._instance = None
    LogManager._initialized = False
    
    yield
    
    # Teardown: 테스트 종료 후 초기화 (안전장치)
    LogManager._instance = None
    LogManager._initialized = False
    
    # 생성된 로거의 핸들러도 정리하여 리소스 누수 방지
    logger = logging.getLogger("TestTask")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()


# ==============================================================================
# Test Cases
# ==============================================================================

def test_singleton_behavior(mock_config, reset_singleton):
    """[검증] LogManager가 애플리케이션 전체에서 단 하나의 인스턴스만 유지하는지 확인.
    
    Why: 로거가 여러 개 생성되면 파일 핸들러 충돌이나 로그 중복 출력이 발생할 수 있음.
    """
    # When: 두 번 연속으로 인스턴스 생성 요청
    manager1 = LogManager()
    manager2 = LogManager()
    
    # Then: 두 객체는 메모리 주소가 동일해야 함 (Identity)
    assert manager1 is manager2
    assert id(manager1) == id(manager2)


def test_logger_file_creation(mock_config, reset_singleton, tmp_path):
    """[검증] 로거 초기화 시 설정된 경로에 로그 파일이 실제로 생성되는지 확인.
    
    Why: 파일 권한 문제나 경로 설정 오류를 사전에 감지하기 위함.
    """
    # Given: 예상되는 로그 파일 경로
    expected_log_dir = tmp_path / "logs"
    expected_log_file = expected_log_dir / "app.log"
    
    # 파일이 아직 없는 상태 확인
    assert not expected_log_file.exists()
    
    # When: LogManager 초기화 (get_logger 호출 시 내부적으로 초기화됨)
    _ = LogManager.get_logger()
    
    # Then: 파일이 생성되었는지 확인
    assert expected_log_file.exists()
    assert expected_log_file.is_file()


def test_json_formatting_and_context(mock_config, reset_singleton, capsys):
    """[검증] 로그가 JSON 포맷으로 출력되며, Request ID가 올바르게 주입되는지 확인.
    
    Args:
        capsys: 표준 출력(stdout/stderr)을 캡처하는 pytest 내장 픽스쳐.
    
    Why: ELK 등 로그 수집 시스템 연동을 위해 JSON 구조와 Trace ID가 필수적임.
    """
    # Given 1: 컨텍스트 설정 (Request ID 주입)
    request_id = "req-test-uuid-9999"
    LogManager.set_context(request_id)
    
    # Given 2: 로거 가져오기 및 로그 기록
    logger = LogManager.get_logger()
    test_msg = "Critical system event occurred."
    
    # When: INFO 레벨 로그 기록
    logger.info(test_msg)
    
    # Then 1: 콘솔 출력 캡처 및 확인
    captured = capsys.readouterr()
    # LogManager는 StreamHandler(sys.stdout)를 사용하므로 out을 확인
    log_output = captured.out
    
    assert log_output, "로그가 콘솔에 출력되지 않았습니다."
    
    # Then 2: JSON 유효성 및 필드 값 검증
    try:
        log_json = json.loads(log_output)
    except json.JSONDecodeError:
        pytest.fail(f"로그가 유효한 JSON 형식이 아닙니다: {log_output}")
        
    assert log_json["message"] == test_msg
    assert log_json["level"] == "INFO"
    assert log_json["name"] == "TestTask"      # Mock Config의 task_name 확인
    assert log_json["request_id"] == request_id # ContextFilter 동작 확인
    
    # 필수 메타데이터 존재 확인
    assert "time" in log_json
    assert "file" in log_json
    assert "line" in log_json


def test_child_logger_inheritance(mock_config, reset_singleton):
    """[검증] get_logger(name) 호출 시 부모 로거의 설정을 상속받는 자식 로거가 반환되는지 확인.
    
    Why: 모듈별(Extractor, Transformer)로 로거를 분리하되, 설정(JSON 포맷 등)은 통일해야 함.
    """
    # When: 자식 로거 생성
    child_name = "KISAdapter"
    child_logger = LogManager.get_logger(child_name)
    
    # Then: 로거 이름이 계층 구조('TaskName.ChildName')를 따르는지 확인
    expected_name = "TestTask.KISAdapter"
    assert child_logger.name == expected_name
    
    # 부모 로거가 이미 핸들러를 가지고 있으므로, 자식은 핸들러가 없어야 중복 출력이 안 됨
    # (logging 모듈의 기본 동작: propagate=True이면 부모 핸들러 사용)
    # 하지만 LogManager 구현상 propagate=False로 설정했으므로 
    # LogManager는 Root Logger가 아닌 'TestTask' 로거에 핸들러를 붙임.
    # 자식 로거(TestTask.KISAdapter)는 기본적으로 부모(TestTask)에게 전파됨.
    assert child_logger.parent.name == "TestTask"


def test_exception_logging(mock_config, reset_singleton, capsys):
    """[검증] 예외(Exception) 발생 시 스택 트레이스가 JSON 필드에 포함되는지 확인.
    
    Why: 에러 원인 분석을 위해 스택 트레이스 정보가 필수적임.
    """
    logger = LogManager.get_logger()
    
    try:
        # 고의로 예외 발생
        1 / 0
    except ZeroDivisionError:
        # When: 예외 정보를 포함하여 로그 기록 (exc_info=True 자동 적용)
        logger.error("Calculation failed", exc_info=True)
        
    captured = capsys.readouterr()
    log_json = json.loads(captured.out)
    
    # Then: exception 필드가 존재하고 스택 트레이스 내용이 있는지 확인
    assert "exception" in log_json
    assert "ZeroDivisionError" in log_json["exception"]