"""
설정 관리 모듈 (Configuration Management Module)

이 모듈은 애플리케이션의 모든 설정을 중앙에서 관리합니다.
보안이 필요한 정보(.env)와 운영 정책(.yml)을 각각의 로더를 통해 추출하고,
이를 병합하여 단일 설정 객체(AppConfig)로 제공합니다.

Classes:
    EnvFileLoader: 환경변수 파일(.env) 로드 담당.
    YamlFileLoader: YAML 설정 파일 로드 담당.
    ConfigMerger: 두 설정 소스의 병합 로직 담당.
    AppConfig: 최종 설정 데이터를 담는 DTO.
    ConfigManager: 설정을 초기화하고 제공하는 싱글톤 관리자.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from dotenv import dotenv_values 

# ==============================================================================
# [Role 1] EnvFileLoader: .env 파일 추출
# ==============================================================================
class EnvFileLoader:
    """시스템의 .env 파일을 파일 시스템에서 직접 찾아 내용을 추출하는 로더.

    자동 환경변수 로딩 라이브러리에 의존하지 않고, 명시적으로 프로젝트 루트의
    .env 파일을 찾아 딕셔너리로 변환합니다.
    """

    def __init__(self, env_filename: str = ".env"):
        """EnvFileLoader를 초기화합니다.

        프로젝트 구조에 기반하여 .env 파일의 절대 경로를 계산합니다.
        (현재 파일 위치: src/common/config.py -> 루트: 상위 2단계)

        Args:
            env_filename (str): 로드할 환경변수 파일명. 기본값은 '.env'입니다.
        """
        self.env_path = Path(__file__).resolve().parents[2] / env_filename

    def extract(self) -> Dict[str, str]:
        """지정된 경로의 .env 파일을 읽어 Key-Value 딕셔너리로 반환합니다.

        Returns:
            Dict[str, str]: 환경변수 키와 값의 쌍.

        Raises:
            FileNotFoundError: .env 파일이 계산된 경로에 존재하지 않을 경우 발생합니다.
                                설정 파일 누락은 치명적 오류이므로 예외를 발생시켜 실행을 중단합니다.
        """
        if not self.env_path.exists():
            raise FileNotFoundError(
                f"CRITICAL: .env file not found at {self.env_path}. "
                "Please ensure the file exists in the project root."
            )
        
        # dotenv_values는 시스템 환경변수가 아닌, 오직 파일 내의 내용만 파싱합니다.
        return dotenv_values(self.env_path)


# ==============================================================================
# [Role 2] YamlFileLoader: .yml 파일 추출
# ==============================================================================
class YamlFileLoader:
    """비즈니스 로직 설정을 담은 YAML 파일을 추출하는 로더.

    config 폴더 내의 YAML 파일을 찾아 파이썬 딕셔너리 구조로 파싱합니다.
    """

    def __init__(self, yaml_filename: str = "extractor.yml"):
        """YamlFileLoader를 초기화합니다.

        Args:
            yaml_filename (str): config 폴더 내에 위치한 YAML 파일명.
                                 기본값은 'extractor.yml'입니다.
        """
        root_dir = Path(__file__).resolve().parents[2]
        self.yaml_path = root_dir / "config" / yaml_filename

    def extract(self) -> Dict[str, Any]:
        """YAML 파일을 읽어 계층화된 딕셔너리로 반환합니다.

        Returns:
            Dict[str, Any]: YAML 파일의 구조가 반영된 설정 데이터.

        Raises:
            FileNotFoundError: YAML 설정 파일이 존재하지 않을 경우 발생합니다.
        """
        if not self.yaml_path.exists():
            raise FileNotFoundError(
                f"CRITICAL: YAML config not found at {self.yaml_path}. "
                "Please verify the configuration file path."
            )

        with open(self.yaml_path, "r", encoding="utf-8") as f:
            # safe_load를 사용하여 신뢰할 수 없는 데이터 실행 방지
            return yaml.safe_load(f) or {}


# ==============================================================================
# [Role 3] ConfigMerger: 병합 로직
# ==============================================================================
class ConfigMerger:
    """서로 다른 소스(Env, Yaml)에서 추출된 설정 데이터를 병합하는 클래스.
    
    기본 정책은 YAML에서 가져오되, 보안이 필요하거나 환경별로 달라지는 값은
    .env의 내용으로 덮어쓰는 전략을 취합니다.
    """

    @staticmethod
    def merge(env_data: Dict[str, str], yaml_data: Dict[str, Any]) -> Dict[str, Any]:
        """YAML 데이터를 베이스로 하고, .env 데이터로 덮어씌웁니다.

        Args:
            env_data (Dict[str, str]): .env 파일에서 추출한 데이터.
            yaml_data (Dict[str, Any]): YAML 파일에서 추출한 데이터.

        Returns:
            Dict[str, Any]: 병합이 완료된 최종 설정 딕셔너리.
        """
        # 1. YAML 데이터 복사 (Base Configuration)
        merged = yaml_data.copy()
        
        # 2. .env 데이터 매핑 (Overwrite Strategy)
        
        # [메타데이터 및 로깅 설정 매핑]
        if "TASK_NAME" in env_data:
            merged["task_name"] = env_data["TASK_NAME"]

        # [환경 종속 설정 매핑] : LogManager에서 사용할 설정
        if "LOG_LEVEL" in env_data:
            merged["log_level"] = env_data["LOG_LEVEL"]
        if "LOG_DIR" in env_data:
            merged["log_dir"] = env_data["LOG_DIR"]
            
        # [보안 키(Secrets) 매핑]
        if "KIS_APP_KEY" in env_data:
            merged["KIS_APP_KEY"] = env_data["KIS_APP_KEY"]
        if "KIS_APP_SECRET" in env_data:
            merged["KIS_APP_SECRET"] = env_data["KIS_APP_SECRET"]
            
        return merged


# ==============================================================================
# [Role 4] ConfigManager: 최종 제공
# ==============================================================================
@dataclass
class AppConfig:
    """애플리케이션 전역에서 사용될 최종 설정 DTO"""
    task_name: str
    log_level: str                      # 로깅 레벨 (DEBUG, INFO, etc)
    log_dir: str                        # 로그 저장 경로
    kis_app_key: str                    # 한국투자증권 App Key
    kis_app_secret: str                 # 한국투자증권 Secret Key
    retry_policy: Dict[str, Any]        # 재시도 정책 (Max Retries, Backoff)
    extraction_policy: Dict[str, Any]   # 데이터 수집 정책 (대상 종목, 주기 등)

class ConfigManager:
    """최종 설정 객체를 생성하고 메모리에 유지하는 싱글톤 관리자.

    애플리케이션 실행 중 설정 로딩은 단 한 번만 수행되어야 하며,
    어디서든 동일한 설정 인스턴스에 접근할 수 있어야 합니다.
    """
    
    _instance = None
    _config: Optional[AppConfig] = None

    def __new__(cls):
        """싱글톤 패턴 구현: 인스턴스가 존재하지 않을 때만 생성합니다."""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            # 인스턴스 생성 시점에 설정을 즉시 초기화합니다.
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Loader와 Merger를 조율하여 AppConfig 객체를 생성합니다.

        1. EnvFileLoader, YamlFileLoader를 통해 Raw Data 추출
        2. ConfigMerger를 통해 데이터 병합
        3. 병합된 데이터를 AppConfig 객체로 변환하여 저장
        """
        # 1. Extract (추출)
        env_loader = EnvFileLoader()
        yaml_loader = YamlFileLoader()

        raw_env = env_loader.extract()
        raw_yaml = yaml_loader.extract()

        # 2. Merge (병합)
        merged_data = ConfigMerger.merge(raw_env, raw_yaml)

        # 3. Transform (변환)
        # 딕셔너리의 키가 누락되었을 경우를 대비해 get() 메서드로 기본값을 제공합니다.
        self._config = AppConfig(
            task_name=merged_data.get("task_name", "TASK_DEFAULT"),
            log_level=merged_data.get("log_level", "INFO"),
            log_dir=merged_data.get("log_dir", "logs"),
            kis_app_key=merged_data.get("KIS_APP_KEY", ""),
            kis_app_secret=merged_data.get("KIS_APP_SECRET", ""),
            retry_policy=merged_data.get("retry", {}),
            extraction_policy=merged_data.get("policy", {})
        )

    @classmethod
    def get_config(cls) -> AppConfig:
        """초기화된 AppConfig 인스턴스를 반환합니다.

        Returns:
            AppConfig: 애플리케이션 설정 객체.
        """
        return cls()._config

def get_config() -> AppConfig:
    """ConfigManager를 통해 설정 객체에 접근하는 전역 헬퍼 함수.

    다른 모듈에서는 이 함수를 호출하여 설정값을 사용할 수 있습니다.

    Returns:
        AppConfig: 설정 객체.
    """
    return ConfigManager.get_config()