"""
[모듈 목적 및 상세 설명]
골드 파이프라인(Gold Pipeline) 전처리 계층 내 단기 결측치 처리를 위한 베이스라인 버킷(Bucket A) 구체 전략 객체입니다.
가장 전통적이고 검증된 금융 공학 표준인 직전값 유지(LOCF) 기법을 적용하여, 결측 구간에 인위적인 통계적 잔차나 
예측 노이즈를 주입하지 않고 시계열 데이터 고유의 거래적 연속성과 자산별 현재 가격 위치를 완벽하게 동결 보존합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 결측 자산 컬럼을 포함하고 있는 20거래일 슬라이딩 Lookback 윈도우 원본 데이터프레임 및 단기 라우팅 대상 자산 목록.
2. Processing: 지정된 자산 컬럼축을 추출하여 전방향 벡터화 채우기(ffill) 및 경계면 방어용 후방향 채우기(bfill)를 순차 적용.
3. Output: 지정된 단기 자산들의 공백이 무결하게 메워지고 차원이 100% 사수된 복제본 데이터프레임 반환.

주요 기능:
- [Vectorized Imputation] 판다스 내장 C-엔진 기반 벡터화 연산을 활용한 Python 루프 없는 초고속 결측 대치.
- [Boundary Protection] 슬라이딩 윈도우 첫 진입점(1일 차) 결측 발생 시 미래 참조 편향을 최소화하는 하향 폴백 체계 가동.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- LOCF 정적 대치 vs 확률적/수리적 모델 보간:
  - 장점: 새로운 가짜 잔차(Artifact)나 왜곡된 미래 정보를 생성하지 않으므로 금융 자산의 무작위 행보(Random Walk) 특성을 가장 완벽히 존중함.
  - 단점: 결측 기간 동안 해당 자산의 당일 수익률이 0%로 고착되어 자산 고유의 역사적 변동성 분포가 일시적으로 과소추정될 위험이 있음.
  - 근거: 본 전처리 시스템은 단기 결측에 대해 자산의 거시적 통계 성향(정적, 추세, 회귀)을 다중 버킷으로 대조 실증하는 구조를 취하므로, 
          LOCF는 시계열 종속성을 완벽히 잠그는 가장 고정적이고 신뢰할 수 있는 중심 베이스라인(Control Group) 역할을 수행함.
"""

from typing import Any, Dict, List
import pandas as pd
from src.common.exceptions import ImputationExecutionError
from src.preprocessor.tasks.missing_value.abstract_imputer import AbstractImputer

# ==============================================================================
# Main Class/Functions
# ==============================================================================
class LocfImputer(AbstractImputer):
    """직전값 유지(LOCF) 기법을 기반으로 단기 자산 결측치를 고속 벡터 연산 대치하는 구체 전략 클래스."""

    def transform(
        self,
        df: pd.DataFrame,
        target_assets: List[str],
        **kwargs: Any
    ) -> pd.DataFrame:
        """설정된 배치 윈도우 데이터프레임 내에서 지정된 단기 자산군 컬럼의 결측치(NaN)를 LOCF로 보간합니다.

        Args:
            df (pd.DataFrame): Ingestion 레이어에서 적재된 20거래일 슬라이딩 윈도우 원본 데이터프레임.
            target_assets (List[str]): 진단 리포트에 의거하여 단기 결측(10% 이하)으로 분류되어 
                본 버킷에서 처리할 대상 자산 코드 목록.
            **kwargs (Any): 상위 라우터 및 팩토리로부터 주입되는 가변 인자 매개변수 사전 (본 모듈은 미사용).

        Returns:
            pd.DataFrame: 지정된 target_assets 컬럼들의 결측치가 직전 가격으로 정밀 대치 완료된 데이터프레임.

        Raises:
            ImputationExecutionError: 판다스 내부의 행렬 차원 붕괴 또는 타입 불일치 등 
                수리 연산 중 예기치 못한 크래시 발생 시 구조화된 문맥을 담아 상위로 즉각 전파.
        """
        # [설계 의도] 함수 진입 시점(Entry Point)에서 인풋 행렬의 데이터 형식을 엄격히 검증하고,
        # 대상 자산이 비어있을 경우 불필요한 연산 낭비 없이 즉각 조기 반환(Early Return)을 집행함.
        assert isinstance(df, pd.DataFrame), "입력 데이터 매트릭스는 pd.DataFrame 타입이어야 합니다."
        
        if not target_assets:
            return df.copy()

        try:
            # [설계 의도] 원본 데이터프레임의 참조 무결성을 철저히 사수하고, 상위 서비스 레이어나
            # 동렬 앙상블 실험 버킷 간의 상호 데이터 오염(Side-Effect)을 원천 차단하기 위해 명시적 깊은 복사를 수행함.
            imputed_df = df.copy()

            # [설계 의도] 금융 시계열의 물리적 종속성을 유지하기 위해 판다스의 고속 벡터화 메서드인 
            # ffill(axis=0)을 사용하여 복잡한 Python for 루프 전개 없이 자산축 전체의 단기 공백을 일괄 대치함.
            imputed_df[target_assets] = imputed_df[target_assets].ffill()

            # [설계 의도] 슬라이딩 윈도우의 가장 첫 번째 행(1일 차)에 결측이 위치하여 ffill()로 밀어줄 
            # 어제의 가격 정보가 누락된 최전선 경계 조건(Boundary Condition)에 한해서만, 차원 방어를 위해 
            # 후방향 bfill()을 하향 폴백(Fallback) 보완책으로 연동함.
            imputed_df[target_assets] = imputed_df[target_assets].bfill()

            return imputed_df

        except Exception as original_error:
            # [설계 의도] 판다스 연산 레이어에서 발생할 수 있는 내부 차원 불정합이나 타입 에러를 포착하고,
            # 에러 당시의 가용 컨텍스트(구체 컴포넌트 명칭, 타겟 자산프레임 목록)를 누수 없이 봉인하여 
            # 중앙 집중형 시스템 예외로 체인 래핑(Raise) 전파함.
            raise ImputationExecutionError(
                message="직전값 유지(LOCF) 벡터 보간 연산 처리 중 판다스 수리 엔진 내부에서 치명적 장애가 발생했습니다.",
                imputer_type=self.__class__.__name__,
                target_assets=target_assets,
                original_exception=original_error
            )