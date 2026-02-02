import pytest
import asyncio
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

# --------------------------------------------------------------------------
# Environment Setup (Path Injection)
# --------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

# --------------------------------------------------------------------------
# Import Real Objects & Target Class
# --------------------------------------------------------------------------
from src.common.decorators import LoggingDecorator

# --------------------------------------------------------------------------
# 0. Constants & Configuration
# --------------------------------------------------------------------------

# Mocking 대상 경로 (log_decorator.py 내부 의존성).
TARGET_LOG_MANAGER = "src.common.decorators.log_decorator.LogManager"
TARGET_CONTEXT = "src.common.decorators.log_decorator.request_id_ctx"
TARGET_JSON = "src.common.decorators.log_decorator.json"

# --------------------------------------------------------------------------
# 1. Fixtures (Test Environment Setup)
# --------------------------------------------------------------------------

@pytest.fixture
def mock_dependencies():
    """
    [Dependencies Mock]
    LogManager와 request_id_ctx를 Mocking하여 외부 의존성을 격리합니다.
    """
    with patch(TARGET_LOG_MANAGER) as MockLogManager, \
         patch(TARGET_CONTEXT) as MockContext:
        
        # 1. Logger Mock 설정
        mock_logger_instance = MagicMock()
        MockLogManager.get_logger.return_value = mock_logger_instance
        
        # 2. Context Mock 설정 (기본값: 'system')
        MockContext.get.return_value = "system"
        
        yield {
            "LogManager": MockLogManager,
            "Context": MockContext,
            "Logger": mock_logger_instance
        }

# --------------------------------------------------------------------------
# 2. Test Cases
# --------------------------------------------------------------------------

class TestLoggingDecorator:
    
    # ==========================================
    # Category: Happy Path (Normal Execution)
    # ==========================================

    def test_tc001_sync_happy_path(self, mock_dependencies):
        """[TC-001] Sync 함수: Context 주입, Start/End 로그 기록, 결과 반환 성공"""
        # Given
        deps = mock_dependencies
        
        @LoggingDecorator()
        def add(a, b):
            return a + b
        
        # When
        result = add(10, 20)
        
        # Then
        assert result == 30
        # 1. Context Auto-Injection 확인
        deps["LogManager"].set_context.assert_called_once()
        # 2. Start/End 로그 호출 확인 (총 2회)
        assert deps["Logger"].info.call_count == 2
        deps["Logger"].info.assert_any_call(ANY)

    @pytest.mark.asyncio
    async def test_tc002_async_happy_path(self, mock_dependencies):
        """[TC-002] Async 함수: Await 처리 지원, 로그 기록, 결과 반환 성공"""
        # Given
        deps = mock_dependencies
        
        @LoggingDecorator()
        async def async_echo(msg):
            await asyncio.sleep(0.01)
            return msg
        
        # When
        result = await async_echo("test")
        
        # Then
        assert result == "test"
        deps["LogManager"].set_context.assert_called_once()
        assert deps["Logger"].info.call_count == 2

    def test_tc003_return_none(self, mock_dependencies):
        """[TC-003] 반환값이 None일 경우: 로그에 문자열 'None'으로 안전하게 기록"""
        # Given
        deps = mock_dependencies
        
        @LoggingDecorator()
        def do_nothing():
            return None
        
        # When
        do_nothing()
        
        # Then
        # 마지막 호출(End Log)의 메시지 검증
        end_log_call = deps["Logger"].info.call_args_list[-1]
        log_msg = end_log_call[0][0]
        assert "Result: None" in log_msg

    # ==========================================
    # Category: Boundary Analysis (Limits)
    # ==========================================

    def test_tc004_no_truncation(self, mock_dependencies):
        """[TC-004] Truncation 미적용: 반환값이 Limit 미만일 때 전체 기록"""
        # Given
        deps = mock_dependencies
        limit = 2000
        short_str = "Short string"
        
        @LoggingDecorator(truncate_limit=limit)
        def return_short():
            return short_str
        
        # When
        return_short()
        
        # Then
        end_log_call = deps["Logger"].info.call_args_list[-1]
        assert f"Result: {short_str}" in end_log_call[0][0]

    def test_tc005_truncation_applied(self, mock_dependencies):
        """[TC-005] Truncation 적용: 반환값이 Limit 초과 시 잘림(...truncated) 처리"""
        # Given
        deps = mock_dependencies
        limit = 10
        long_str = "Long string over limit"
        
        @LoggingDecorator(truncate_limit=limit)
        def return_long():
            return long_str
        
        # When
        return_long()
        
        # Then
        end_log_call = deps["Logger"].info.call_args_list[-1]
        log_msg = end_log_call[0][0]
        assert "Result: Long strin... (truncated" in log_msg

    def test_tc006_empty_args(self, mock_dependencies):
        """[TC-006] 인자가 없을 때: Params가 빈 JSON 객체로 안전하게 기록"""
        # Given
        deps = mock_dependencies
        
        @LoggingDecorator()
        def no_args():
            return "ok"
        
        # When
        no_args()
        
        # Then
        start_log_call = deps["Logger"].info.call_args_list[0]
        assert "Params: {}" in start_log_call[0][0]

    # ==========================================
    # Category: Type Safety & Security (PII)
    # ==========================================

    def test_tc007_pii_masking_exact(self, mock_dependencies):
        """[TC-007] PII Masking: 정확히 일치하는 민감 키워드(password) 마스킹"""
        # Given
        deps = mock_dependencies
        
        @LoggingDecorator()
        def login(id, password):
            pass
        
        # When
        login(id="user", password="secret")
        
        # Then
        start_log_call = deps["Logger"].info.call_args_list[0]
        log_msg = start_log_call[0][0]
        assert '"password": "***** (MASKED)"' in log_msg
        assert "secret" not in log_msg

    def test_tc008_pii_masking_case_insensitive(self, mock_dependencies):
        """[TC-008] PII Masking: 대소문자 혼합 키워드(PaSsWoRd) 마스킹"""
        # Given
        deps = mock_dependencies
        
        @LoggingDecorator()
        def login(**kwargs):
            pass
        
        # When
        login(PaSsWoRd="secret")
        
        # Then
        start_log_call = deps["Logger"].info.call_args_list[0]
        log_msg = start_log_call[0][0]
        assert '"PaSsWoRd": "***** (MASKED)"' in log_msg
        assert "secret" not in log_msg

    def test_tc009_complex_object_serialization(self, mock_dependencies):
        """[TC-009] 복잡한 객체 인자: str() 변환을 통해 안전하게 로깅"""
        # Given
        deps = mock_dependencies
        class ComplexObj:
            def __str__(self):
                return "MyComplexObject"
        
        @LoggingDecorator()
        def process(obj):
            pass
        
        # When
        process(ComplexObj())
        
        # Then
        start_log_call = deps["Logger"].info.call_args_list[0]
        assert "MyComplexObject" in start_log_call[0][0]

    def test_tc010_json_serialization_failure(self, mock_dependencies):
        """[TC-010] JSON 직렬화 실패: 경고 로그를 남기고 함수 실행은 계속 진행(Fail-safe)"""
        # Given
        deps = mock_dependencies
        
        @LoggingDecorator()
        def process(arg):
            return "done"
        
        # json.dumps가 특정 시점에 실패하도록 Mocking
        with patch(f"{TARGET_JSON}.dumps", side_effect=TypeError("JSON Fail")):
            # When
            result = process("something")
            
            # Then
            # 1. 비즈니스 로직은 중단되지 않아야 함
            assert result == "done"
            # 2. Warning 로그가 기록되어야 함
            deps["Logger"].warning.assert_called()
            assert "(Serialization Failed)" in deps["Logger"].warning.call_args[0][0]

    # ==========================================
    # Category: Logical Exceptions
    # ==========================================

    def test_tc011_exception_reraise(self, mock_dependencies):
        """[TC-011] Exception Re-raise: suppress_error=False일 때 예외 전파"""
        # Given
        deps = mock_dependencies
        
        @LoggingDecorator(suppress_error=False)
        def faulty():
            raise ValueError("Boom")
        
        # When & Then
        with pytest.raises(ValueError, match="Boom"):
            faulty()
        
        # Error 로그 기록 확인
        deps["Logger"].error.assert_called_once()
        assert "ValueError - Boom" in deps["Logger"].error.call_args[0][0]

    def test_tc012_exception_suppress(self, mock_dependencies):
        """[TC-012] Exception Suppress: suppress_error=True일 때 예외 무시 및 None 반환"""
        # Given
        deps = mock_dependencies
        
        @LoggingDecorator(suppress_error=True)
        def faulty():
            raise ValueError("Boom")
        
        # When
        result = faulty()
        
        # Then
        assert result is None
        deps["Logger"].error.assert_called_once()

    # ==========================================
    # Category: Resource & State
    # ==========================================

    def test_tc013_context_preservation(self, mock_dependencies):
        """[TC-013] Context 보존: 이미 ID가 존재할 경우 덮어쓰지 않음(Idempotency)"""
        # Given
        deps = mock_dependencies
        # 기존 Context가 설정된 상태 시뮬레이션
        deps["Context"].get.return_value = "existing-id-123"
        
        @LoggingDecorator()
        def action(): pass
        
        # When
        action()
        
        # Then
        # set_context가 호출되지 않아야 함
        deps["LogManager"].set_context.assert_not_called()

    def test_tc014_custom_logger_name(self, mock_dependencies):
        """[TC-014] Custom Logger: 지정된 이름으로 로거 인스턴스 생성"""
        # Given
        deps = mock_dependencies
        custom_name = "custom.logger"
        
        # When
        @LoggingDecorator(logger_name=custom_name)
        def action(): pass
        
        action()
        
        # Then
        deps["LogManager"].get_logger.assert_called_with(custom_name)