"""
[모듈 목적 및 상세 설명]
골드 파이프라인(Gold Pipeline) 전처리 계층 내 단기 결측치 처리를 위한 실험군 버킷(Bucket C) 구체 전략 객체입니다.
자산별 최근 고유 가격 데이터의 이동평균(Moving Average)을 산출하고, 결측 구간이 발생했을 때 
해당 자산의 가격이 이동평균선으로 복귀하려는 통계적 관성(평균 회귀 성향, Mean Reversion)을 가중치로 계산하여 보간합니다.
이를 통해 주가가 과열되거나 침체된 국면에서 발생한 단기 공백의 분포 왜곡을 금융 공학적 관성으로 정밀 보정합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 결측 자산 컬럼을 포함하고 있는 20거래일 슬라이딩 Lookback 윈도우 원본 데이터프레임 및 단기 라우팅 대상 자산 목록.
2. Processing:
   - 각 자산별 ffill 기반 이동평균선(Moving Average) 베이스라인 행렬 계산.
   - 결측 구간별 연속 누적 공백 일수(Run Length) 행렬을 고속 벡터로 도출.
   - 이격 거리에 회귀 속도(μ)에 따른 지수 감쇄 인자(Exponential Decay Factor)를 적용하여 평균 복귀 경로 일괄 계산.
3. Output: 지정된 단기 자산들의 공백이 이동평균 회귀 경로로 정밀 대치 완료된 복제본 데이터프레임 반환.

주요 기능:
- [Vectorized Mean Reversion] 복잡한 시계열 재귀 루프를 거치지 않고, 이격 거리 감쇄 모델을 통한 전 자산 일괄 벡터화 대치.
- [Dynamic Parameter Binding] 외부 YML 설정을 통해 이동평균 윈도우 크기 및 회귀 강도를 유연하게 조절하는 개방-폐쇄 원칙(OCP) 사수.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 이동평균 복귀 모델 외삽 vs 단순 직전값(LOCF) 대치:
  - 장점: 결측 발생 직전의 단기 과열/과매도 노이즈가 유입되는 것을 방지하고 시계열 고유의 역사적 중심선 분포를 안정적으로 유지함.
  - 단점: 자산이 강력한 국면 전환(Regime Shift)이나 추세적 돌파(Breakout) 중일 때 결측이 발생하면 실제 가격 추세를 과소평가할 수 있음.
  - 근거: 다운스트림 모델이 자산의 '평균 회귀적 성향'을 피처 구조로 학습할 때, 정적/추세 확장 버킷과 완벽한 삼각 편대를 이루는 필수 통계적 대조군임.
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, List
from src.common.exceptions import ImputationExecutionError
from src.preprocessor.tasks.missing_value.abstract_imputer import AbstractImputer

# ==============================================================================
# Main Class/Functions
# ==============================================================================


class MovingAverageImputer(AbstractImputer):
    """최근 이동평균선으로의 복귀 관성을 통계적으로 모델링하여 단기 결측치를 평균 회귀 보간하는 구체 전략 클래스."""

    def transform(
        self,
        df: pd.DataFrame,
        target_assets: List[str],
        **kwargs: Any
    ) -> pd.DataFrame:
        """설정된 배치 윈도우 데이터프레임 내에서 지정된 단기 자산군 컬럼의 결측치를 이동평균 회귀 경로로 보간합니다.

        Args:
            df (pd.DataFrame): Ingestion 레이어에서 적재된 20거래일 슬라이딩 윈도우 원본 데이터프레임.
            target_assets (List[str]): 진단 리포트에 의거하여 단기 결측(10% 이하)으로 분류되어 
                본 버킷에서 처리할 대상 자산 코드 목록.
            **kwargs (Any): 상위 라우터 및 팩토리로부터 주입되는 가변 인자 매개변수 사전.
                - rolling_window (int, optional): 이동평균 계산에 사용할 과거 윈도우 길이. 기본값 20.
                - reversion_speed (float, optional): 평균 회귀 강도 파라미터 (0 < reversion_speed <= 1). 기본값 0.5.

        Returns:
            pd.DataFrame: 지정된 target_assets 컬럼들의 결측치가 이동평균 복귀 가중치로 정밀 보간 완료된 데이터프레임.

        Raises:
            ImputationExecutionError: 수리적 연산 불능, 행렬 차원 비정합성 등 판다스 수리 엔진 
                내부 장애 발생 시 문맥 컨텍스트를 봉인하여 상위 오케스트레이터로 전파.
        """
        # [설계 의도] 파이썬 컴파일 최적화 옵션(-O)에 의해 무력화될 위험이 있는 assert 구문 대신,
        # 상시 운영 환경에서도 철저한 방어벽 역할을 수행할 수 있도록 명시적 타입 검증 및 커스텀 구조화 예외를 처리함.
        if not isinstance(df, pd.DataFrame):
            raise ImputationExecutionError(
                message="입력 데이터 매트릭스가 유효한 pd.DataFrame 타입이 아닙니다.",
                imputer_type=self.__class__.__name__,
                target_assets=target_assets
            )

        # [설계 의도] 처리해야 할 대상 자산 프레임이 존재하지 않는 공집합 조건(Empty Set)의 경우,
        # 불필요한 연산 자원 오버헤드를 원천 방지하기 위해 즉시 인풋 인스턴스를 조기 반환(Early Return)함.
        if not target_assets:
            return df

        try:
            imputed_df = df.copy()

            rolling_window = kwargs.get("rolling_window", 20)
            reversion_speed = kwargs.get("reversion_speed", 0.5)

            target_df = imputed_df[target_assets]

            # 수치형 자산과 비수치형(문자열/범주형) 자산 격리 분리
            numeric_assets = target_df.select_dtypes(include=['number']).columns.tolist()
            non_numeric_assets = [col for col in target_assets if col not in numeric_assets]

            # 1. 비수치형 자산: 이동평균 연산 불가하므로 LOCF(ffill/bfill) 대치
            if non_numeric_assets:
                imputed_df[non_numeric_assets] = imputed_df[non_numeric_assets].ffill(axis=0).bfill(axis=0)

            # 2. 수치형 자산: 이동평균 평균 복귀 관성 보간 연산집행
            if numeric_assets:
                num_target_df = target_df[numeric_assets]
                base_locf = num_target_df.ffill(axis=0).bfill(axis=0)
                moving_averages = base_locf.rolling(window=rolling_window, min_periods=1).mean()

                consecutive_nan_counts = pd.DataFrame(index=num_target_df.index, columns=num_target_df.columns)
                for asset in numeric_assets:
                    asset_indicator = num_target_df[asset].notna().cumsum(axis=0)
                    consecutive_nan_counts[asset] = num_target_df[asset].isna().groupby(asset_indicator).cumcount()

                decay_factors = (1.0 - reversion_speed) ** consecutive_nan_counts
                imputed_df[numeric_assets] = moving_averages + (base_locf - moving_averages) * decay_factors

            return imputed_df

        except Exception as original_error:
            raise ImputationExecutionError(
                message="이동평균 기반 평균 회귀(Moving Average Mean Reversion) 보간 연산 중 판다스 수리 엔진에서 치명적 장애가 발생했습니다.",
                imputer_type=self.__class__.__name__,
                target_assets=target_assets,
                original_exception=original_error
            )