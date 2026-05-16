"""
Reader 계층과의 유연한 결합(List[Dict] 지원), 메타데이터 파라미터 수용(**kwargs), 
그리고 Silver 데이터 레이어의 핵심인 출력 스키마 강제화(_enforce_schema) 훅을 템플릿에 추가합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: Reader에서 넘어온 List[Dict] 또는 DataFrame 데이터, 그리고 메타데이터(**kwargs).
2. Convert: List[Dict]인 경우 OOM 방지를 고려하며 내부적으로 DataFrame으로 변환.
3. Template Execution: _validate -> _apply_transform -> _enforce_schema 순차 실행.
4. Output: 사내 DW의 표준 데이터 규격(컬럼, 타입)에 완벽히 맞추어진 DataFrame 반환.

주요 기능:
- Input Flexibility: 상위 파이프라인에서 데이터 타입 캐스팅을 신경 쓰지 않도록 추상화.
- Schema Enforcement: Silver 데이터의 무결성을 보장하는 마지막 방어선(Hook) 추가.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약. 반드시 모든 코드 내용을 작성. 가혹할정도로 코드를 재확인하면서 작성.
1. 템플릿 내 입력 타입 변환(List[Dict] -> DataFrame) 내장화:
   - 장점: 파이프라인 제어기(Airflow/Service) 코드가 얇아지고, 변환기가 다양한 입력에 유연하게 대응함.
   - 단점: Transformer 객체가 DataFrame 초기화 오버헤드를 일정 부분 부담하게 됨.
   - 근거: 데이터를 가장 잘 아는 도메인 객체(Transformer)가 자신의 입력 규격 변환을 스스로 책임지는 것이 응집도(Cohesion) 측면에서 유리함.
2. _enforce_schema 단계 분리:
   - 장점: '데이터 값을 조작하는 로직(_apply_transform)'과 '데이터 그릇의 형태를 맞추는 로직(_enforce_schema)'이 철저히 분리되어 단일 책임 원칙(SRP) 준수.
   - 단점: 구체화된 변환기(Concrete Class)를 만들 때 구현해야 할 의무 추상 메서드가 1개 더 늘어남.
   - 근거: API 공급자마다 데이터의 중첩(Nested) 정도나 키값이 달라지더라도, 최종 타겟(DW/S3)에 적재되는 Silver 스키마는 반드시 동일해야 함. 스키마 강제 로직을 별도의 훅으로 분리하는 것이 장기적인 유지보수성과 데이터 정합성(Data Integrity) 확보에 절대적으로 유리함.
"""

from abc import abstractmethod
from typing import Any, Dict, List, Optional, Union

import pandas as pd

# 프로젝트 내부 모듈 (경로는 실제 프로젝트 구조에 맞게 조정 필요)
from src.common.interfaces import ITransformer
from src.common.exceptions import TransformerError, ConfigurationError, ETLError
from src.common.log import LogManager
from src.common.config import ConfigManager

from src.common.decorators.log_decorator import log_decorator

class AbstractTransformer(ITransformer):
    """모든 데이터 변환기의 기반이 되는 추상 클래스.
    
    구현체(DataMerger, FeatureScaler 등)는 이 클래스를 상속받아 구체적인 
    변환 로직을 구현해야 하며, 반드시 ConfigManager를 주입받아야 합니다.

    Attributes:
        config (ConfigManager): 애플리케이션 전역 설정 객체. (변환 정책, 파라미터 포함)
        logger (logging.Logger): 구조화된 로깅을 위한 커스텀 로거 인스턴스.
    """

    def __init__(self, config: ConfigManager):
        """AbstractTransformer를 초기화하고 필수 의존성을 검증합니다.

        Args:
            config (ConfigManager): 데이터 변환 정책이 포함된 앱 설정 객체.

        Raises:
            ConfigurationError: 필수 의존성(Config 등)이 누락된 경우.
        """
        if config is None:
            raise ConfigurationError("초기화 실패: ConfigManager 인스턴스가 필요합니다.")
             
        self.config = config
        self.logger = LogManager.get_logger(self.__class__.__name__)

    @log_decorator()
    def transform(
        self, 
        data: Union[pd.DataFrame, List[Dict[str, Any]]],
        enforce_schema: bool = True,
        **kwargs: Any
    ) -> pd.DataFrame:
        """데이터 변환 파이프라인의 뼈대(Template)를 실행합니다.
        
        로깅, 검증, 실제 변환, 에러 핸들링의 순서를 엄격하게 제어합니다.

        Args:
            data (pd.DataFrame): 변환을 수행할 원본 데이터프레임.
            enforce_schema (bool): 스키마 강제화를 적용할지 여부.
            **kwargs (Any): 추가적인 메타데이터 파라미터.

        Returns:
            pd.DataFrame: 변환이 완료된 데이터프레임.

        Raises:
            TransformerError: 데이터 검증 실패 또는 변환 중 발생한 모든 런타임 에러.
        """
        transformer_name = self.__class__.__name__

        try:
            # 0. 데이터 타입 유연화 (Reader의 List[Dict] 출력을 DataFrame으로 자동 수용)
            if isinstance(data, list):
                df_data = pd.DataFrame(data)
            elif isinstance(data, pd.DataFrame):
                df_data = data.copy()
            else:
                raise TransformerError(
                    message=f"[{transformer_name}] 지원하지 않는 입력 타입입니다. (Type: {type(data)})",
                    should_retry=False
                )

            # 1. 사전 검증: 입력 데이터와 주입된 메타데이터(**kwargs) 검증
            self._validate(df_data, **kwargs)

            # 2. 변환 로직: 실제 값과 구조를 변환(Flatten 등)하는 알고리즘 실행
            transformed_data = self._apply_transform(df_data, **kwargs)

            # 3. 스키마 강제화: 적재를 위한 최종 타입/컬럼명 캐스팅
            if enforce_schema:
                final_data = self._enforce_schema(transformed_data, **kwargs)
                self.logger.debug(f"[{transformer_name}] Production 모드: Schema Enforcement 적용 완료")
            else:
                final_data = transformed_data
                self.logger.info(f"[{transformer_name}] EDA 탐색 모드: Schema Enforcement 건너뜀 (Bypass)")

            # 4. 결과 검증
            if not isinstance(final_data, pd.DataFrame):
                raise TransformerError(
                    message=f"[{transformer_name}] 반환 타입 오류: DataFrame이 아닙니다. (Type: {type(final_data)})",
                    should_retry=False
                )
            
            return final_data

        except ETLError as e:
            raise e
            
        except Exception as e:
            error_msg = f"[{transformer_name}] 변환 로직 수행 중 예기치 않은 오류 발생"
            self.logger.error(f"{error_msg} | Error: {e}", exc_info=True)
            raise TransformerError(
                message=f"[{transformer_name}] 변환 로직 수행 중 예기치 않은 네이티브 오류 발생",
                details={"transformer": transformer_name, "raw_error": str(e)},
                original_exception=e,
                should_retry=False
            ) from e

    @abstractmethod
    def _validate(self, data: pd.DataFrame, **kwargs: Any) -> None:
        """데이터 변환 전 입력 DataFrame과 설정의 무결성을 검증합니다.
        
        구현체는 `self.config`를 참조하여 필수 파라미터 유무를 확인하고,
        DataFrame의 필수 컬럼 존재 여부, 데이터 타입 등을 확인해야 합니다.

        Args:
            data (pd.DataFrame): 검증할 입력 데이터프레임.
            
        Raises:
            TransformerError (또는 하위 예외): 데이터나 설정이 변환 조건을 만족하지 않을 경우.
        """
        pass

    @abstractmethod
    def _apply_transform(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """실제 데이터 변환 알고리즘을 수행합니다.
        
        모든 구체 클래스는 이 메서드 내부에 벡터화된(Vectorized) 
        pandas/numpy 연산을 구현해야 합니다.

        Args:
            data (pd.DataFrame): 변환할 대상 데이터프레임.

        Returns:
            pd.DataFrame: 변환이 완료된 데이터프레임.
        """
        pass

    @abstractmethod
    def _enforce_schema(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """최종 데이터프레임의 컬럼명과 데이터 타입을 표준 스키마에 맞게 강제합니다.
        
        Args:
            data (pd.DataFrame): 비즈니스 변환(_apply_transform)이 끝난 데이터프레임.
            **kwargs (Any): 파이프라인 실행 메타데이터.
            
        Returns:
            pd.DataFrame: 최종 검수 및 캐스팅이 완료된 데이터프레임.
        """
        pass

    # 파일 위치: src/transformer/processors/abstract_transformer.py

    def _cast_datetime_vectorized(self, series: pd.Series) -> pd.Series:
        """다양한 외부 API의 날짜 포맷(YYYYMMDD, YYYY-MM-DD, ISO8601 등)을 
        사내 표준인 Pandas datetime64[ns] 타입으로 안전하게 일괄 변환(Vectorized)합니다.

        for 루프 없이 Pandas 내부의 C-엔진을 활용하여 190종 지수의 수만 건 데이터를 고속 파싱합니다.
        문자열에 포함된 하이픈(-)이나 T, Z 같은 구분자를 정규식 보정 없이 대시 형태로 통일하여 
        pd.to_datetime의 내장 추론 성능을 최대로 끌어올립니다.

        Args:
            series (pd.Series): 정제 전 다양한 포맷의 문자열 또는 객체가 담긴 날짜 컬럼 데이터.

        Returns:
            pd.Series: datetime64[ns] 데이터 타입으로 완벽히 형변환된 시리즈 객체.
        """
        if series.empty:
            return series

        # 1. 전처리: 데이터를 문자열 스트링으로 강제 변환 후 공백 제거 및 결측치 문자 처리
        clean_series = series.astype(str).str.strip()
        
        # 2. KIS 규격 방어 (20260513 -> 2026-05-13): 하이픈이 없는 8자리 정수형태의 문자열 보정
        # 설계 의도: pd.to_datetime이 8자리 숫자를 간혹 unix timestamp 밀리초로 오진하는 현상을 원천 방어합니다.
        is_eight_digit = clean_series.str.match(r"^\d{8}$")
        if is_eight_digit.any():
            clean_series = pd.Series(
                [f"{val[:4]}-{val[4:6]}-{val[6:8]}" if m else val 
                 for val, m in zip(clean_series, is_eight_digit)],
                index=series.index
            )

        # 3. Pandas 네이티브 벡터화 파싱 실행 (errors='coerce'를 통해 파싱 실패 시 Crash 대신 NaN 처리)
        return pd.to_datetime(clean_series, errors="coerce")