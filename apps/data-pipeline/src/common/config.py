"""
Multi-Provider 설정 관리 모듈 (Multi-Provider Configuration Management)

KIS(한국투자증권), FRED(미 연준), ECOS(한국은행) 등 이기종 데이터 소스의 
설정(Credentials)과 수집 정책(Extraction Policy)을 통합 관리합니다.
작업(Task) 단위로 분리된 YAML 설정 파일을 동적으로 로드하여 유연성을 확보합니다.

데이터 흐름 (Data Flow):
Input (Task Name) -> Load .env & configs/{task_name}.yml -> Pydantic Parsing -> AppConfig Object

주요 기능:
- 동적 설정 로딩 (Dynamic Loading): 실행 시점의 `task_name`에 맞춰 관련 YAML 파일만 선별 로드.
- 컨텍스트 인식 (Context Awareness): `get_config()` 호출 시 인자가 없으면 최근 로드된 설정을 반환.
- Provider별 설정 격리 (Isolation): 각 API의 인증 정보와 Base URL을 독립된 클래스로 관리.
- 정책 검증 (Policy Validation): 수집 작업 정의가 스키마(JobPolicy)에 맞는지 즉시 검증.

Trade-off:
- Active Config Caching:
    - 장점: `LogManager`와 같이 Task Name을 알 수 없는 공통 모듈에서도 설정을 쉽게 참조 가능.
    - 단점: 멀티스레드 환경에서 서로 다른 Task가 동시에 로드되면 Race Condition 발생 가능성 있음.
    - 근거: 현재 파이프라인은 단일 프로세스/단일 Task 실행 모델이므로, 전역 상태(Global State) 관리가 효율적임.
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

class UPBITSettings(BaseSettings):
    """업비트(UPBIT) API 전용 설정 모델."""
    api_key: SecretStr = Field(alias="UPBIT_API_KEY")
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
# 3. 통합 AppConfig
# ==============================================================================
class AppConfig(BaseSettings):
    """애플리케이션의 모든 설정을 통합 관리하는 최상위 설정 클래스.

    Attributes:
        task_name (str): 현재 실행 중인 파이프라인 작업 식별자.
        kis (KISSettings): KIS 관련 설정 그룹.
        fred (FREDSettings): FRED 관련 설정 그룹.
        ecos (ECOSSettings): ECOS 관련 설정 그룹.
        upbit (UPBITSettings): UPBIT 관련 설정 그룹.
        extraction_policy (Dict[str, JobPolicy]): 검증된 수집 정책 목록.
    """
    task_name: str = "default_task"

    # Rationale: Composition(합성) 패턴을 사용하여 설정을 계층화함.
    kis: KISSettings = Field(default_factory=KISSettings)
    fred: FREDSettings = Field(default_factory=FREDSettings)
    ecos: ECOSSettings = Field(default_factory=ECOSSettings)
    upbit: UPBITSettings = Field(default_factory=UPBITSettings)

    # YAML에서 로드된 정책 (Job ID -> Policy Model)
    extraction_policy: Dict[str, JobPolicy] = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @classmethod
    def load(cls, task_name: str) -> "AppConfig":
        """환경변수와 특정 Task의 YAML 정책 파일을 로드하여 설정을 생성합니다.

        Args:
            task_name (str): 로드할 설정 파일의 이름 (예: 'extractor').
                             파일 경로는 'configs/{task_name}.yml'로 결정됨.

        Returns:
            AppConfig: 초기화 및 검증이 완료된 설정 객체.
        """
        config = cls()
        config.task_name = task_name
        
        # Rationale: __file__ 기준 상대 경로를 사용하여 실행 위치에 독립적인 경로 계산.
        yaml_path = Path(__file__).resolve().parents[2] / "configs" / f"{task_name}.yml"
        
        if yaml_path.exists():
            with open(yaml_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f) or {}
                raw_policies = raw_data.get("policy", {})
                
                validated_policies = {}
                for job_id, policy_data in raw_policies.items():
                    try:
                        validated_policies[job_id] = JobPolicy(**policy_data)
                    except Exception as e:
                        print(f"⚠️ Warning: Invalid policy for job '{job_id}': {e}")
                
                config.extraction_policy = validated_policies
        else:
            print(f"⚠️ Warning: YAML config not found at {yaml_path}")
        
        return config

# ==============================================================================
# 4. Global Config Accessor (Context-Aware)
# ==============================================================================
_config_cache: Dict[str, AppConfig] = {}
_active_task_name: Optional[str] = None

def get_config(task_name: Optional[str] = None) -> AppConfig:
    """설정 인스턴스를 반환하는 전역 접근자 함수.

    Args:
        task_name (Optional[str]): 
            - 지정 시: 해당 Task의 설정을 로드하거나 캐시에서 반환하고, '활성 설정'으로 지정함.
            - 미지정 시: 가장 최근에 로드된 '활성 설정'을 반환함 (LogManager 등에서 사용).

    Returns:
        AppConfig: 설정 객체.

    Raises:
        RuntimeError: 초기화된 설정이 없는 상태에서 인자 없이 호출된 경우.
    """
    global _config_cache, _active_task_name

    # Case 1: 인자 없이 호출된 경우 (예: LogManager)
    # 현재 활성화된(가장 최근 로드된) 설정을 반환합니다.
    if task_name is None:
        if _active_task_name is None:
            raise RuntimeError(
                "CRITICAL: AppConfig is not initialized. "
                "Call get_config(task_name='...') at least once before accessing it without arguments."
            )
        return _config_cache[_active_task_name]

    # Case 2: 특정 Task 설정을 요청한 경우 (예: Main Runner)
    if task_name not in _config_cache:
        # Lazy Loading 수행
        _config_cache[task_name] = AppConfig.load(task_name)
    
    # 요청된 Task를 '활성 상태'로 변경하여 이후 호출(LogManager 등)이 이를 참조하게 함
    _active_task_name = task_name
    
    return _config_cache[task_name]