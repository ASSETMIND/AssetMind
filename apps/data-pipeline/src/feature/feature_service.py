"""
[모듈 목적 및 상세 설명]
파사드(Facade) 패턴을 적용하여, feature.yml 기반으로 FeatureFactory가 일괄 결합한
파생 피처 엔지니어링 태스크 체인(Feature Tasks Chain)의 순차 실행 및 데이터 흐름을 오케스트레이션하는 서비스 모듈입니다.
상위 파이프라인(Gold Pipeline)은 하위 세부 태스크나 파라미터 구조를 알 필요 없이
단일 진입점 메서드를 통해 피처 엔지니어링 작업을 완벽히 수행할 수 있습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 상위 파이프라인 컨트롤러로부터 매개변수 주입 없이 원본/정제 금융 시계열 데이터프레임(`market_data: pd.DataFrame`) 유입.
2. Build Chain: `FeatureFactory.create_features()`를 호출하여 feature.yml 명세에 따라 생성 및 결합된 태스크 객체 리스트 수신.
3. Execution Loop: 조립된 태스크 리스트를 순회하며 `market_data = task.calculate(market_data)` 파이프라이닝 연산 순차 실행.
4. Output: 예측 타겟 변수 및 5개 파생 피처 그룹 연산이 완벽히 완료된 최종 데이터프레임(`pd.DataFrame`) 반환.

주요 기능:
- [Param-Free Pipeline Entry Point] `execute_feature_engineering_job(market_data)` 진입점을 제공하여 상위 파이프라인의 비즈니스 의존성 최소화.
- [Sequential Task Chain Execution] FeatureFactory가 결합한 태스크 체인을 순차 구동하고 런타임 방어적 예외 처리 및 수행 로깅 수행.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 파사드(Facade) 서비스 레이어 기반 통합 제어 vs 파이프라인 내 직접 태스크 호출:
  - 장점: 상위 파이프라인 파일이 세부 피처 태스크 클래스나 파라미터 변경에 영향받지 않으며, 파이프라인 진입점의 캡슐화와 응집도를 극대화함.
  - 단점: 서비스 계층이라는 레이어가 하나 추가되어 오버헤드가 미세하게 증가함.
  - 근거: MLOps 파이프라인 모듈화 명세상, 서비스 계층을 통한 단일 진입점 제공과 결합도 분리가 유지보수성 측면에서 필수적이므로 이 구조를 강제함.
"""

import pandas as pd
from typing import List, Optional

from src.feature.feature_factory import FeatureFactory
from src.feature.tasks.abstract_feature import AbstractFeature
from src.common.exceptions import FeatureServiceError, FeatureError


class FeatureService:
    """피처 엔지니어링 파이프라인의 파사드 오케스트레이터 서비스 클래스."""

    def __init__(self) -> None:
        """FeatureService 인스턴스를 초기화하고 팩토리 객체를 바인딩합니다."""
        # [설계 의도] 내부 팩토리 객체를 사전 생성하여 실행 시점 피처 태스크 체인 조립 준비
        self._feature_factory: FeatureFactory = FeatureFactory()

    def execute(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """상위 파이프라인 진입점으로서 피처 엔지니어링 태스크 체인을 순차 실행합니다.

        Args:
            market_data (pd.DataFrame): 정제가 완료된 원본 금융 시계열 데이터프레임.

        Returns:
            pd.DataFrame: 타겟 변수 및 파생 피처들이 통합 추가된 마스터 데이터프레임.

        Raises:
            FeatureServiceError: 입력 데이터 무결성 결여, 태스크 체인 생성 실패 또는 연산 중 크래시 발생 시 전파.
        """
        if market_data is None or market_data.empty:
            raise FeatureServiceError(
                message="[FeatureService] 입력 데이터프레임이 None이거나 비어 있어 피처 엔지니어링을 수행할 수 없습니다."
            )

        try:
            # [설계 의도] 상위 파이프라인은 인자 없이 팩토리를 기동하여 feature.yml 기준의 최신 태스크 체인을 결합받음
            feature_tasks: List[AbstractFeature] = self._feature_factory.create_features()

            if not feature_tasks:
                raise FeatureServiceError(
                    message="[FeatureService] 실행 가능한 피처 엔지니어링 태스크가 존재하지 않습니다."
                )

            processed_df: pd.DataFrame = market_data.copy()
            initial_columns_count: int = len(processed_df.columns)

            # [설계 의도] 팩토리가 정렬 결합한 Task 체인을 순회하며 데이터프레임 파이프라이닝 연산 집행
            for task in feature_tasks:
                processed_df = task.calculate(processed_df)

            final_columns_count: int = len(processed_df.columns)
            generated_features_count: int = final_columns_count - initial_columns_count

            return processed_df

        except FeatureError as feature_err:
            # [설계 의도] 하위 피처 레이어 커스텀 예외 발생 시 서비스 예외로 포장하여 상위 파이프라인에 전파
            raise FeatureServiceError(
                message=f"[FeatureService] 피처 엔지니어링 수행 중 오류가 감지되었습니다: {feature_err.message}",
                original_exception=feature_err
            ) from feature_err
        except Exception as unexpected_err:
            raise FeatureServiceError(
                message=f"[FeatureService] 피처 엔지니어링 오케스트레이션 중 예기치 않은 시스템 예외가 발생했습니다.",
                original_exception=unexpected_err
            ) from unexpected_err