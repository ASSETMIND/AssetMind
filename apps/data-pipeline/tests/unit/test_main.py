import pytest
import importlib
from unittest.mock import MagicMock, patch, AsyncMock

# [Target Modules]
# 근본 원인 해결: src 디렉터리 구조에 맞게 절대 경로로 임포트합니다.
from src import main

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture
def mock_logger():
    """메인 로거 격리 및 모킹 픽스처"""
    # Patch 타겟 경로를 src.main으로 수정
    with patch("src.main.logging.getLogger") as mock_get_logger:
        logger_instance = MagicMock()
        mock_get_logger.return_value = logger_instance
        yield logger_instance

@pytest.fixture
def mock_pipeline_service_cls():
    """PipelineService 클래스 및 비동기 컨텍스트 매니저 모킹"""
    # Patch 타겟 경로를 src.main으로 수정
    with patch("src.main.PipelineService") as mock_cls:
        instance = mock_cls.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.run_batch = AsyncMock()
        yield mock_cls

# ========================================================================================
# 1. 정상 흐름 테스트 (Functional Success)
# ========================================================================================

@pytest.mark.asyncio
async def test_main_suc_01_functional_success(mock_pipeline_service_cls, mock_logger):
    """[MAIN-SUC-01] 정상 배치 실행 및 시스템 로그 기록 검증"""
    # Given
    mock_result = {"total": 1, "success": 1, "fail": 0}
    mock_pipeline_service_cls.return_value.run_batch.return_value = mock_result
    
    # When
    await main.main()
    
    # Then
    mock_pipeline_service_cls.return_value.run_batch.assert_awaited_once()
    mock_logger.info.assert_called_once_with(f"파이프라인 최종 결과: {mock_result}")

# ========================================================================================
# 2. 경계값 및 환경 테스트 (Boundary / Environment)
# ========================================================================================

def test_main_env_01_dotenv_missing_defense():
    """[MAIN-ENV-01] .env 파일 누락 시 모듈 로드 크래시 방어 검증"""
    # Given: Patch 타겟 경로 수정
    with patch("dotenv.load_dotenv", return_value=False) as mock_load_dotenv:
        
        # When
        importlib.reload(main)
        
        # Then
        mock_load_dotenv.assert_called_once()
        assert hasattr(main, "TARGET_TASK")
        assert main.TARGET_TASK == "daily_macro_batch"

# ========================================================================================
# 3. 데이터 견고성 테스트 (Data Robustness)
# ========================================================================================

@pytest.mark.asyncio
async def test_main_log_01_abnormal_result_logging(mock_pipeline_service_cls, mock_logger):
    """[MAIN-LOG-01] 비정상적인 반환값(None)에 대한 로깅 포맷팅 견고성 검증"""
    # Given
    mock_pipeline_service_cls.return_value.run_batch.return_value = None
    
    # When
    await main.main()
    
    # Then
    mock_logger.info.assert_called_once_with("파이프라인 최종 결과: None")

# ========================================================================================
# 4. 논리적 예외 및 Fail-Fast 테스트 (Logical Exceptions)
# ========================================================================================

@pytest.mark.asyncio
async def test_main_err_01_context_init_fail_fast(mock_pipeline_service_cls, mock_logger):
    """[MAIN-ERR-01] PipelineService 초기화(Context 진입) 실패 시 즉시 예외 전파 (Fail-Fast)"""
    # Given
    error_msg = "Configuration Missing"
    mock_pipeline_service_cls.return_value.__aenter__.side_effect = Exception(error_msg)
    
    # When & Then
    with pytest.raises(Exception, match=error_msg):
        await main.main()
        
    # Then
    mock_logger.info.assert_not_called()

@pytest.mark.asyncio
async def test_main_err_02_run_batch_system_error_and_teardown(mock_pipeline_service_cls, mock_logger):
    """[MAIN-ERR-02] 실행 중 치명적 에러 발생 시 예외 전파 및 자원 해제(__aexit__) 보장"""
    # Given
    error_msg = "Critical System Memory Error"
    mock_pipeline_service_cls.return_value.run_batch.side_effect = RuntimeError(error_msg)
    
    # When & Then
    with pytest.raises(RuntimeError, match=error_msg):
        await main.main()
        
    # Then
    mock_logger.info.assert_not_called()
    mock_pipeline_service_cls.return_value.__aexit__.assert_awaited_once()

# ========================================================================================
# 5. 진입점 로직 테스트 (Entrypoint CLI Execution)
# ========================================================================================

def test_main_cli_01_entrypoint_execution():
    """[MAIN-CLI-01] 애플리케이션 진입점(__main__) 실행 로직 검증"""
    import runpy
    from unittest.mock import patch

    # Given: 실제 이벤트 루프 구동을 방지하기 위해 asyncio.run을 Mocking함.
    # 이때 전달된 코루틴이 GC(Garbage Collector)에 의해 소멸되며 발생하는 
    # 'never awaited' RuntimeWarning을 방어하기 위해 코루틴 리소스를 명시적으로 해제(close)함.
    def mock_asyncio_run_behavior(coro):
        coro.close()

    with patch("asyncio.run", side_effect=mock_asyncio_run_behavior) as mock_asyncio_run:
        
        # When: sys.modules 캐싱 충돌을 방지하기 위해 파일 경로 기반(run_path)으로
        # CLI 환경에서의 `python main.py` 실행 상태를 모사함.
        runpy.run_path(main.__file__, run_name="__main__")
        
        # Then: 진입점 조건문(if __name__ == "__main__")이 정상적으로 통과되어
        # 메인 코루틴 실행 함수(asyncio.run)가 정확히 1회 호출되어야 함.
        mock_asyncio_run.assert_called_once()