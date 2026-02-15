"""
Multi-Provider 설정 관리 모듈 (Multi-Provider Configuration Management)

KIS(한국투자증권), FRED(미 연준), ECOS(한국은행) 등 이기종 데이터 소스의 
설정(Credentials)과 수집 정책(Extraction Policy)을 통합 관리합니다.
사용자의 요청에 따라 `ConfigManager` 클래스 내부에 팩토리 메서드와 캐싱 로직을 
캡슐화하여 응집도를 높였습니다.

데이터 흐름 (Data Flow):
Input (Task Name) -> ConfigManager.get_config() -> Load YAML & .env -> Cache Instance -> Config Object

주요 기능:
- 싱글톤 패턴 응용 (Singleton-like): Task Name별로 인스턴스를 캐싱하여 중복 로딩 방지.
- 팩토리 메서드 패턴 (Factory Method): `ConfigManager.get_config()`를 통해 객체 생성 및 반환.
- Provider별 설정 격리 (Isolation): 각 API의 인증 정보와 Base URL을 독립된 클래스로 관리.
- 정책 검증 (Policy Validation): 수집 작업 정의가 스키마(JobPolicy)에 맞는지 즉시 검증.

Trade-off:
- Class-level Caching vs Module-level Globals:
    - 변경 전: 모듈 레벨의 전역 변수 `_config_cache` 사용. 구현이 간단하지만 네임스페이스가 오염됨.
    - 변경 후: `ConfigManager` 내부의 `ClassVar`로 캐시 관리. 캡슐화가 강화되고 IDE 자동완성 지원이 좋아짐.
    - 근거: `LogManager`와의 일관성 및 객체지향적 설계 원칙(상태와 행위의 그룹화) 준수.
"""

from typing import Dict, Any, Literal, Optional, ClassVar
from pathlib import Path
import yaml

from pydantic import Field, SecretStr, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# ==============================================================================
# 1. Provider별 설정 모델 (Provider Specific Settings)
# ==============================================================================
class KISSettings(BaseSettings):
    """한국투자증권(KIS) API 전용 설정 모델.

    Attributes:
        app_key (SecretStr): API 인증 키 (로그 노출 방지).
        app_secret (SecretStr): API 시크릿 키.
        base_url (str): API 엔드포인트 URL.
    """
    app_key: SecretStr = Field(alias="KIS_APP_KEY")
    app_secret: SecretStr = Field(alias="KIS_APP_SECRET")
    base_url: str = Field(alias="KIS_BASE_URL")
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

class FREDSettings(BaseSettings):
    """FRED (Federal Reserve Economic Data) API 전용 설정 모델."""
    api_key: SecretStr = Field(alias="FRED_API_KEY")
    base_url: str = Field(alias="FRED_BASE_URL")
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

class ECOSSettings(BaseSettings):
    """한국은행 경제통계시스템(ECOS) API 전용 설정 모델."""
    api_key: SecretStr = Field(alias="ECOS_API_KEY")
    base_url: str = Field(alias="ECOS_BASE_URL")
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

class UPBITSettings(BaseSettings):
    """업비트(UPBIT) API 전용 설정 모델."""
    api_key: SecretStr = Field(alias="UPBIT_API_KEY")
    secret_key: SecretStr = Field(alias="UPBIT_SECRET_KEY")
    base_url: str = Field(alias="UPBIT_BASE_URL")
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

# ==============================================================================
# 2. 정책(Job) 검증 모델 (Validation Model)
# ==============================================================================
class JobPolicy(BaseModel):
    """YAML 파일에 정의된 개별 수집 작업(Job)의 스키마를 검증합니다.

    Attributes:
        provider (Literal): 지원하지 않는 API Provider 입력 시 에러 발생.
        description (str): 작업 설명.
        path (str): API 경로.
        params (Dict): 요청 파라미터.
    """
    provider: Literal["KIS", "FRED", "ECOS", "UPBIT"]
    description: str
    path: str
    
    # Rationale: 파라미터가 없는 경우를 대비해 빈 딕셔너리를 기본값으로 설정 (Null Safety).
    params: Dict[str, Any] = Field(default_factory=dict)
    tr_id: Optional[str] = None
    domain: Optional[str] = None

# ==============================================================================
# 3. 통합 ConfigManager
# ==============================================================================
class ConfigManager(BaseSettings):
    """애플리케이션의 모든 설정을 통합 관리하는 최상위 설정 클래스.
    
    Singleton 패턴과 Factory Method 패턴을 결합하여, Task별로 고유한 설정 인스턴스를
    캐싱하고 관리합니다.

    Attributes:
        task_name (str): 현재 실행 중인 파이프라인 작업 식별자.
        kis (KISSettings): KIS 관련 설정 그룹.
        fred (FREDSettings): FRED 관련 설정 그룹.
        ecos (ECOSSettings): ECOS 관련 설정 그룹.
        upbit (UPBITSettings): UPBIT 관련 설정 그룹.
        extraction_policy (Dict[str, JobPolicy]): 검증된 수집 정책 목록.
    """
    # Class-level Cache Storage (Encapsulated)
    # Rationale: ClassVar를 사용하여 Pydantic 필드가 아닌 클래스 속성임을 명시.
    # 이를 통해 인스턴스 데이터 검증(Validation) 로직에서 제외됨.
    _cache: ClassVar[Dict[str, "ConfigManager"]] = {}
    _active_task_name: ClassVar[Optional[str]] = None

    task_name: str = "default_task"
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_filename: str = "app.log"

    # Rationale: Composition(합성) 패턴을 사용하여 설정을 계층화함.
    kis: KISSettings = Field(default_factory=KISSettings)
    fred: FREDSettings = Field(default_factory=FREDSettings)
    ecos: ECOSSettings = Field(default_factory=ECOSSettings)
    upbit: UPBITSettings = Field(default_factory=UPBITSettings)

    # YAML에서 로드된 정책 (Job ID -> Policy Model)
    extraction_policy: Dict[str, JobPolicy] = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @classmethod
    def get_config(cls, task_name: Optional[str] = None) -> "ConfigManager":
        """설정 인스턴스를 반환하는 팩토리 메서드.

        Args:
            task_name (Optional[str]): 
                - 지정 시: 해당 Task의 설정을 로드하거나 캐시에서 반환하고, '활성 설정'으로 지정함.
                - 미지정 시: 가장 최근에 로드된 '활성 설정'을 반환함.

        Returns:
            ConfigManager: 설정 객체.

        Raises:
            RuntimeError: 초기화된 설정이 없는 상태에서 인자 없이 호출된 경우.
        """
        # Case 1: 인자 없이 호출된 경우 (Active Config 반환)
        if task_name is None:
            if cls._active_task_name is None:
                raise RuntimeError(
                    "CRITICAL: ConfigManager is not initialized. "
                    "Call ConfigManager.get_config(task_name='...') at least once before accessing it without arguments."
                )
            return cls._cache[cls._active_task_name]

        # Case 2: 특정 Task 설정을 요청한 경우 (Lazy Loading & Caching)
        if task_name not in cls._cache:
            cls._cache[task_name] = cls._load_from_yaml(task_name)
        
        # 요청된 Task를 '활성 상태'로 업데이트
        cls._active_task_name = task_name
        
        return cls._cache[task_name]

    @classmethod
    def _load_from_yaml(cls, task_name: str) -> "ConfigManager":
        """(Internal) 환경변수와 YAML 정책 파일을 병합하여 설정을 생성합니다.

        Args:
            task_name (str): 로드할 설정 파일의 식별자.

        Returns:
            ConfigManager: 초기화된 설정 객체.
        """
        # 1. 환경 변수 기반으로 기본 설정 인스턴스 생성
        config = cls()
        config.task_name = task_name
        
        # 2. YAML 파일 경로 계산
        # Rationale: __file__ 기준 상대 경로를 사용하여 실행 위치에 독립적인 경로 계산.
        base_path = Path(__file__).resolve().parents[2]
        yaml_path = base_path / "configs" / f"{task_name}.yml"
        
        # 3. YAML 로드 및 병합
        if yaml_path.exists():
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    raw_data = yaml.safe_load(f) or {}
                    
                    # 로깅 설정 오버라이딩
                    if "log_level" in raw_data:
                        config.log_level = raw_data["log_level"]
                    if "log_dir" in raw_data:
                        config.log_dir = raw_data["log_dir"]
                    if "log_filename" in raw_data:
                        config.log_filename = raw_data["log_filename"]

                    # 정책(Policy) 파싱 및 검증
                    raw_policies = raw_data.get("policy", {})
                    validated_policies = {}
                    
                    for job_id, policy_data in raw_policies.items():
                        try:
                            validated_policies[job_id] = JobPolicy(**policy_data)
                        except Exception as e:
                            # LogManager가 준비되지 않았을 수 있으므로 print 사용 (Bootstrapping 단계)
                            print(f"⚠️ [ConfigManager] Invalid policy for job '{job_id}': {e}")
                    
                    config.extraction_policy = validated_policies
            except Exception as e:
                print(f"⚠️ [ConfigManager] Failed to parse YAML at {yaml_path}: {e}")
        else:
            print(f"⚠️ [ConfigManager] YAML config not found at {yaml_path}. Using default env settings.")
        
        return config