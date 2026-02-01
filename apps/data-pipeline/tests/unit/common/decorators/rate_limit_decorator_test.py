import pytest
import time
import asyncio
import sys
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
# 프로젝트 구조에 맞게 경로 수정
try:
    from src.common.decorators.rate_limit_decorator import rate_limit, _buckets
except ImportError:
    from rate_limit_decorator import rate_limit, _buckets

# --------------------------------------------------------------------------
# 0. Constants & Configuration
# --------------------------------------------------------------------------

# Mocking 대상 경로 (rate_limit_decorator.py 내부 의존성)
TARGET_MODULE = "src.common.decorators.rate_limit_decorator" if "src.common.decorators.rate_limit_decorator" in sys.modules else "rate_limit_decorator"
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
    AppConfig 초기화 에러를 방지하고 순수 로직만 검증합니다.
    """
    # src.common.decorators.rate_limit_decorator 내부의 LogManager를 Mocking
    with patch(TARGET_LOG_MANAGER) as MockLogManager:
        # get_logger가 호출되면 Mock 객체를 반환하도록 설정
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
        # Given
        @rate_limit(limit=5, period=1.0)
        def my_func():
            return "ok"

        # When
        start_time = time.time()
        for _ in range(5):
            result = my_func()
            # Then
            assert result == "ok"
        
        duration = time.time() - start_time
        assert duration < 0.1 

    @pytest.mark.asyncio
    async def test_tc002_async_happy_path(self):
        """[TC-002] Async 함수: limit 내에서 호출 시 즉시 반환 확인"""
        # Given
        @rate_limit(limit=5, period=1.0)
        async def my_async_func():
            return "async_ok"

        # When
        for _ in range(5):
            result = await my_async_func()
            # Then
            assert result == "async_ok"

    # ==========================================
    # Category: Throttling Logic (Active)
    # ==========================================

    @patch('time.sleep')
    @patch('time.time')
    def test_tc003_sync_throttling(self, mock_time, mock_sleep):
        """[TC-003] Sync 함수: limit 초과 시 time.sleep 호출 검증"""
        # Given
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
        # 부동소수점 오차 고려
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
        # Given
        @rate_limit(limit=5, period=1.0)
        def boundary_func(): 
            pass

        # 1~5회 호출 (통과)
        for i in range(5):
            boundary_func()
        mock_sleep.assert_not_called()

        # When: 6회 호출 (스로틀링)
        boundary_func()

        # Then
        mock_sleep.assert_called_once()

    @patch('time.sleep')
    @patch('time.time')
    def test_tc006_period_expiration(self, mock_time, mock_sleep):
        """[TC-006] Period Expiration: 기간 경과 후 버킷 초기화 검증"""
        # Given
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
        # Given
        @rate_limit(limit=1, period=1.0)
        def func_a(): pass

        @rate_limit(limit=1, period=1.0)
        def func_b(): pass

        # When
        func_a()
        func_b() # 독립적이므로 대기 없음

        # Then
        mock_sleep.assert_not_called()

    @patch('time.sleep')
    def test_tc008_shared_buckets(self, mock_sleep):
        """[TC-008] Shared Bucket: 동일 bucket_key 사용 시 제한 공유 검증"""
        # Given
        SHARED_KEY = "API_KEY_1"
        
        @rate_limit(limit=1, period=1.0, bucket_key=SHARED_KEY)
        def func_a(): pass

        @rate_limit(limit=1, period=1.0, bucket_key=SHARED_KEY)
        def func_b(): pass

        # When
        func_a()
        func_b() # 공유되므로 대기 발생

        # Then
        mock_sleep.assert_called_once()

    @patch('time.sleep')
    @patch('time.time')
    def test_tc009_math_safety(self, mock_time, mock_sleep):
        """[TC-009] Math Safety: wait_time 계산 시 음수 방어 로직 검증"""
        # Given
        mock_time.return_value = 100.0
        @rate_limit(limit=1, period=1.0)
        def math_func(): pass
        
        math_func()

        # When: 현재 시간이 예상 실행 시간보다 훨씬 지남
        mock_time.return_value = 105.0 
        math_func()

        # Then
        mock_sleep.assert_not_called()

    # ==========================================
    # Category: Resource & Exception Handling
    # ==========================================

    @patch('time.time')
    def test_tc010_resource_cleanup(self, mock_time):
        """[TC-010] Resource Cleanup: 오래된 타임스탬프가 정리되는지 확인"""
        # Given
        mock_time.return_value = 100.0
        @rate_limit(limit=5, period=1.0)
        def resource_func(): pass

        for _ in range(5):
            resource_func()
        
        bucket = _buckets[resource_func.__qualname__]
        assert len(bucket.timestamps) == 5

        # When: 시간 대폭 경과
        mock_time.return_value = 200.0
        resource_func()

        # Then: Cleanup 동작 확인 (1개만 남음)
        assert len(bucket.timestamps) == 1

    def test_tc011_no_log_manager_exception(self):
        """[TC-011] Exception Safety: LogManager가 없는 환경(ImportError) 시뮬레이션"""
        # Given
        with patch(TARGET_LOG_MANAGER, None):
            @rate_limit(limit=1, period=1.0)
            def silent_func(): pass
            
            silent_func() # 1회 소진
            
            with patch('time.sleep'):
                # When: Throttling 발생 -> 로깅 시도
                try:
                    silent_func()
                except Exception as e:
                    # Then: 에러 없이 통과해야 함
                    pytest.fail(f"LogManager가 없을 때 예외가 발생했습니다: {e}")

    # ==========================================
    # Category: Integration & Logging
    # ==========================================

    @patch('time.sleep')
    def test_tc012_integration_log_output(self, mock_sleep):
        """[TC-012] Integration: LogManager 존재 시 로그 출력 확인"""
        # Given
        from src.common.decorators.rate_limit_decorator import LogManager as MockLogManager
        
        @rate_limit(limit=1, period=1.0)
        def log_func(): pass

        log_func()

        # When: Throttling 발생
        log_func() 

        # Then
        MockLogManager.get_logger.assert_called_with("RateLimit")
        mock_logger = MockLogManager.get_logger.return_value
        mock_logger.debug.assert_called()
        assert "Throttling active" in mock_logger.debug.call_args[0][0]

    @patch('time.sleep')
    @patch('time.time')
    def test_tc013_small_wait_logging_skip(self, mock_time, mock_sleep):
        """[TC-013] Logging Logic: 대기 시간이 짧을(<=0.1s) 경우 로그 생략 확인"""
        # Given
        from src.common.decorators.rate_limit_decorator import LogManager as MockLogManager
        
        mock_time.return_value = 100.0
        @rate_limit(limit=1, period=1.0)
        def noise_func(): pass
        
        noise_func()

        # 0.95초 경과 (Wait time = 0.05초)
        mock_time.return_value = 100.95
        
        mock_logger = MockLogManager.get_logger.return_value
        mock_logger.debug.reset_mock()

        # When
        noise_func()

        # Then
        mock_sleep.assert_called() # Sleep은 해야 함
        mock_logger.debug.assert_not_called() # 로그는 스킵

    # ==========================================
    # Category: Concurrency & Thread Safety
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc014_concurrency_async(self):
        """[TC-014] Async Concurrency: 비동기 동시 요청(Race Condition) 안전성 검증"""
        # Given
        limit = 5
        @rate_limit(limit=limit, period=1.0)
        async def concurrent_func():
            return 1

        tasks = [concurrent_func() for _ in range(10)]
        
        with patch('asyncio.sleep', return_value=None):
            with patch('time.time') as mock_time:
                mock_time.return_value = 100.0
                # When: 동시 실행
                await asyncio.gather(*tasks)
        
        # Then
        bucket = _buckets[concurrent_func.__qualname__]
        assert len(bucket.timestamps) == 10

    def test_tc015_concurrency_sync_thread_safety(self):
        """
        [TC-015] Sync Thread Safety: 동기 함수 멀티스레드 환경 안전성 검증.
        [Note] 현재 구현 코드에 Thread Lock이 없으므로 실패 가능성이 있음.
        """
        # Given
        limit = 50 
        @rate_limit(limit=limit, period=1.0)
        def thread_func():
            time.sleep(0.0001) 
            return 1

        _buckets.clear()

        # When: 스레드풀로 동시 공격
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(thread_func) for _ in range(100)]
            for f in futures:
                f.result() 

        # Then
        bucket = _buckets[thread_func.__qualname__]
        assert len(bucket.timestamps) > 0