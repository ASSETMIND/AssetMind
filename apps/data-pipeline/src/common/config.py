"""
[모듈 제목]
Multi-Provider Configuration Management Module

[모듈 목적 및 상세 설명]
KIS(한국투자증권), FRED(미 연준), ECOS(한국은행), UPBIT 등 이기종 데이터 소스의 
API 인증 정보(Credentials)와 데이터 수집/적재 정책(Extraction/Load Policy)을 통합 관리합니다.
Pydantic을 활용하여 환경 변수(.env)와 YAML 설정 파일의 유효성을 애플리케이션 진입 시점에 즉시 검증하며,
ConfigManager 클래스 내부에 팩토리 메서드와 캐싱 로직을 캡슐화하여 모듈의 응집도를 높였습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: Task/Config 이름 (예: "extractor", "loader", "pipeline") 기반 설정 로드 요청.
2. Cache Look-up: ConfigManager._cache 내 동일 파일 로드 이력 확인 (Cache Hit/Miss 분기).
3. Secrets Injection: Pydantic BaseSettings를 통해 .env 파일 내 민감 정보(API Key 등) 자동 매핑 및 마스킹.
4. YAML Parsing: 지정된 도메인의 YAML 정책 파일을 읽고 딕셔너리로 파싱하여 원본 데이터(yaml_data)로 저장.
5. Output: get_* 메서드 호출 시 Pydantic 모델로 타입과 스키마가 엄격히 검증된 도메인 객체 반환.

주요 기능:
- Singleton-like Caching: Task Name별로 설정 인스턴스를 클래스 변수에 캐싱하여 중복된 파일 I/O 및 파싱 방지.
- Factory Method: `ConfigManager.load()` 팩토리 메서드를 통해 설정 객체의 생성과 초기화를 중앙에서 통제.
- Provider Isolation: 각 API 공급자의 인증 정보와 Base URL을 독립된 모델 클래스로 격리하여 보안성 및 유지보수성 확보.
- Strict Policy Validation: 추출(Extractor), 적재(Loader), 파이프라인 구성 시 예상되는 스키마와 실제 데이터를 즉각 대조(Fail-Fast).

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. Class-level Caching vs Module-level Globals:
   - 장점: 모듈 단위 전역 변수 대신 `ConfigManager._cache`에 상태를 캡슐화하여 네임스페이스 오염을 방지하고 IDE의 정적 분석 지원을 극대화함.
   - 단점: Gunicorn, Celery 등 Multi-Processing 환경에서는 워커(Worker) 간 캐시가 공유되지 않아 최초 1회씩 파일 I/O가 발생함.
   - 근거: 데이터 파이프라인의 단일 실행 컨텍스트(Single Task) 내에서는 클래스 레벨 캐싱만으로도 충분한 성능 이득을 얻을 수 있으며, 객체지향의 상태 은닉 원칙에 완벽히 부합함.
2. Pydantic Strict Validation vs Lazy Evaluation(단순 딕셔너리 접근):
   - 장점: 필수 파라미터 누락, 타입 불일치(문자열 대신 정수 등)로 인한 파이프라인 붕괴를 애플리케이션 시작 시점에 원천 차단(Fail-Fast)함.
   - 단점: 데이터 맵핑 및 모델 인스턴스화에 따른 미세한 런타임 오버헤드 발생.
   - 근거: 파이프라인 도중 설정 오류로 대규모 데이터가 오염될 경우 복구 비용이 막대하므로, 초기 진입점에서의 100% 무결성 보장이 마이크로초 단위의 성능 최적화보다 압도적으로 중요함.
3. SecretStr 도입 (보안 관점):
   - 장점: 메모리 덤프나 로깅 시 인증 토큰 및 비밀번호가 평문으로 노출되는 것을 방지함.
   - 단점: 실제 API 호출 시 `.get_secret_value()`를 명시적으로 호출해야 하는 추가 작업이 필요함.
   - 근거: 금융 및 경제 데이터를 수집하는 Production 환경에서는 보안 컴플라이언스 준수가 개발 편의성에 우선해야 함.
"""

from typing import Dict, Any, List, Literal, Optional, ClassVar, Union
from pathlib import Path
import yaml

from pydantic import Field, SecretStr, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.common.exceptions import ConfigurationError

# ==============================================================================
# Provider별 설정 모델 (Provider Specific Settings)
# ==============================================================================
# [설계 의도] 각 데이터 프로바이더의 환경변수를 독립적인 Pydantic 모델로 정의하여,
# 새로운 프로바이더 추가 시 기존 코드의 수정을 최소화(OCP 준수)하고 독립성을 보장함.

class KISSettings(BaseSettings):
    """한국투자증권(KIS) API 전용 설정 모델."""
    
    app_key: SecretStr = Field(alias="KIS_APP_KEY")
    app_secret: SecretStr = Field(alias="KIS_APP_SECRET")
    base_url: str = Field(alias="KIS_BASE_URL")
    
    # [설계 의도] 불필요한 환경 변수 유입으로 인한 오류 방지를 위해 extra="ignore" 정책 사용.
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
# 정책 검증 모델 (Validation Models)
# ==============================================================================
# [설계 의도] YAML에 정의된 파이프라인 작업 명세가 시스템이 처리할 수 있는 규격인지
# 실행 전 강력하게 검증하기 위한 데이터 컨트랙트(Data Contract).

class JobPolicy(BaseModel):
    """extractor.yml에 정의된 개별 수집 작업(Job) 스키마."""
    
    # [설계 의도] Literal을 사용하여 지원하지 않는 Provider가 입력되었을 때 즉시 오류를 발생시킴.
    provider: Literal["KIS", "FRED", "ECOS", "UPBIT"]
    description: str
    path: str
    params: Dict[str, Any] = Field(default_factory=dict)
    tr_id: Optional[str] = None
    domain: Optional[str] = None
    chunk_size: int
    base_date: str

class PipelineTask(BaseModel):
    """pipeline.yml에 정의된 개별 파이프라인 조립(Task) 스키마."""
    
    description: str
    target_loader: str
    extract_jobs: List[str] = Field(default_factory=list)

class AWSLoaderPolicy(BaseModel):
    """AWS S3 데이터 레이크 적재를 위한 환경 설정 스키마."""
    
    region: str
    s3: Dict[str, str]
    tuning: Dict[str, int] = Field(default_factory=dict)

class PostgresLoaderPolicy(BaseModel):
    """PostgreSQL 데이터 웨어하우스 적재를 위한 환경 설정 스키마."""
    
    host: str
    port: int
    database: str
    user: str
    pool: Dict[str, int] = Field(default_factory=dict)
    default_schema: str

class GlobalLoaderPolicy(BaseModel):
    """모든 로더가 공통으로 상속 및 준수해야 하는 네트워크/재시도 설정 스키마."""
    
    timeout_sec: int = 300
    max_retries: int = 3
    retry_backoff_factor: float = 2.0

# ==============================================================================
# ConfigManager
# ==============================================================================
class ConfigManager(BaseSettings):
    """애플리케이션의 모든 설정을 통합 관리하는 최상위 설정 클래스.
    
    Singleton 패턴과 Factory Method 패턴을 결합하여, Task별로 고유한 설정 인스턴스를
    메모리에 캐싱하고 관리합니다. 환경변수와 YAML 설정이 이 클래스로 집중됩니다.

    Attributes:
        file_name (str): 현재 로드된 YAML 설정 파일의 이름.
        kis (KISSettings): KIS API 연결을 위한 자격 증명 및 설정.
        fred (FREDSettings): FRED API 연결을 위한 자격 증명 및 설정.
        ecos (ECOSSettings): ECOS API 연결을 위한 자격 증명 및 설정.
        upbit (UPBITSettings): UPBIT API 연결을 위한 자격 증명 및 설정.
        yaml_data (Dict[str, Any]): 동적으로 파싱된 YAML 파일의 원본 딕셔너리 구조체.
    """
    
    # [설계 의도] 파일 명을 키(Key)로, ConfigManager 인스턴스를 값(Value)으로 저장하는 내부 캐시.
    # 전역 네임스페이스를 보호하기 위해 ClassVar로 캡슐화.
    _cache: ClassVar[Dict[str, "ConfigManager"]] = {}

    file_name: str = "default"
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_filename: str = "app.log"

    # [설계 의도] Composition(합성) 패턴. 프로바이더별 설정을 하위 객체로 위임하여 관리를 단순화.
    kis: KISSettings = Field(default_factory=KISSettings)
    fred: FREDSettings = Field(default_factory=FREDSettings)
    ecos: ECOSSettings = Field(default_factory=ECOSSettings)
    upbit: UPBITSettings = Field(default_factory=UPBITSettings)

    # [설계 의도] YAML 파일에서 동적으로 읽어온 정책 데이터를 유지.
    yaml_data: Dict[str, Any] = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @classmethod
    def load(cls, file_name: str) -> "ConfigManager":
        """YAML 파일 이름(file_name)을 기준으로 설정 인스턴스를 로드하고 캐싱하는 팩토리 메서드.

        주어진 파일 이름의 설정이 메모리 캐시에 존재하면 캐시된 객체를 반환하고,
        없으면 YAML 파일을 읽어 파싱한 후 초기화 및 캐싱을 수행합니다.

        Args:
            file_name (str): 로드할 대상 YAML 설정 파일 이름 (확장자 제외).

        Returns:
            ConfigManager: 초기화가 완료된 ConfigManager 싱글톤 인스턴스.

        Raises:
            ConfigurationError: YAML 파일 파싱 중 문법 오류나 I/O 에러 발생 시.
        """
        if file_name not in cls._cache:
            config = cls(file_name=file_name)
            
            base_path = Path(__file__).resolve().parents[2]
            yaml_path = base_path / "configs" / f"{file_name}.yml"
            
            if yaml_path.exists():
                try:
                    with open(yaml_path, "r", encoding="utf-8") as f:
                        raw_data = yaml.safe_load(f) or {}
                        config.yaml_data = raw_data
                        
                        # [설계 의도] 로깅 설정 등 전역 수준에서 필요한 설정은 최상위 속성으로 덮어씌움.
                        if "log_level" in raw_data:
                            config.log_level = raw_data["log_level"]
                        if "log_dir" in raw_data:
                            config.log_dir = raw_data["log_dir"]
                        if "log_filename" in raw_data:
                            config.log_filename = raw_data["log_filename"]
                except Exception as e:
                    # [설계 의도] 초기화 실패는 시스템의 치명적 결함이므로 내장 에러가 아닌
                    # 식별 가능한 커스텀 비즈니스 예외(ConfigurationError)로 래핑하여 Fail-Fast 유도.
                    raise ConfigurationError(f"YAML 파싱 실패 ({yaml_path}): {e}") from e
            else:
                config.yaml_data = {}
            
            cls._cache[file_name] = config
            
        return cls._cache[file_name]

    def get(self, key: str, default: Any = None) -> Any:
        """YAML 최상위 키를 기준으로 데이터를 안전하게 추출합니다.

        Args:
            key (str): 조회할 YAML 데이터의 최상위 키.
            default (Any, optional): 키가 존재하지 않을 때 반환할 기본값. Defaults to None.

        Returns:
            Any: 조회된 설정 데이터 구조 또는 기본값.
        """
        # [설계 의도] 딕셔너리 직접 접근(Bracket Notation) 시 발생할 수 있는 KeyError를 방어하기 위함.
        return self.yaml_data.get(key, default)

    def get_extractor(self, job_id: str) -> JobPolicy:
        """동적으로 특정 job_id의 수집 정책(Extractor Policy)을 추출 및 스키마 검증 후 반환합니다.

        Args:
            job_id (str): 추출하려는 수집 작업의 고유 ID.

        Returns:
            JobPolicy: 검증이 완료된 Job 정책 데이터 컨트랙트 객체.

        Raises:
            ConfigurationError: 현재 인스턴스가 'extractor' 모드가 아니거나 대상 ID가 없을 경우.
        """
        # [설계 의도] 도메인 응집성 보장. extractor 설정을 로드하지 않은 상태에서 정책을 
        # 가져오려는 개발자의 실수를 런타임에 차단함.
        if self.file_name != "extractor":
            raise ConfigurationError("get_extractor는 'extractor' 설정에서만 호출 가능합니다.")
        
        policy_data = self.yaml_data.get("policy", {}).get(job_id)
        if not policy_data:
            raise ConfigurationError(f"Job ID '{job_id}'를 찾을 수 없습니다.")
        
        return JobPolicy(**policy_data)

    def get_loader(self, loader_name: str) -> Union[AWSLoaderPolicy, PostgresLoaderPolicy]:
        """동적으로 특정 대상의 적재 정책(Loader Policy)을 추출 및 스키마 검증 후 반환합니다.

        Args:
            loader_name (str): 추출하려는 적재 대상의 이름 (예: "aws", "postgres").

        Returns:
            Union[AWSLoaderPolicy, PostgresLoaderPolicy]: 대상 시스템에 맞는 구체화된 정책 모델.

        Raises:
            ConfigurationError: 현재 인스턴스가 'loader' 모드가 아니거나 지원하지 않는 Loader일 경우.
        """
        if self.file_name != "loader":
            raise ConfigurationError("get_loader는 'loader' 설정에서만 호출 가능합니다.")
            
        loader_data = self.yaml_data.get(loader_name)
        if not loader_data:
            raise ConfigurationError(f"Loader 타겟 '{loader_name}'을 찾을 수 없습니다.")
            
        # [설계 의도] OCP(개방-폐쇄 원칙)에 따라 적재 타겟에 맞는 구체적인 Pydantic 모델을 
        # 다형성(Polymorphism) 형태로 분기하여 반환. 향후 GCP, Azure 로더 추가 시 확장 용이.
        if loader_name == "aws":
            return AWSLoaderPolicy(**loader_data)
        elif loader_name == "postgres":
            return PostgresLoaderPolicy(**loader_data)
        else:
            raise ConfigurationError(f"지원하지 않는 Loader 타겟입니다: {loader_name}")
    
    def get_pipeline(self, task_id: str) -> PipelineTask:
        """동적으로 특정 task_id의 파이프라인 조립 정책(Pipeline Policy)을 추출 및 검증하여 반환합니다.

        Args:
            task_id (str): 실행할 파이프라인 태스크의 고유 ID.

        Returns:
            PipelineTask: 수집-적재 조립 정보를 담고 있는 데이터 컨트랙트 객체.

        Raises:
            ConfigurationError: 현재 인스턴스가 'pipeline' 모드가 아니거나 대상 Task ID가 없을 경우.
        """
        if self.file_name != "pipeline":
            raise ConfigurationError("get_pipeline은 'pipeline' 설정에서만 호출 가능합니다.")
        
        task_data = self.yaml_data.get("tasks", {}).get(task_id)
        if not task_data:
            raise ConfigurationError(f"Task ID '{task_id}'를 찾을 수 없습니다.")
        
        return PipelineTask(**task_data)