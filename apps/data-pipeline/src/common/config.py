"""
Multi-Provider 설정 관리 모듈 (Multi-Provider Configuration Management)

KIS(한국투자증권), FRED(미 연준), ECOS(한국은행) 등 이기종 데이터 소스의 
설정(Credentials)과 수집 정책(Extraction Policy)을 통합 관리합니다.
작업(Task) 단위로 분리된 YAML 설정 파일을 동적으로 로드하여 유연성을 확보합니다.

데이터 흐름 (Data Flow):
Input (Task Name) -> Load .env & configs/{task_name}.yml -> Pydantic Parsing -> AppConfig Object

주요 기능:
- 동적 설정 로딩 (Dynamic Loading): 실행 시점의 `task_name`에 맞춰 관련 YAML 파일만 선별 로드.
- Provider별 설정 격리 (Isolation): 각 API의 인증 정보와 Base URL을 독립된 클래스로 관리.
- 정책 검증 (Policy Validation): 수집 작업 정의가 스키마(JobPolicy)에 맞는지 즉시 검증.

Trade-off:
- Task-Based Config Loading:
    - 장점: 거대한 하나의 설정 파일 대신, 작업별로 파일을 분리하여 관리 복잡도를 낮춤.
    - 단점: 설정 로더(get_config) 호출 시 반드시 `task_name`을 인자로 넘겨야 하는 제약 발생.
    - 근거: 파이프라인이 확장됨에 따라 수집/전처리/적재 설정이 섞이는 것을 방지하기 위해 물리적 분리가 필수적임.
"""

from typing import Dict, Any, Literal, Optional
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
    # Rationale: Literal 타입을 사용하여 컴파일 타임과 런타임에 유효한 Provider인지 엄격히 검사.
    provider: Literal["KIS", "FRED", "ECOS"]
    description: str
    path: str
    
    # Rationale: 파라미터가 없는 경우를 대비해 빈 딕셔너리를 기본값으로 설정 (Null Safety).
    params: Dict[str, Any] = Field(default_factory=dict)
    tr_id: Optional[str] = None
    domain: Optional[str] = None

# ==============================================================================
# 3. 통합 AppConfig
# ==============================================================================
class AppConfig(BaseSettings):
    """애플리케이션의 모든 설정을 통합 관리하는 최상위 설정 클래스.

    Attributes:
        task_name (str): 현재 실행 중인 파이프라인 작업 식별자.
        kis (KISSettings): KIS 관련 설정 그룹.
        fred (FREDSettings): FRED 관련 설정 그룹.
        ecos (ECOSSettings): ECOS 관련 설정 그룹.
        extraction_policy (Dict[str, JobPolicy]): 검증된 수집 정책 목록.
    """
    # Rationale: load() 시점에 주입받은 task_name을 저장하기 위해 필드 정의.
    task_name: str = "default_task"

    # Rationale: Composition(합성) 패턴을 사용하여 설정을 계층화함.
    kis: KISSettings = Field(default_factory=KISSettings)
    fred: FREDSettings = Field(default_factory=FREDSettings)
    ecos: ECOSSettings = Field(default_factory=ECOSSettings)

    # YAML에서 로드된 정책 (Job ID -> Policy Model)
    extraction_policy: Dict[str, JobPolicy] = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @classmethod
    def load(cls, task_name: str) -> "AppConfig":
        """환경변수와 특정 Task의 YAML 정책 파일을 로드하여 설정을 생성합니다.

        Args:
            task_name (str): 로드할 설정 파일의 이름 (예: 'extractor', 'loader').
                             파일 경로는 'configs/{task_name}.yml'로 결정됨.

        Returns:
            AppConfig: 초기화 및 검증이 완료된 설정 객체.
        """
        # 1. 환경변수 로딩 (.env -> Settings)
        config = cls()
        
        # Rationale: 인자로 받은 task_name을 Config 객체에 명시적으로 주입.
        config.task_name = task_name
        
        # 2. YAML 로딩 (Policy)
        # Rationale: __file__ 기준 상대 경로를 사용하여 실행 위치에 독립적인 경로 계산.
        # configs/{task_name}.yml 파일을 찾습니다.
        yaml_path = Path(__file__).resolve().parents[2] / "configs" / f"{task_name}.yml"
        
        if yaml_path.exists():
            with open(yaml_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f) or {}
                raw_policies = raw_data.get("policy", {})
                
                validated_policies = {}
                for job_id, policy_data in raw_policies.items():
                    try:
                        # Rationale: 딕셔너리 데이터를 JobPolicy 모델에 주입하여 즉시 유효성 검증 수행.
                        validated_policies[job_id] = JobPolicy(**policy_data)
                    except Exception as e:
                        print(f"⚠️ Warning: Invalid policy for job '{job_id}': {e}")
                
                config.extraction_policy = validated_policies
        else:
            print(f"⚠️ Warning: YAML config not found at {yaml_path}")
        
        return config

# 전역 설정 캐시 (Memoization for each task_name)
_config_cache: Dict[str, AppConfig] = {}

def get_config(task_name: str) -> AppConfig:
    """요청된 Task Name에 해당하는 설정 인스턴스를 반환합니다.

    이미 로드된 Task라면 캐시된 인스턴스를 반환하여 I/O 오버헤드를 줄입니다.

    Args:
        task_name (str): 설정 파일명 (확장자 제외).

    Returns:
        AppConfig: 해당 Task의 설정 객체.
    """
    global _config_cache
    if task_name not in _config_cache:
        # Lazy Loading - 최초 요청 시에만 파일을 읽고 파싱함.
        _config_cache[task_name] = AppConfig.load(task_name)
    return _config_cache[task_name]

