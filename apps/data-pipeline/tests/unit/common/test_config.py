import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

# [Target Modules]
from src.common.config import (
    ConfigManager, JobPolicy, PipelineTask, 
    AWSLoaderPolicy, PostgresLoaderPolicy, KISSettings
)
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
def reset_config_cache():
    """[Teardown] Singleton 상태 격리를 위한 ClassVar 자동 초기화"""
    ConfigManager._cache.clear()
    yield
    ConfigManager._cache.clear()

@pytest.fixture
def config_file_helper(tmp_path):
    """YAML 파일 생성 및 Path Mocking 헬퍼"""
    def _create_and_patch(file_name: str, content: dict | str):
        config_dir = tmp_path / "configs"
        config_dir.mkdir(parents=True, exist_ok=True)
        file_path = config_dir / f"{file_name}.yml"
        
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
    """ConfigManager 내부의 Path 객체를 Patch하여 tmp_path를 루트로 인식"""
    with patch("src.common.config.Path") as mock_path_cls:
        mock_path_instance = MagicMock()
        mock_path_instance.resolve.return_value.parents = [None, None, tmp_path]
        mock_path_cls.return_value = mock_path_instance
        yield mock_path_cls

# ========================================================================================
# 1. 초기화 및 보안 테스트 (Init & Security)
# ========================================================================================

def test_init_01_valid_env(mock_env):
    """[INIT-01] GIVEN 필수 환경변수 WHEN 인스턴스 생성 THEN 속성 정상 매핑"""
    config = ConfigManager()
    assert config.kis.base_url == "https://kis.api"
    assert config.fred.base_url == "https://fred.api"

def test_init_02_missing_env(monkeypatch):
    """[INIT-02] GIVEN 환경변수 누락 WHEN 인스턴스 생성 THEN ValidationError 발생"""
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    with patch.dict(KISSettings.model_config, {"env_file": ".non_existent_env_file"}):
        with pytest.raises(ValidationError):
            ConfigManager()

def test_init_03_secret_security(mock_env):
    """[INIT-03] GIVEN 시크릿 환경변수 WHEN 접근 THEN 평문 노출 방지(SecretStr)"""
    config = ConfigManager()
    assert "dummy_upbit_secret" not in str(config.upbit.secret_key)
    assert config.upbit.secret_key.get_secret_value() == "dummy_upbit_secret"

# ========================================================================================
# 2. 파일 로드 및 캐싱 테스트 (Load & Cache)
# ========================================================================================

def test_load_01_valid_yaml_and_override(mock_env, config_file_helper, patch_config_path):
    """[LOAD-01] GIVEN 정상 YAML WHEN load 호출 THEN 파싱 성공 및 전역 로그 설정 오버라이드"""
    yaml_content = {
        "log_level": "DEBUG",
        "log_dir": "/var/logs",
        "log_filename": "test.log",
        "custom_key": "custom_value"
    }
    config_file_helper("extractor", yaml_content)
    
    config = ConfigManager.load("extractor")
    
    assert config.log_level == "DEBUG"
    assert config.log_dir == "/var/logs"
    assert config.log_filename == "test.log"
    assert config.yaml_data["custom_key"] == "custom_value"
    assert "extractor" in ConfigManager._cache

def test_load_02_cache_hit(mock_env, config_file_helper, patch_config_path):
    """[LOAD-02] GIVEN 이미 로드된 캐시 상태 WHEN load 재호출 THEN I/O 없이 동일 인스턴스 반환"""
    config_file_helper("extractor", {"key": "value"})
    config1 = ConfigManager.load("extractor")
    config2 = ConfigManager.load("extractor")
    
    assert config1 is config2
    assert id(config1) == id(config2)

def test_load_03_broken_yaml(mock_env, config_file_helper, patch_config_path):
    """[LOAD-03] GIVEN 문법 오류 YAML WHEN load 호출 THEN ConfigurationError 발생"""
    config_file_helper("broken", "invalid: yaml: : format")
    
    with pytest.raises(ConfigurationError, match="YAML 파싱 실패"):
        ConfigManager.load("broken")

def test_load_04_file_not_found(mock_env, patch_config_path):
    """[LOAD-04] GIVEN 존재하지 않는 파일 WHEN load 호출 THEN 빈 yaml_data 반환"""
    config = ConfigManager.load("not_exist")
    assert config.yaml_data == {}

# ========================================================================================
# 3. 유틸리티 테스트 (Utility)
# ========================================================================================

def test_util_01_get_method(mock_env, config_file_helper, patch_config_path):
    """[UTIL-01] GIVEN 로드된 설정 WHEN get 호출 THEN 값 또는 기본값 반환"""
    config_file_helper("test", {"exist_key": "exist_val"})
    config = ConfigManager.load("test")
    
    assert config.get("exist_key") == "exist_val"
    assert config.get("not_exist", "default_val") == "default_val"

# ========================================================================================
# 4. 수집 정책 검증 테스트 (Extractor Policy)
# ========================================================================================

def test_ext_01_domain_isolation(mock_env):
    """[EXT-01] GIVEN extractor가 아닌 상태 WHEN get_extractor 호출 THEN ConfigurationError 발생"""
    config = ConfigManager(file_name="pipeline")
    with pytest.raises(ConfigurationError, match="'extractor' 설정에서만 호출 가능"):
        config.get_extractor("job_1")

def test_ext_02_missing_job(mock_env, config_file_helper, patch_config_path):
    """[EXT-02] GIVEN 미존재 Job ID WHEN get_extractor 호출 THEN ConfigurationError 발생"""
    config_file_helper("extractor", {"policy": {}})
    config = ConfigManager.load("extractor")
    
    with pytest.raises(ConfigurationError, match="Job ID 'unknown'를 찾을 수 없습니다"):
        config.get_extractor("unknown")

def test_ext_03_valid_policy(mock_env, config_file_helper, patch_config_path):
    """[EXT-03] GIVEN 정상 Job 데이터 WHEN get_extractor 호출 THEN JobPolicy 인스턴스 반환"""
    job_data = {
        "policy": {
            "job_kis_01": {
                "provider": "KIS",
                "description": "국내 주식 수집",
                "path": "/uapi/domestic-stock"
            }
        }
    }
    config_file_helper("extractor", job_data)
    config = ConfigManager.load("extractor")
    
    policy = config.get_extractor("job_kis_01")
    assert isinstance(policy, JobPolicy)
    assert policy.provider == "KIS"
    assert policy.path == "/uapi/domestic-stock"

# ========================================================================================
# 5. 적재 정책 검증 테스트 (Loader Policy)
# ========================================================================================

def test_ldr_01_domain_isolation(mock_env):
    """[LDR-01] GIVEN loader가 아닌 상태 WHEN get_loader 호출 THEN ConfigurationError 발생"""
    config = ConfigManager(file_name="extractor")
    with pytest.raises(ConfigurationError, match="'loader' 설정에서만 호출 가능"):
        config.get_loader("aws")

def test_ldr_02_missing_loader(mock_env, config_file_helper, patch_config_path):
    """[LDR-02] GIVEN 미존재 로더 타겟 WHEN get_loader 호출 THEN ConfigurationError 발생"""
    config_file_helper("loader", {})
    config = ConfigManager.load("loader")
    
    with pytest.raises(ConfigurationError, match="Loader 타겟 'unknown'을 찾을 수 없습니다"):
        config.get_loader("unknown")

def test_ldr_03_aws_policy(mock_env, config_file_helper, patch_config_path):
    """[LDR-03] GIVEN AWS 로더 데이터 WHEN get_loader 호출 THEN AWSLoaderPolicy 반환"""
    loader_data = {
        "aws": {
            "region": "ap-northeast-2",
            "s3": {"bucket": "test-bucket"}
        }
    }
    config_file_helper("loader", loader_data)
    config = ConfigManager.load("loader")
    
    policy = config.get_loader("aws")
    assert isinstance(policy, AWSLoaderPolicy)
    assert policy.region == "ap-northeast-2"

def test_ldr_04_postgres_policy(mock_env, config_file_helper, patch_config_path):
    """[LDR-04] GIVEN Postgres 로더 데이터 WHEN get_loader 호출 THEN PostgresLoaderPolicy 반환"""
    loader_data = {
        "postgres": {
            "host": "localhost",
            "port": 5432,
            "database": "dw",
            "user": "admin",
            "default_schema": "public"
        }
    }
    config_file_helper("loader", loader_data)
    config = ConfigManager.load("loader")
    
    policy = config.get_loader("postgres")
    assert isinstance(policy, PostgresLoaderPolicy)
    assert policy.port == 5432

def test_ldr_05_unsupported_loader(mock_env, config_file_helper, patch_config_path):
    """[LDR-05] GIVEN 미지원 로더 타겟 WHEN get_loader 호출 THEN ConfigurationError 발생"""
    loader_data = {"gcp": {"project_id": "test"}}
    config_file_helper("loader", loader_data)
    config = ConfigManager.load("loader")
    
    with pytest.raises(ConfigurationError, match="지원하지 않는 Loader 타겟입니다: gcp"):
        config.get_loader("gcp")

# ========================================================================================
# 6. 파이프라인 정책 검증 테스트 (Pipeline Policy)
# ========================================================================================

def test_pipe_01_domain_isolation(mock_env):
    """[PIPE-01] GIVEN pipeline이 아닌 상태 WHEN get_pipeline 호출 THEN ConfigurationError 발생"""
    config = ConfigManager(file_name="extractor")
    with pytest.raises(ConfigurationError, match="'pipeline' 설정에서만 호출 가능"):
        config.get_pipeline("task_1")

def test_pipe_02_missing_task(mock_env, config_file_helper, patch_config_path):
    """[PIPE-02] GIVEN 미존재 Task ID WHEN get_pipeline 호출 THEN ConfigurationError 발생"""
    config_file_helper("pipeline", {"tasks": {}})
    config = ConfigManager.load("pipeline")
    
    with pytest.raises(ConfigurationError, match="Task ID 'unknown'를 찾을 수 없습니다"):
        config.get_pipeline("unknown")

def test_pipe_03_valid_task(mock_env, config_file_helper, patch_config_path):
    """[PIPE-03] GIVEN 정상 Task 데이터 WHEN get_pipeline 호출 THEN PipelineTask 반환"""
    task_data = {
        "tasks": {
            "task_daily_batch": {
                "description": "일일 배치 수집",
                "target_loader": "aws",
                "extract_jobs": ["job_1", "job_2"]
            }
        }
    }
    config_file_helper("pipeline", task_data)
    config = ConfigManager.load("pipeline")
    
    task = config.get_pipeline("task_daily_batch")
    assert isinstance(task, PipelineTask)
    assert task.target_loader == "aws"
    assert len(task.extract_jobs) == 2