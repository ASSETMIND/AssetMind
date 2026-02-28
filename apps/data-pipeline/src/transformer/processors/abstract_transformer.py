"""
[AbstractTransformer 모듈]

ITransformer 인터페이스를 구현하며, 모든 구체적인 변환기(Concrete Transformer)들이
공통적으로 가져야 할 실행 흐름(Template Method Pattern)과 로깅/에러 핸들링 로직을 제공합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
Input DataFrame -> [_validate: 스키마/데이터 무결성 검증] -> [_apply_transform: 실제 알고리즘 적용] -> Output DataFrame

주요 기능:
- [기능 1] Template Method (`transform`): 검증 -> 변환 -> 로깅으로 이어지는 표준화된 파이프라인 실행 흐름 강제
- [기능 2] 예외 포착 및 래핑: 하위 클래스에서 발생하는 예측 불가능한 런타임 에러를 도메인 예외(TransformerError)로 규격화
- [기능 3] 로깅 내장: 모든 변환기의 실행 시작/종료 및 에러 발생 시점을 자동으로 추적

Trade-off: 
- 장점: 중복되는 로깅 및 예외 처리(Try-Catch) 보일러플레이트를 부모 클래스로 끌어올려, 하위 클래스 개발자는 순수 데이터 변환 알고리즘(`_apply_transform`)과 검증(`_validate`)에만 집중할 수 있습니다.
- 단점: 파이썬의 동적 타이핑 특성상, 추상 클래스의 보호 속성(Protected Attributes) 접근이나 오버라이딩을 문법적으로 완벽히 강제하기는 어렵습니다.
- 근거: 실제 프로덕션 파이프라인에서는 "어떤 변환기에서 에러가 터졌는가?"를 즉시 추적하는 것이 생명입니다. 모든 구체 클래스가 각자 로깅과 에러 핸들링을 구현하면 반드시 누락이 발생하므로, 중앙 집중식 에러 핸들링을 제공하는 템플릿 메서드 패턴 도입이 필수적입니다.
"""

import logging
from abc import abstractmethod
from typing import Any, Optional

import pandas as pd

# 프로젝트 내부 모듈 (경로는 실제 프로젝트 구조에 맞게 조정 필요)
from src.common.interfaces import ITransformer
from src.common.exceptions import TransformerError, ConfigurationError, ETLError
from src.common.log import LogManager
from src.common.config import ConfigManager

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

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """데이터 변환 파이프라인의 뼈대(Template)를 실행합니다.
        
        로깅, 검증, 실제 변환, 에러 핸들링의 순서를 엄격하게 제어합니다.

        Args:
            data (pd.DataFrame): 변환을 수행할 원본 데이터프레임.

        Returns:
            pd.DataFrame: 변환이 완료된 데이터프레임.

        Raises:
            TransformerError: 데이터 검증 실패 또는 변환 중 발생한 모든 런타임 에러.
        """
        transformer_name = self.__class__.__name__
        self.logger.info(f"[{transformer_name}] 데이터 변환 작업을 시작합니다. (Input shape: {data.shape})")

        try:
            # 1. 사전 검증: 입력 데이터의 스키마 및 무결성 사전 검증
            self._validate(data)

            # 2. 변환 로직: 하위 클래스에서 구현한 실제 변환 로직 실행
            transformed_data = self._apply_transform(data)

            # 3. 결과 검증: 변환 로직의 반환값이 정상적인 DataFrame인지 확인
            if not isinstance(transformed_data, pd.DataFrame):
                raise TransformerError(
                    message=f"[{transformer_name}] 반환 타입 오류: DataFrame이 아닙니다. (Type: {type(transformed_data)})",
                    should_retry=False
                )
            
            self.logger.info(f"[{transformer_name}] 데이터 변환 작업을 완료했습니다. (Output shape: {transformed_data.shape})")
            return transformed_data

        except ETLError as e:
            # 하위 클래스에서 발생시킨 비즈니스/도메인 에러는 로깅 후 그대로 통과(Pass-through)
            self.logger.error(f"[{transformer_name}] 도메인 로직 실패 | Error: {e.message}")
            raise e
            
        except Exception as e:
            # 판다스 내부 C엔진 에러(MemoryError 등)와 같은 예측 불가능한 예외를 
            # 파이프라인 공통 규격인 TransformerError로 래핑하여 추적성 확보
            error_msg = f"[{transformer_name}] 변환 로직 수행 중 예기치 않은 오류 발생"
            self.logger.error(f"{error_msg} | Error: {e}", exc_info=True)
            raise TransformerError(
                message=error_msg,
                details={"transformer": transformer_name, "raw_error": str(e)},
                original_exception=e,
                should_retry=False
            )

    @abstractmethod
    def _validate(self, data: pd.DataFrame) -> None:
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
    def _apply_transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """실제 데이터 변환 알고리즘을 수행합니다.
        
        모든 구체 클래스는 이 메서드 내부에 벡터화된(Vectorized) 
        pandas/numpy 연산을 구현해야 합니다.

        Args:
            data (pd.DataFrame): 변환할 대상 데이터프레임.

        Returns:
            pd.DataFrame: 변환이 완료된 데이터프레임.
        """
        pass