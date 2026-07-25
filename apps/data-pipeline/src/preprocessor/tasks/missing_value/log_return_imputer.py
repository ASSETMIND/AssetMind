"""
[모듈 목적 및 상세 설명]
골드 파이프라인(Gold Pipeline) 전처리 계층 내 단기 결측치 처리를 위한 실험군 버킷(Bucket B) 구체 전략 객체입니다.
자산별 최근 20거래일 Window 내의 가용 역사적 로그 수익률(Log Return)의 산술 평균을 계산하고,
결측이 발생한 시점에 해당 자산 고유의 등락 모멘텀(Drift) 관성을 복리로 누적 반영하여 가격을 외삽(Extrapolation)합니다.
이를 통해 결측 당일의 수익률이 기계적으로 0% 고착되는 LOCF의 한계를 통계학적으로 극복합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 결측 자산 컬럼을 포함하고 있는 20거래일 슬라이딩 Lookback 윈도우 원본 데이터프레임 및 단기 라우팅 대상 자산 목록.
2. Processing: 
   - 전 타임스탬프 대비 로그 수익률 행렬 변환 후 자산별 평균 등락률(μ) 산출.
   - 정상 거래일의 cumsum 패러다임을 이용해 결측 구간별 연속 누적 공백 일수(Run Length) 행렬을 벡터로 계산.
   - LOCF 기본 프레임에 exp(누적일수 * μ)를 행렬 곱하여 추세가 반영된 가격으로 최종 변환.
3. Output: 지정된 단기 자산들의 공백이 고유 등락 추세로 정밀 대치 완료된 복제본 데이터프레임 반환.

주요 기능:
- [Matrix-Wide Drift Injection] Python 가독성을 해치는 루프를 배제하고, 판다스 groupby cumcount 트릭을 통한 전 자산 등락률 동시 주입.
- [Univariate Isolation] 타 자산 클래스의 데이터 노이즈 간섭을 100% 차단하고 오직 당해 자산의 과거 물리적 역사 흐름만 참조.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 로그 수익률 평균 기반 외삽 vs 단순 선형(Linear) 보간:
  - 장점: 미래 가격을 알 수 없는 리얼타임 배치 최전선(20번째 행) 결측 상황에서도 완벽히 작동하며 미래 참조 편향을 원천 차단함.
  - 단점: 최근 20일 윈도우 내에 비정상적인 일회성 폭등/폭락 쇼크가 존재할 경우 평균 등락률이 왜곡되어 가짜 잔차가 증폭될 수 있음.
  - 근거: 다운스트림 머신러닝 모델이 자산의 '단기 모멘텀 관성'을 피처로 학습할 때 분포 왜곡을 최소화하기 위한 필수적인 통계적 대조군 버킷임.
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, List
from src.common.exceptions import ImputationExecutionError
from src.preprocessor.tasks.missing_value.abstract_imputer import AbstractImputer

# ==============================================================================
# Main Class/Functions
# ==============================================================================


class LogReturnImputer(AbstractImputer):
    """최근 역사적 로그 수익률 추세를 기반으로 단기 결측치를 복리 외삽 보간하는 구체 전략 클래스."""

    def transform(
        self,
        df: pd.DataFrame,
        target_assets: List[str],
        **kwargs: Any
    ) -> pd.DataFrame:
        """설정된 배치 윈도우 데이터프레임 내에서 지정된 단기 자산군 컬럼의 결측치를 로그 수익률 추세로 보간합니다.

        Args:
            df (pd.DataFrame): Ingestion 레이어에서 적재된 20거래일 슬라이딩 윈도우 원본 데이터프레임.
            target_assets (List[str]): 진단 리포트에 의거하여 단기 결측(10% 이하)으로 분류되어 
                본 버킷에서 처리할 대상 자산 코드 목록.
            **kwargs (Any): 상위 라우터 및 팩토리로부터 주입되는 가변 인자 매개변수 사전 (본 모듈은 미사용).

        Returns:
            pd.DataFrame: 지정된 target_assets 컬럼들의 결측치가 로그 수익률 관성으로 정밀 보간 완료된 데이터프레임.

        Raises:
            ImputationExecutionError: 수리적 연산 불능, 행렬 차원 비정합성 등 판다스 수리 엔진 
                내부 장애 발생 시 문맥 컨텍스트를 봉인하여 상위 오케스트레이터로 전파.
        """
        # [설계 의도] 파이썬 컴파일 최적화 플래그에 의해 무력화될 위험이 있는 assert 구문 대신,
        # 상시 운영 환경에서도 철저한 방어벽 역할을 수행할 수 있도록 명시적 타입 검증 및 커스텀 구조화 예외를 처리함.
        if not isinstance(df, pd.DataFrame):
            raise ImputationExecutionError(
                message="입력 데이터 매트릭스가 유효한 pd.DataFrame 타입이 아닙니다.",
                imputer_type=self.__class__.__name__,
                target_assets=target_assets
            )

        # [설계 의도] 처리해야 할 대상 자산프레임이 존재하지 않는 휴두 조건(Empty Set)의 경우,
        # 메모리 카피 오버헤드를 원천 방지하기 위해 즉시 인풋 인스턴스를 조기 반환(Early Return)함.
        if not target_assets:
            return df

        try:
            # [설계 의도] 동렬 앙상블 다중 버킷 실험 구조 환경에서 상호 버킷 간 데이터 프레임 참조 오염 
            # (Side-Effect)을 철저히 차단하고 데이터 무결성을 보장하기 위해 명시적 깊은 복사를 수행함.
            imputed_df = df.copy()

            # [설계 의도] 190종 금융 자산 간의 극단적 이질성(Heterogeneity)을 존중하여 타 자산의 오염 유입을 막기 위해,
            # 타겟 자산프레임 서브셋 행렬만 슬라이싱하여 격리 연산 블록을 구축함.
            target_df = imputed_df[target_assets]

            # [설계 의도] 금융 시계열의 가격 결정 메커니즘을 반영하기 위해 일별 로그 수익률(Log Return) 행렬을 구함.
            # 복잡한 파이썬 루프를 배제하고 판다스 내부 C-엔진의 shift 연산 및 넘파이 벡터화 로그 함수를 연동함.
            log_returns = np.log(target_df / target_df.shift(1))

            # [설계 의도] 각 자산 클래스별 최근 윈도우 내 가용 등락 모멘텀의 대표값인 산술 평균 등락률(μ) 벡터를 도출함.
            # 윈도우 내부 결측으로 인해 발생하는 NaN 값은 통계 추정 왜곡을 막기 위해 산술 평균 계산에서 자동 제외(skipna=True)함.
            mean_drifts = log_returns.mean(axis=0, skipna=True)

            # [설계 의도] 만약 윈도우 전체가 결측이거나 가용 수익률이 없어 평균 등락률 추정이 불가능한 고립 자산이 존재할 경우,
            # 수리적 NaN 전파 크래시를 방지하기 위해 추세가 없는 상태(Drift = 0.00, 즉 LOCF와 동일)로 안전하게 결측 대체 디폴트 처리함.
            mean_drifts = mean_drifts.fillna(0.0)

            # [설계 의도] Pandas 엔진은 2차원 DataFrame 구조를 .groupby()의 그루퍼 키 배열로 수용하지 못하고 발산합니다.
            # 따라서 본 모듈의 핵심 철학인 [Univariate Isolation] (단변량 격리 원칙)에 입각하여, 자산별(Column-wise)로 
            # 1차원 Series 단위의 groupby-cumcount 트릭을 격리 집행함으로써 판다스 엔진의 차원 정합성을 완벽하게 사수합니다.
            consecutive_nan_counts = pd.DataFrame(index=target_df.index, columns=target_df.columns)
            for asset in target_assets:
                asset_indicator = target_df[asset].notna().cumsum(axis=0)
                consecutive_nan_counts[asset] = target_df[asset].isna().groupby(asset_indicator).cumcount()
                
            # [설계 의도] 결측치를 채우기 위한 베이스라인 위치 확보를 위해 1차적으로 ffill() 및 bfill()을 동결 적용함.
            # bfill()은 윈도우 첫 진입점(1일 차) 경계 결측 발생 시 차원 방어를 위한 폴백 레이어로 연동함.
            base_locf = target_df.ffill(axis=0).bfill(axis=0)

            # [설계 의도] 최종 가격 외삽 공식집행: P_t = P_{t-consecutive_count} * exp(consecutive_nan_counts * μ)
            # 넘파이 브로드캐스팅 엔진을 통해 기 존재하던 LOCF 가격 위치에 고유 추세 모멘텀 가중치를 일괄 정밀 곱 연산 처리함.
            trend_factors = np.exp(consecutive_nan_counts * mean_drifts)
            imputed_df[target_assets] = base_locf * trend_factors

            return imputed_df

        except Exception as original_error:
            # [설계 의도] 넘파이/판다스 내부 수학 연산 중 발생할 수 있는 데이터 타입 불일치 및 0 나누기 등의 
            # 예기치 못한 시스템 패닉을 포착하여 중앙 집중형 로그 구조에 즉시 적재할 수 있도록 전처리 레이어 전용 시스템 예외로 체인 래핑함.
            raise ImputationExecutionError(
                message="로그 수익률 추세 관성 반영(Log Return Trend Extension) 보간 연산 중 판다스 수리 엔진에서 치명적 장애가 발생했습니다.",
                imputer_type=self.__class__.__name__,
                target_assets=target_assets,
                original_exception=original_error
            )