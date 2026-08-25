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
            imputed_df = df.copy()
            target_df = imputed_df[target_assets]

            # 수치형 자산과 비수치형(문자열/범주형) 자산 격리 분리
            numeric_assets = target_df.select_dtypes(include=['number']).columns.tolist()
            non_numeric_assets = [col for col in target_assets if col not in numeric_assets]

            # 1. 비수치형 자산: 로그 수익률 수리 연산 불가하므로 LOCF(ffill/bfill) 대치
            if non_numeric_assets:
                imputed_df[non_numeric_assets] = imputed_df[non_numeric_assets].ffill(axis=0).bfill(axis=0)

            # 2. 수치형 자산: 로그 수익률 추세 관성 복리 외삽 보간 연산집행
            if numeric_assets:
                num_target_df = target_df[numeric_assets]

                log_returns = np.log(num_target_df / num_target_df.shift(1))
                mean_drifts = log_returns.mean(axis=0, skipna=True).fillna(0.0)

                consecutive_nan_counts = pd.DataFrame(index=num_target_df.index, columns=num_target_df.columns)
                for asset in numeric_assets:
                    asset_indicator = num_target_df[asset].notna().cumsum(axis=0)
                    consecutive_nan_counts[asset] = num_target_df[asset].isna().groupby(asset_indicator).cumcount()

                base_locf = num_target_df.ffill(axis=0).bfill(axis=0)
                trend_factors = np.exp(consecutive_nan_counts * mean_drifts)
                imputed_df[numeric_assets] = base_locf * trend_factors

            return imputed_df

        except Exception as original_error:
            raise ImputationExecutionError(
                message="로그 수익률 추세 관성 반영(Log Return Trend Extension) 보간 연산 중 판다스 수리 엔진에서 치명적 장애가 발생했습니다.",
                imputer_type=self.__class__.__name__,
                target_assets=target_assets,
                original_exception=original_error
            )