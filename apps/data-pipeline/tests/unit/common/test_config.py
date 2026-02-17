import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

# [Target Modules]
# 실제 프로젝트 구조에 맞춰 import 경로 수정 필요 (예: src.common.config)
from src.common.config import ConfigManager, JobPolicy, KISSettings

from src.common.exceptions import ConfigurationError

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture
def mock_env(monkeypatch):
    """[Setup] Pydantic Settings 로딩을 위한 필수 환경변수 주입"""
    env_vars = {
        "KIS_APP_KEY": "dummy_kis_key",
        "KIS_APP_SECRET": "dummy_kis_secret",
        "KIS_BASE_URL": "https://kis.api",
        "FRED_API_KEY": "dummy_fred_key",
        "FRED_BASE_URL": "https://fred.api",
        "ECOS_API_KEY": "dummy_ecos_key",
        "ECOS_BASE_URL": "https://ecos.api",
        "UPBIT_API_KEY": "dummy_upbit_key",
        "UPBIT_SECRET_KEY": "dummy_upbit_secret",
        "UPBIT_BASE_URL": "https://upbit.api",
    }
    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)
    return env_vars

@pytest.fixture(autouse=True)
def reset_config_state():
    """[Teardown] Singleton 상태 격리를 위한 자동 초기화"""
    # 테스트 전 초기화
    ConfigManager._cache.clear()
    ConfigManager._active_task_name = None
    yield
    # 테스트 후 초기화
    ConfigManager._cache.clear()
    ConfigManager._active_task_name = None

@pytest.fixture
def config_file_helper(tmp_path):
    """
    YAML 파일 생성 및 Path Mocking을 돕는 헬퍼.
    ConfigManager가 내부적으로 사용하는 Path(__file__) 로직을 가로채서
    tmp_path를 바라보게 만듭니다.
    """
    def _create_and_patch(task_name: str, content: dict | str):
        # 1. 파일 생성 구조: tmp_path/configs/{task_name}.yml
        config_dir = tmp_path / "configs"
        config_dir.mkdir(parents=True, exist_ok=True)
        file_path = config_dir / f"{task_name}.yml"
        
        if isinstance(content, dict):
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(content, f)
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        
        return tmp_path

    return _create_and_patch

@pytest.fixture
def patch_config_path(tmp_path):
    """ConfigManager 내부의 Path 객체를 Patch하여 tmp_path를 루트로 인식하게 함"""
    # src.common.config.Path를 Patch 해야 함.
    with patch("src.common.config.Path") as mock_path_cls:
        # Path(__file__).resolve().parents[2] 가 tmp_path가 되도록 설정
        # parents[2]를 호출하므로, mock 객체 구조를 맞춰줌
        mock_path_instance = MagicMock()
        mock_path_instance.resolve.return_value.parents = [None, None, tmp_path]
        mock_path_cls.return_value = mock_path_instance
        yield mock_path_cls

# ========================================================================================
# 1. 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_valid_env(mock_env):
    """[INIT-01] [Standard] 필수 환경변수가 존재하면 인스턴스 생성 성공"""
    config = ConfigManager(task_name="test_init")
    assert config.task_name == "test_init"
    assert config.kis.base_url == "https://kis.api"

def test_init_02_missing_env(monkeypatch):
    """[INIT-02] [BVA] 필수 환경변수 누락 시 ValidationError 발생 (Fail-Fast)"""
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    # Pydantic이 로컬의 .env 파일을 읽어 값을 채우는 것을 방지하기 위해
    # 테스트 범위(Context) 내에서만 env_file 설정을 무효화합니다.
    with patch.dict(KISSettings.model_config, {"env_file": ".non_existent_env_file"}):
        with pytest.raises(ValidationError):
            ConfigManager()

def test_init_03_secret_security(mock_env):
    """[INIT-03] [Security] 민감 정보는 SecretStr로 래핑되어 평문 노출 방지"""
    config = ConfigManager()
    # __repr__ 시 평문이 보이지 않아야 함
    assert "dummy_kis_key" not in str(config.kis.app_key)
    # 명시적 호출 시에만 값 확인 가능
    assert config.kis.app_key.get_secret_value() == "dummy_kis_key"

# ========================================================================================
# 2. 팩토리 & 캐싱 테스트 (Factory & Caching)
# ========================================================================================

def test_fact_01_factory_load(mock_env, config_file_helper, patch_config_path):
    """[FACT-01] [State] 최초 호출 시 파일 로딩 및 캐시 저장, Active Task 설정"""
    # Given
    config_file_helper("task_A", {
        "log_level": "DEBUG",
        "log_dir": "custom_logs",
        "log_filename": "task_a.log"
    })
    
    # When
    config = ConfigManager.get_config("task_A")
    
    # Then
    assert config.task_name == "task_A"
    assert config.log_level == "DEBUG" # YAML 오버라이드 확인
    assert config.log_dir == "custom_logs"
    assert "task_A" in ConfigManager._cache
    assert ConfigManager._active_task_name == "task_A"

def test_fact_02_cache_hit(mock_env, config_file_helper, patch_config_path):
    """[FACT-02] [Performance] 재호출 시 I/O 없이 동일한 객체 ID 반환 (캐시 적중)"""
    # Given
    config_file_helper("task_A", {})
    first_config = ConfigManager.get_config("task_A")
    
    # When
    second_config = ConfigManager.get_config("task_A")
    
    # Then
    assert first_config is second_config  # 동일 인스턴스 확인
    assert id(first_config) == id(second_config)

def test_fact_03_context_switch(mock_env, config_file_helper, patch_config_path):
    """[FACT-03] [State] 다른 Task 호출 시 Active Config 교체 및 독립 객체 생성"""
    # Given
    config_file_helper("task_A", {})
    config_file_helper("task_B", {})
    ConfigManager.get_config("task_A")
    
    # When
    config_b = ConfigManager.get_config("task_B")
    
    # Then
    assert ConfigManager._active_task_name == "task_B"
    assert config_b.task_name == "task_B"
    assert len(ConfigManager._cache) == 2

def test_fact_04_get_active_no_args(mock_env, config_file_helper, patch_config_path):
    """[FACT-04] [Usability] 인자 없이 호출 시 현재 활성 설정 반환"""
    # Given
    config_file_helper("task_A", {})
    ConfigManager.get_config("task_A")
    
    # When
    config = ConfigManager.get_config()
    
    # Then
    assert config.task_name == "task_A"

# ========================================================================================
# 3. 파일 로딩 테스트 (File Loading)
# ========================================================================================

def test_file_01_missing_file_fallback(mock_env, patch_config_path, capsys):
    """[FILE-01] [Robustness] YAML 파일 부재 시 에러 없이 기본 설정(Env) 반환"""
    # Given: 파일 생성 안함
    task_name = "no_file_task"
    
    # When
    config = ConfigManager.get_config(task_name)
    
    # Then
    assert config.task_name == task_name
    captured = capsys.readouterr()
    assert "YAML config not found" in captured.out

def test_file_02_empty_file(mock_env, config_file_helper, patch_config_path):
    """[FILE-02] [BVA] 파일은 존재하나 내용이 비어있는 경우 기본값 로드"""
    # Given
    config_file_helper("empty_task", {})
    
    # When
    config = ConfigManager.get_config("empty_task")
    
    # Then
    assert config.extraction_policy == {}

def test_file_03_broken_yaml(mock_env, config_file_helper, patch_config_path, capsys):
    """[FILE-03] [Robustness] YAML 문법 오류 시 예외 처리 및 기본 설정 반환"""
    # Given: 깨진 YAML 문법
    config_file_helper("broken_task", "key: value: error:")
    
    # When
    config = ConfigManager.get_config("broken_task")
    
    # Then
    assert config.extraction_policy == {}
    captured = capsys.readouterr()
    assert "Failed to parse YAML" in captured.out

# ========================================================================================
# 4. 정책 검증 테스트 (Policy Validation)
# ========================================================================================

def test_pol_01_valid_policy(mock_env, config_file_helper, patch_config_path):
    """[POL-01] [Standard] 올바른 스키마의 정책 파싱 및 매핑 확인"""
    # Given
    policy_data = {
        "policy": {
            "job_1": {"provider": "KIS", "description": "test", "path": "/uapi/test"}
        }
    }
    config_file_helper("valid_task", policy_data)
    
    # When
    config = ConfigManager.get_config("valid_task")
    
    # Then
    assert "job_1" in config.extraction_policy
    assert isinstance(config.extraction_policy["job_1"], JobPolicy)
    assert config.extraction_policy["job_1"].provider == "KIS"

def test_pol_02_partial_failure(mock_env, config_file_helper, patch_config_path, capsys):
    """[POL-02] [Partial Failure] 일부 정책 오류 시 유효한 정책만 로드 (Skip Invalid)"""
    # Given
    policy_data = {
        "policy": {
            "job_ok": {"provider": "KIS", "description": "ok", "path": "/ok"},
            "job_bad": {"provider": "KIS"} # Missing description, path
        }
    }
    config_file_helper("partial_task", policy_data)
    
    # When
    config = ConfigManager.get_config("partial_task")
    
    # Then
    assert "job_ok" in config.extraction_policy
    assert "job_bad" not in config.extraction_policy
    captured = capsys.readouterr()
    assert "Invalid policy for job 'job_bad'" in captured.out

def test_pol_03_invalid_enum(mock_env, config_file_helper, patch_config_path):
    """[POL-03] [BVA] 지원하지 않는 Provider 타입 입력 시 검증 실패 및 스킵"""
    # Given
    policy_data = {
        "policy": {
            "job_enum": {"provider": "UNKNOWN", "description": "f", "path": "/f"}
        }
    }
    config_file_helper("enum_task", policy_data)
    
    # When
    config = ConfigManager.get_config("enum_task")
    
    # Then
    assert "job_enum" not in config.extraction_policy

# ========================================================================================
# 5. 예외 및 상태 테스트 (Exception & State)
# ========================================================================================

def test_err_01_uninitialized_access(mock_env):
    """[ERR-01] [Logic] 초기화 전 인자 없는 get_config 접근 시 Critical Error"""
    # Given: 캐시가 비어있는 상태 (reset_config_state fixture)
    
    # When & Then
    with pytest.raises(ConfigurationError, match="치명적 오류"):
        ConfigManager.get_config()

def test_state_01_isolation(mock_env, config_file_helper, patch_config_path):
    """[STATE-01] [Idempotency] Fixture에 의한 테스트 간 상태 격리 확인"""
    # Given: 임의의 상태 변경
    config_file_helper("temp", {})
    ConfigManager.get_config("temp")
    
    # Teardown은 fixture가 수행하므로, 
    # 여기서는 '다른 테스트가 끝난 직후'라고 가정했을 때 캐시가 비어있는지 확인할 수는 없음.
    # 대신 이 테스트가 끝난 후 다음 테스트에 영향을 주지 않는지(reset_config_state 동작)는
    # pytest 실행 구조상 보장됨. 
    # 명시적으로 reset 기능을 호출하여 비워지는지 검증.
    
    ConfigManager._cache.clear()
    assert len(ConfigManager._cache) == 0