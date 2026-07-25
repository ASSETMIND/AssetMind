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
            # [설계 의도] 동렬 앙상블 다중 버킷 실험 구조 환경에서 상호 버킷 간 데이터 프레임 참조 오염 
            # (Side-Effect)을 철저히 차단하고 데이터 무결성을 보장하기 위해 명시적 깊은 복사를 수행함.
            imputed_df = df.copy()

            # [설계 의도] 외부 YML 설정을 통해 파라미터를 동적으로 안전하게 꺼내오고, 누락 시 도메인 최적 하이퍼파라미터를 방어적으로 매핑함.
            rolling_window = kwargs.get("rolling_window", 20)
            reversion_speed = kwargs.get("reversion_speed", 0.5)

            # [설계 의도] 자산 이질성 사수 원칙에 맞춰 타겟 자산프레임 서브셋 행렬만 슬라이싱하여 격리 연산 블록을 구성함.
            target_df = imputed_df[target_assets]

            # [설계 의도] 1차 베이스라인 위치를 잡기 위해 ffill()을 수행한 데이터프레임을 생성함.
            # 이 프레임은 이동평균선 산출의 연속성 확보 및 결측 발생 시점의 '직전 가격 위치'를 고정하는 역할을 전담함.
            base_locf = target_df.ffill(axis=0).bfill(axis=0)

            # [설계 의도] 자산별 고유의 역사적 균형선인 이동평균(Moving Average) 행렬을 벡터 연산으로 도출함.
            # 데이터 초기 진입점의 결측 전파를 방어하기 위해 min_periods=1 제약을 주입하여 수리적 안전성을 사수함.
            moving_averages = base_locf.rolling(window=rolling_window, min_periods=1).mean()

            # [설계 의도] Pandas 엔진은 2차원 DataFrame 구조를 .groupby()의 그루퍼 키 배열로 수용하지 못하고 발산합니다.
            # 따라서 본 모듈의 핵심 철학인 [Univariate Isolation] (단변량 격리 원칙)에 입각하여, 자산별(Column-wise)로 
            # 1차원 Series 단위의 groupby-cumcount 트릭을 격리 집행함으로써 판다스 엔진의 차원 정합성을 완벽하게 사수합니다.
            consecutive_nan_counts = pd.DataFrame(index=target_df.index, columns=target_df.columns)
            for asset in target_assets:
                asset_indicator = target_df[asset].notna().cumsum(axis=0)
                consecutive_nan_counts[asset] = target_df[asset].isna().groupby(asset_indicator).cumcount()

            # ==============================================================================
            # [설계 의도] 평균 회귀 차분 방정식의 수학적 벡터화: 
            # P_t = P_{t-1} + reversion_speed * (MA_t - P_{t-1}) 공식을 연속 결측 구간에 대해 풀면 다음과 같음:
            # P_t = MA_t + (P_{last_valid} - MA_t) * (1 - reversion_speed)^consecutive_count
            # 즉, 직전 가격 위치와 이동평균선 간의 이격 거리가 시간 흐름에 따라 (1 - reversion_speed)의 속도로 지수 감쇄하는 원리임.
            # ==============================================================================
            decay_factors = (1.0 - reversion_speed) ** consecutive_nan_counts
            
            # [설계 의도] 넘파이 브로드캐스팅 엔진을 통해 최종 평균 회귀 보간 행렬을 일괄 합성하여 원본 프레임축에 정밀 대입함.
            imputed_df[target_assets] = moving_averages + (base_locf - moving_averages) * decay_factors

            return imputed_df

        except Exception as original_error:
            # [설계 의도] 판다스/넘파이 내부 수학 연산 중 발생할 수 있는 데이터 타입 비정합성 및 수리 패닉을 포착하여,
            # 구조화된 장애 문맥과 함께 전처리 레이어 전용 예외인 ImputationExecutionError로 체인 래핑함.
            raise ImputationExecutionError(
                message="이동평균 기반 평균 회귀(Moving Average Mean Reversion) 보간 연산 중 판다스 수리 엔진에서 치명적 장애가 발생했습니다.",
                imputer_type=self.__class__.__name__,
                target_assets=target_assets,
                original_exception=original_error
            )