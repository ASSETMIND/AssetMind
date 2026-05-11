"""
[모듈 제목]
TransformerService - 의존성 분리 및 패턴 기반 라우팅 서비스 (전면 수정)

[모듈 목적 및 상세 설명]
Extractor 도메인과의 결합도를 완전히 끊어내고, 오직 transformer.yml 내부의 라우팅 룰(Prefix matching)에 
의존하여 동적으로 변환기(Concrete Transformer)를 바인딩하고 스트리밍 처리를 수행합니다.

Trade-off:
1. 패턴 매칭(Prefix) 라우팅 도입:
   - 장점: Extractor 설정 파일에 대한 의존성이 사라져 SRP(단일 책임 원칙)를 완벽히 준수합니다. 190개 Job을 단 몇 줄의 Prefix 룰로 커버하여 오버엔지니어링을 방지합니다.
   - 단점: job_id의 네이밍 컨벤션(예: kis_kospi_...)이 틀어지면 라우팅이 실패할 수 있습니다.
   - 근거: 파이프라인에서 Job 명명 규칙(Naming Convention)을 지키는 것은 기본 규약이므로, 이를 활용해 도메인을 분리하는 것이 결합도를 높이는 것보다 훨씬 우수한 아키텍처입니다.
"""

from typing import Any, Dict, Iterator, List, Union
import pandas as pd

from src.common.config import ConfigManager
from src.common.log import LogManager
from src.common.exceptions import ConfigurationError, TransformerInitializationError, TransformerError
from src.transformer.processors.abstract_transformer import AbstractTransformer


class TransformerService:
    """데이터 변환 파이프라인의 생명주기와 라우팅을 총괄하는 서비스(Facade) 클래스."""

    def __init__(self) -> None:
        self._logger = LogManager.get_logger(self.__class__.__name__)
        
        # [핵심 수정] Extractor config 로드 제거. 오직 Transformer 설정만 의존.
        self._transformer_config = ConfigManager.load("transformer")
        self._transformer_cache: Dict[str, AbstractTransformer] = {}

    def _resolve_schema_policy(self, job_id: str) -> str:
        """transformer.yml의 routing 룰을 기반으로 job_id에 맞는 스키마 정책명을 추론합니다."""
        routing_rules = self._transformer_config.get("routing", [])
        
        for rule in routing_rules:
            prefix = rule.get("prefix", "")
            if job_id.startswith(prefix):
                return rule.get("schema")
                
        raise ConfigurationError(f"Job '{job_id}'에 일치하는 라우팅 룰(Prefix)이 transformer.yml에 존재하지 않습니다.")

    def _get_or_create_transformer(self, job_id: str) -> AbstractTransformer:
        """job_id를 기반으로 스키마 정책을 추론하고 알맞은 변환기를 지연 초기화합니다."""
        # 1. 자체 라우팅 룰을 통해 스키마 이름 도출
        schema_policy_name = self._resolve_schema_policy(job_id)

        # 2. 캐시 히트
        if schema_policy_name in self._transformer_cache:
            return self._transformer_cache[schema_policy_name]

        self._logger.info(f"[{job_id}] 변환기 지연 초기화 진입 (Policy: {schema_policy_name})")

        # 3. 스키마 정책 조회 및 객체 생성
        try:
            policy_data = self._transformer_config.get("policy", {}).get(schema_policy_name)
            if not policy_data:
                raise ConfigurationError(f"변환 정책 '{schema_policy_name}'을 찾을 수 없습니다.")
                
            provider = policy_data.get("provider", "").lower()
            
            if provider in ["kis", "kis_domestic", "kis_overseas"]:
                from src.transformer.processors.providers.kis_transformer import KISTransformer
                transformer_instance = KISTransformer(config=self._transformer_config, policy=policy_data)
            
            elif provider == "fred":
                from src.transformer.processors.providers.fred_transformer import FREDTransformer
                transformer_instance = FREDTransformer(config=self._transformer_config, policy=policy_data)

            elif provider == "ecos":
                from src.transformer.processors.providers.ecos_transformer import ECOSTransformer
                transformer_instance = ECOSTransformer(config=self._transformer_config, policy=policy_data)

            elif provider == "upbit":
                from src.transformer.processors.providers.upbit_transformer import UPBITTransformer
                transformer_instance = UPBITTransformer(config=self._transformer_config, policy=policy_data)

            else:
                raise TransformerInitializationError(f"지원하지 않는 변환기 프로바이더입니다: '{provider}'")

            self._transformer_cache[schema_policy_name] = transformer_instance
            return transformer_instance

        except Exception as e:
            if isinstance(e, (ConfigurationError, TransformerInitializationError)):
                raise e
            raise TransformerInitializationError(f"변환기 초기화 중 예기치 않은 오류 발생: {e}") from e

    def transform_stream(
        self, 
        job_id: str, 
        data_stream: Iterator[Union[List[Dict[str, Any]], pd.DataFrame]],
        enforce_schema: bool = True,  # EDA 탐색 모드 지원
        **kwargs: Any
    ) -> Iterator[pd.DataFrame]:
        """Reader 계층의 스트림을 받아 변환을 수행하는 제너레이터를 반환합니다."""
        transformer = self._get_or_create_transformer(job_id)
        
        self._logger.info(f"[{job_id}] 스트리밍 데이터 변환 파이프라인 가동 (enforce_schema={enforce_schema})")
        
        chunk_count = 0
        try:
            for batch_data in data_stream:
                if batch_data is None or len(batch_data) == 0:
                    continue
                    
                transformed_df = transformer.transform(
                    data=batch_data, 
                    enforce_schema=enforce_schema, 
                    job_id=job_id, 
                    **kwargs
                )
                chunk_count += 1
                yield transformed_df
                
            self._logger.info(f"[{job_id}] 스트리밍 변환 완료 (총 {chunk_count}개 청크 처리됨)")
            
        except Exception as e:
            raise TransformerError(
                message=f"스트리밍 변환 제너레이터 실행 중 오류 발생: {e}",
                should_retry=False,
                original_exception=e
            ) from e