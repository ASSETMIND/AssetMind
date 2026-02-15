import pytest
import asyncio
import sys
import json
import importlib
import builtins
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
    # Category: Logical Exceptions (Sync & Async)
    # ==========================================

    def test_tc011_sync_exception_reraise(self, mock_dependencies):
        """[TC-011] Sync Exception Re-raise: suppress_error=False일 때 예외 전파"""
        # Given
        deps = mock_dependencies
        
        @LoggingDecorator(suppress_error=False)
        def faulty():
            raise ValueError("Boom")
        
        # When & Then
        with pytest.raises(ValueError, match="Boom"):
            faulty()
        
        # Error 로그 기록 및 스택 트레이스 확인
        deps["Logger"].error.assert_called_once()
        assert "ValueError - Boom" in deps["Logger"].error.call_args[0][0]
        # exc_info=True가 전달되었는지 확인
        assert deps["Logger"].error.call_args[1].get('exc_info') is True

    def test_tc012_sync_exception_suppress(self, mock_dependencies):
        """[TC-012] Sync Exception Suppress: suppress_error=True일 때 예외 무시 및 None 반환"""
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

    @pytest.mark.asyncio
    async def test_tc013_async_exception_reraise(self, mock_dependencies):
        """[TC-013] Async Exception Re-raise: 비동기 함수 예외 전파 확인"""
        # Given
        deps = mock_dependencies

        @LoggingDecorator(suppress_error=False)
        async def async_faulty():
            raise RuntimeError("Async Boom")

        # When & Then
        with pytest.raises(RuntimeError, match="Async Boom"):
            await async_faulty()
        
        # 로그 확인
        deps["Logger"].error.assert_called_once()
        assert "RuntimeError - Async Boom" in deps["Logger"].error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_tc014_async_exception_suppress(self, mock_dependencies):
        """[TC-014] Async Exception Suppress: 비동기 함수 예외 억제 및 None 반환 확인"""
        # Given
        deps = mock_dependencies

        @LoggingDecorator(suppress_error=True)
        async def async_faulty():
            raise RuntimeError("Async Boom")

        # When
        result = await async_faulty()

        # Then
        assert result is None
        deps["Logger"].error.assert_called_once()

    # ==========================================
    # Category: Resource & State
    # ==========================================

    def test_tc015_context_preservation(self, mock_dependencies):
        """[TC-015] Context 보존: 이미 ID가 존재할 경우 덮어쓰지 않음(Idempotency)"""
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

    def test_tc016_custom_logger_name(self, mock_dependencies):
        """[TC-016] Custom Logger: 지정된 이름으로 로거 인스턴스 생성"""
        # Given
        deps = mock_dependencies
        custom_name = "custom.logger"
        
        # When
        @LoggingDecorator(logger_name=custom_name)
        def action(): pass
        
        action()
        
        # Then
        deps["LogManager"].get_logger.assert_called_with(custom_name)

    def test_tc017_default_logger_name_resolution(self, mock_dependencies):
        """[TC-017] Default Logger Name: 이름 미지정 시 함수의 __module__ 사용 검증"""
        # Given
        deps = mock_dependencies
        
        @LoggingDecorator()
        def action(): pass
        
        # When
        action()
        
        # Then
        # action 함수가 정의된 현재 테스트 모듈의 이름을 사용해야 함
        expected_name = action.__module__
        deps["LogManager"].get_logger.assert_called_with(expected_name)

    # ==========================================
    # Category: Environment & Import Logic (Coverage 100%)
    # ==========================================
    
    def test_tc018_import_fallback_logic(self):
        """
        [TC-018] Import Fallback Logic:
        모듈 로드 시 'src.common.log'를 찾을 수 없을 때(ImportError),
        sys.path를 수정하여 다시 import를 시도하는 except 블록(lines 35-40)을 검증합니다.
        """
        target_module_name = "src.common.decorators.log_decorator"
        
        # 1. 현재 로드된 모듈 제거 (재로딩을 위해)
        if target_module_name in sys.modules:
            del sys.modules[target_module_name]

        # 2. builtins.__import__ Mocking
        # 목적: 첫 번째 'from src.common.log ...' 시도에서 ImportError 발생 유도
        original_import = builtins.__import__

        def side_effect_import(name, globals=None, locals=None, fromlist=(), level=0):
            # 타겟 모듈이 'src.common.log'를 import 하려 할 때
            if name == "src.common.log" and fromlist:
                # 상태 플래그를 함수 속성으로 저장하여 1회만 실패하도록 설정
                # (except 블록에서 재시도할 때는 성공해야 함)
                if not getattr(side_effect_import, 'failed_once', False):
                    side_effect_import.failed_once = True
                    raise ImportError("Forced ImportError for Coverage")
            return original_import(name, globals, locals, fromlist, level)

        # 3. Patch 적용 및 모듈 Import 수행
        with patch('builtins.__import__', side_effect=side_effect_import):
            # 이때 log_decorator.py가 실행되면서:
            # try: import src.common.log -> ImportError (side_effect)
            # except: sys.path.append -> 다시 import src.common.log -> 성공 (failed_once=True)
            try:
                import src.common.decorators.log_decorator
                importlib.reload(src.common.decorators.log_decorator)
            except ImportError:
                pytest.fail("Module import failed even after fallback logic")

        # 4. 검증: 모듈이 정상적으로 로드되었는지 확인
        assert "src.common.decorators.log_decorator" in sys.modules
        
        # 5. Cleanup: 다음 테스트를 위해 모듈을 정상 상태로 다시 로드
        if target_module_name in sys.modules:
            del sys.modules[target_module_name]
        import src.common.decorators.log_decorator