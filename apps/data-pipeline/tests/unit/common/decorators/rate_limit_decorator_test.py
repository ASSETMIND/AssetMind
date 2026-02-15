import pytest
import time
import asyncio
import sys
import importlib
import builtins
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock, ANY
from collections import deque
from pathlib import Path

# --------------------------------------------------------------------------
# Environment Setup (Path Injection)
# --------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

# --------------------------------------------------------------------------
# Import Real Objects & Target Class
# --------------------------------------------------------------------------
try:
    from src.common.decorators.rate_limit_decorator import rate_limit, _buckets, RateLimitBucket
except ImportError:
    from src.common.decorators.rate_limit_decorator import rate_limit, _buckets, RateLimitBucket

# --------------------------------------------------------------------------
# 0. Constants & Configuration
# --------------------------------------------------------------------------
TARGET_MODULE = "src.common.decorators.rate_limit_decorator"
TARGET_LOG_MANAGER = f"{TARGET_MODULE}.LogManager"

# --------------------------------------------------------------------------
# 1. Fixtures (Test Environment Setup)
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_global_state():
    """
    [Global State Reset]
    각 테스트 실행 전후로 전역 변수 _buckets를 초기화하여
    테스트 간 상태 오염(State Pollution)을 방지합니다.
    """
    _buckets.clear()
    yield
    _buckets.clear()

@pytest.fixture(autouse=True)
def mock_dependencies():
    """
    [Dependencies Mock]
    LogManager 등 외부 의존성을 전역적으로 Mocking합니다.
    ConfigManager 초기화 에러를 방지하고 순수 로직만 검증합니다.
    """
    with patch(TARGET_LOG_MANAGER) as MockLogManager:
        mock_logger_instance = MagicMock()
        MockLogManager.get_logger.return_value = mock_logger_instance
        
        yield {
            "LogManager": MockLogManager,
            "Logger": mock_logger_instance
        }

# --------------------------------------------------------------------------
# 2. Test Cases
# --------------------------------------------------------------------------

class TestRateLimitDecorator:

    # ==========================================
    # Category: Happy Path (Normal Execution)
    # ==========================================

    def test_tc001_sync_happy_path(self):
        """[TC-001] Sync 함수: limit 내에서 호출 시 즉시 반환 확인"""
        @rate_limit(limit=5, period=1.0)
        def my_func():
            return "ok"

        start_time = time.time()
        for _ in range(5):
            assert my_func() == "ok"
        
        duration = time.time() - start_time
        assert duration < 0.1 

    @pytest.mark.asyncio
    async def test_tc002_async_happy_path(self):
        """[TC-002] Async 함수: limit 내에서 호출 시 즉시 반환 확인"""
        @rate_limit(limit=5, period=1.0)
        async def my_async_func():
            return "async_ok"

        for _ in range(5):
            assert await my_async_func() == "async_ok"

    # ==========================================
    # Category: Throttling Logic (Active)
    # ==========================================

    @patch('time.sleep')
    @patch('time.time')
    def test_tc003_sync_throttling(self, mock_time, mock_sleep):
        """[TC-003] Sync 함수: limit 초과 시 time.sleep 호출 검증"""
        mock_time.return_value = 100.0
        
        @rate_limit(limit=1, period=1.0)
        def rigid_func():
            return True

        # 1. 첫 번째 호출 (성공)
        rigid_func()
        
        # 2. 시간 경과 시뮬레이션 (0.1초 경과 -> 아직 period 안 지남)
        mock_time.return_value = 100.1 
        
        # When: 두 번째 호출 (실패 -> Sleep 발생해야 함)
        # 예상 대기: (100.0 + 1.0) - 100.1 = 0.9
        rigid_func()

        # Then
        mock_sleep.assert_called_once()
        args, _ = mock_sleep.call_args
        assert abs(args[0] - 0.9) < 0.0001

    @pytest.mark.asyncio
    async def test_tc004_async_throttling(self):
        """[TC-004] Async 함수: limit 초과 시 asyncio.sleep 호출 검증"""
        # Given
        with patch('time.time', return_value=100.0):
            @rate_limit(limit=1, period=1.0)
            async def async_rigid():
                return True
            await async_rigid()

        # When
        with patch('time.time', return_value=100.1):
            with patch('asyncio.sleep', new_callable=MagicMock) as mock_async_sleep:
                f = asyncio.Future()
                f.set_result(None)
                mock_async_sleep.return_value = f
                
                await async_rigid()

                # Then
                mock_async_sleep.assert_called_once()
                args, _ = mock_async_sleep.call_args
                assert abs(args[0] - 0.9) < 0.0001

    # ==========================================
    # Category: Boundary Analysis
    # ==========================================

    @patch('time.sleep')
    def test_tc005_boundary_limit(self, mock_sleep):
        """[TC-005] Boundary: 정확히 6번째 호출(Limit=5)에서 스로틀링 발생 검증"""
        @rate_limit(limit=5, period=1.0)
        def boundary_func(): pass

        for i in range(5):
            boundary_func()
        mock_sleep.assert_not_called()

        boundary_func()
        mock_sleep.assert_called_once()

    @patch('time.sleep')
    @patch('time.time')
    def test_tc006_period_expiration(self, mock_time, mock_sleep):
        """[TC-006] Period Expiration: 기간 경과 후 버킷 초기화 검증"""
        mock_time.return_value = 100.0
        @rate_limit(limit=1, period=1.0)
        def refresh_func(): pass
            
        refresh_func()

        # When: Period 경과
        mock_time.return_value = 102.0 
        refresh_func()

        # Then
        mock_sleep.assert_not_called()

    # ==========================================
    # Category: Bucket Logic (State & Math)
    # ==========================================

    @patch('time.sleep')
    def test_tc007_independent_buckets(self, mock_sleep):
        """[TC-007] Bucket Isolation: bucket_key=None일 때 함수별 독립 제한 검증"""
        @rate_limit(limit=1, period=1.0)
        def func_a(): pass

        @rate_limit(limit=1, period=1.0)
        def func_b(): pass

        func_a()
        func_b() 
        mock_sleep.assert_not_called()

    @patch('time.sleep')
    def test_tc008_shared_buckets(self, mock_sleep):
        """[TC-008] Shared Bucket: 동일 bucket_key 사용 시 제한 공유 검증"""
        SHARED_KEY = "API_KEY_1"
        
        @rate_limit(limit=1, period=1.0, bucket_key=SHARED_KEY)
        def func_a(): pass

        @rate_limit(limit=1, period=1.0, bucket_key=SHARED_KEY)
        def func_b(): pass

        func_a()
        func_b()
        mock_sleep.assert_called_once()

    def test_tc009_math_safety_negative_wait_defensive(self):
        """
        [TC-009] Math Safety (Defensive Coding): 
        내부 상태가 꼬여서(예: _cleanup 실패) 이론상 불가능한 
        음수 대기 시간이 계산되더라도, 0.0으로 보정되는지 검증 (Coverage for 'if wait_time < 0')
        """
        # Given
        bucket = RateLimitBucket(limit=1, period=10.0)
        # 강제로 타임스탬프 주입 (현재 시간 100일 때, 80은 이미 만료되었어야 함)
        bucket.timestamps.append(80.0)
        
        # When
        # _cleanup을 Mocking하여 만료된 토큰을 삭제하지 못하게 함 (State Corruption Simulation)
        with patch.object(bucket, '_cleanup', return_value=None):
            with patch('time.time', return_value=100.0):
                # 로직: wait_time = (80 + 10) - 100 = -10
                wait_time = bucket.get_wait_time()
        
        # Then
        # 음수가 아닌 0.0이 반환되어야 함 (Fail-safe)
        assert wait_time == 0.0

    # ==========================================
    # Category: Resource & Exception Handling
    # ==========================================

    @patch('time.time')
    def test_tc010_resource_cleanup(self, mock_time):
        """[TC-010] Resource Cleanup: 오래된 타임스탬프가 정리되는지 확인"""
        mock_time.return_value = 100.0
        @rate_limit(limit=5, period=1.0)
        def resource_func(): pass

        for _ in range(5):
            resource_func()
        
        bucket = _buckets[resource_func.__qualname__]
        assert len(bucket.timestamps) == 5

        mock_time.return_value = 200.0
        resource_func()
        assert len(bucket.timestamps) == 1

    # ==========================================
    # Category: Integration & Logging
    # ==========================================

    @patch('time.sleep')
    def test_tc012_integration_log_output(self, mock_sleep):
        """[TC-012] Integration: LogManager 존재 시 로그 출력 확인"""
        from src.common.decorators.rate_limit_decorator import LogManager as MockLogManager
        
        @rate_limit(limit=1, period=1.0)
        def log_func(): pass

        log_func()
        log_func() 

        MockLogManager.get_logger.assert_called_with("RateLimit")
        mock_logger = MockLogManager.get_logger.return_value
        mock_logger.debug.assert_called()
        assert "Throttling active" in mock_logger.debug.call_args[0][0]

    @patch('time.sleep')
    @patch('time.time')
    def test_tc013_log_threshold_boundary(self, mock_time, mock_sleep):
        """[TC-013] Log Threshold: 0.1s 경계값 테스트 (BVA)"""
        # Given
        from src.common.decorators.rate_limit_decorator import LogManager as MockLogManager
        mock_logger = MockLogManager.get_logger.return_value
        
        @rate_limit(limit=1, period=1.0)
        def noise_func(): pass
        
        # 1. Case: Wait time = 0.1s (정확히 경계) -> 로그 찍히지 않아야 함 (wait_time > 0.1)
        mock_time.return_value = 100.0
        noise_func() # 소진
        
        mock_time.return_value = 100.9 # Wait = 0.1
        noise_func()
        mock_logger.debug.assert_not_called()
        
        # 2. Case: Wait time = 0.1001s (경계 초과) -> 로그 찍혀야 함
        mock_logger.reset_mock()
        # bucket reset
        _buckets.clear()
        
        mock_time.return_value = 200.0
        noise_func() # 소진
        
        mock_time.return_value = 200.8999 # Wait = 0.1001
        noise_func()
        mock_logger.debug.assert_called()

    # ==========================================
    # Category: Concurrency & Thread Safety
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc014_concurrency_async(self):
        """[TC-014] Async Concurrency: 비동기 동시 요청 안전성 검증"""
        limit = 5
        @rate_limit(limit=limit, period=1.0)
        async def concurrent_func():
            return 1

        tasks = [concurrent_func() for _ in range(10)]
        
        with patch('asyncio.sleep', return_value=None):
            with patch('time.time') as mock_time:
                mock_time.return_value = 100.0
                await asyncio.gather(*tasks)
        
        bucket = _buckets[concurrent_func.__qualname__]
        assert len(bucket.timestamps) == 10

    def test_tc015_concurrency_sync_thread_safety(self):
        """[TC-015] Sync Thread Safety: 동기 함수 멀티스레드 환경 안전성 검증"""
        limit = 50 
        @rate_limit(limit=limit, period=1.0)
        def thread_func():
            time.sleep(0.0001) 
            return 1

        _buckets.clear()

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(thread_func) for _ in range(100)]
            for f in futures:
                f.result() 

        bucket = _buckets[thread_func.__qualname__]
        assert len(bucket.timestamps) > 0

    # ==========================================
    # Category: Environment & Import Logic (Coverage 100%)
    # ==========================================

    def test_tc016_import_fallback_logic(self):
        """
        [TC-016] Import Fallback Logic:
        'src.common.log' 모듈이 없을 때 LogManager가 None으로 설정되고
        코드가 크래시 없이 동작하는지 검증 (ImportError 분기)
        """
        target_module_name = "src.common.decorators.rate_limit_decorator"
        
        # 1. 모듈 언로드
        if target_module_name in sys.modules:
            del sys.modules[target_module_name]

        # 2. builtins.__import__ Mocking (ImportError 유발)
        original_import = builtins.__import__
        def side_effect_import(name, *args, **kwargs):
            if name == "src.common.log":
                raise ImportError("Mocked ImportError")
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=side_effect_import):
            # 3. 모듈 재로드 -> ImportError 발생 -> except 블록 실행 -> LogManager = None
            import src.common.decorators.rate_limit_decorator
            importlib.reload(src.common.decorators.rate_limit_decorator)
            
            # 4. 검증: LogManager가 None이어야 함
            assert src.common.decorators.rate_limit_decorator.LogManager is None
            
            # 5. LogManager가 None인 상태에서도 데코레이터가 정상 동작하는지 확인 (Fail-safe)
            @src.common.decorators.rate_limit_decorator.rate_limit(limit=1, period=1.0)
            def safe_func(): return "safe"
            
            assert safe_func() == "safe"

        # Cleanup
        if target_module_name in sys.modules:
            del sys.modules[target_module_name]
        import src.common.decorators.rate_limit_decorator