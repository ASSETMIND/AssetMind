"""
설정 관리 모듈 단위 테스트 (Unit Test for Configuration Management Module)

이 모듈은 src.common.config의 클래스들이 설계된 대로 정확히 동작하는지 검증합니다.
실제 파일 시스템에 접근하지 않고 Mock 객체를 사용하여 테스트의 속도와 안정성을 보장합니다.

주요 검증 포인트:
1. File Loading: .env 및 .yml 파일 추출 로직의 정상 동작 및 예외(FileNotFound) 처리 검증.
2. Merge Strategy: 환경변수(.env)가 YAML 설정보다 높은 우선순위를 가지는지(Override) 검증.
3. Singleton Pattern: ConfigManager가 애플리케이션 전역에서 유일한 인스턴스를 유지하는지 검증.
4. Integration: Loader와 Merger가 조율되어 최종 AppConfig 객체가 올바르게 생성되는지 검증.
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
from src.common.config import (
    EnvFileLoader,
    YamlFileLoader,
    ConfigMerger,
    ConfigManager,
    AppConfig,
    get_config
)

# ==============================================================================
# Fixtures: 테스트 환경 설정
# ==============================================================================
@pytest.fixture
def reset_singleton():
    """ConfigManager의 Singleton 상태를 테스트 전후로 초기화합니다.
    
    싱글톤 패턴은 메모리에 상태가 남기 때문에, 테스트 간 간섭을 막기 위해
    _instance와 _config를 강제로 None으로 설정합니다.
    """
    ConfigManager._instance = None
    ConfigManager._config = None
    yield
    ConfigManager._instance = None
    ConfigManager._config = None

# ==============================================================================
# Test Case 1: EnvFileLoader (환경변수 로더)
# ==============================================================================
class TestEnvFileLoader:
    
    @patch("src.common.config.Path.exists")
    @patch("src.common.config.dotenv_values")
    def test_extract_success(self, mock_dotenv, mock_exists):
        """[성공] .env 파일이 존재할 때 데이터를 정상적으로 딕셔너리로 반환해야 한다."""
        
        # Given: 파일이 존재한다고 가정하고, 가짜 데이터를 반환하도록 설정
        mock_exists.return_value = True
        expected_data = {"TASK_NAME": "TestApp", "KIS_APP_KEY": "secret_key"}
        mock_dotenv.return_value = expected_data
        
        # When: 로더 초기화 및 추출 실행
        loader = EnvFileLoader()
        result = loader.extract()
        
        # Then: 결과가 예상 데이터와 일치해야 함
        assert result == expected_data
        mock_exists.assert_called()  # 파일 존재 확인이 호출되었는지 검증

    @patch("src.common.config.Path.exists")
    def test_extract_file_not_found(self, mock_exists):
        """[실패] .env 파일이 없을 때 FileNotFoundError를 발생시켜야 한다."""
        
        # Given: 파일이 존재하지 않는다고 가정
        mock_exists.return_value = False
        
        # When & Then: extract 호출 시 예외 발생 확인
        loader = EnvFileLoader()
        with pytest.raises(FileNotFoundError) as exc_info:
            loader.extract()
        
        assert "CRITICAL: .env file not found" in str(exc_info.value)

# ==============================================================================
# Test Case 2: YamlFileLoader (YAML 로더)
# ==============================================================================
class TestYamlFileLoader:
    
    @patch("src.common.config.Path.exists")
    @patch("src.common.config.yaml.safe_load")
    def test_extract_success(self, mock_yaml_load, mock_exists):
        """[성공] YAML 파일이 존재할 때 파싱된 딕셔너리를 반환해야 한다."""
        
        # Given: 파일 존재 및 YAML 파싱 결과 Mocking
        mock_exists.return_value = True
        expected_data = {
            "retry": {"max_retries": 3},
            "policy": {"target_tickers": ["005930"]}
        }
        mock_yaml_load.return_value = expected_data
        
        # 파일 열기(open) 함수 Mocking
        with patch("builtins.open", mock_open(read_data="dummy yaml content")):
            # When
            loader = YamlFileLoader()
            result = loader.extract()
        
        # Then
        assert result == expected_data

    @patch("src.common.config.Path.exists")
    def test_extract_file_not_found(self, mock_exists):
        """[실패] YAML 파일이 없을 때 FileNotFoundError를 발생시켜야 한다."""
        
        # Given
        mock_exists.return_value = False
        
        # When & Then
        loader = YamlFileLoader()
        with pytest.raises(FileNotFoundError) as exc_info:
            loader.extract()
        
        assert "CRITICAL: YAML config not found" in str(exc_info.value)

# ==============================================================================
# Test Case 3: ConfigMerger (병합 로직)
# ==============================================================================
class TestConfigMerger:
    
    def test_merge_priority(self):
        """[로직] YAML 데이터보다 .env 데이터가 우선순위를 가져야 한다."""
        
        # Given: YAML에는 기본값이, ENV에는 덮어쓸 값이 들어있는 상황
        yaml_data = {
            "task_name": "DefaultTask",
            "log_level": "INFO",
            "retry": {"count": 3}
        }
        env_data = {
            "TASK_NAME": "ProductionTask",  # 덮어쓰기 대상
            "LOG_LEVEL": "ERROR",           # 덮어쓰기 대상
            "KIS_APP_KEY": "new_key"        # ENV에만 있는 데이터
        }
        
        # When
        merged = ConfigMerger.merge(env_data, yaml_data)
        
        # Then
        # 1. ENV 값으로 덮어써졌는지 확인
        assert merged["task_name"] == "ProductionTask"
        assert merged["log_level"] == "ERROR"
        # 2. YAML에만 있던 값은 유지되는지 확인
        assert merged["retry"] == {"count": 3}
        # 3. ENV에만 있던 값이 추가되었는지 확인
        assert merged["KIS_APP_KEY"] == "new_key"

# ==============================================================================
# Test Case 4: ConfigManager (통합 및 싱글톤)
# ==============================================================================
class TestConfigManager:
    
    @patch("src.common.config.EnvFileLoader")
    @patch("src.common.config.YamlFileLoader")
    def test_initialize_and_singleton(self, MockYamlLoader, MockEnvLoader, reset_singleton):
        """[통합] ConfigManager가 Loader들을 조율하여 AppConfig를 생성하고 싱글톤을 유지하는지 검증."""
        
        # Given: Mock Loader들이 반환할 데이터 설정
        # EnvLoader Mock
        env_instance = MockEnvLoader.return_value
        env_instance.extract.return_value = {
            "TASK_NAME": "IntegrationTest",
            "KIS_APP_KEY": "real_key"
        }
        
        # YamlLoader Mock
        yaml_instance = MockYamlLoader.return_value
        yaml_instance.extract.return_value = {
            "retry": {"max": 5},
            "policy": {"default": "D"}
        }
        
        # When 1: 최초 호출 (초기화 발생)
        config1 = get_config()
        
        # Then 1: 데이터가 정상적으로 병합되어 AppConfig 객체로 변환되었는지 확인
        assert isinstance(config1, AppConfig)
        assert config1.task_name == "IntegrationTest"  # Env 값
        assert config1.kis_app_key == "real_key"      # Env 값
        assert config1.retry_policy["max"] == 5       # Yaml 값
        
        # When 2: 두 번째 호출 (싱글톤 동작 확인)
        config2 = ConfigManager.get_config()
        
        # Then 2: 두 객체는 메모리 주소가 동일해야 함 (Identity Check)
        assert config1 is config2
        
        # Loader들이 딱 한 번씩만 호출되었는지 확인 (효율성 검증)
        env_instance.extract.assert_called_once()
        yaml_instance.extract.assert_called_once()