"""
이상치 진단 마스크 정보를 기반으로 가격 매트릭스의 극단값을 통계적 상하한 경계선(Winsorization)으로 강제 수렴시키는 최하위 구체 정제 엔진

[전체 데이터 흐름 설명 (Input -> Output)]
1. Initialization: 상위 오케스트레이터 태스크로부터 상하한 임계선 산출용 배수 파라미터(multiplier) 인자를 개별 주입받아 바인딩.
2. Input: 1차 보간 완료 가격 데이터프레임(df) 및 대응되는 이상치 진단 불리언 마스크 매트릭스(mask).
3. Processing:
   - 각 자산 컬럼축(axis=0) 단위로 가격 분포의 25%(Q1) 및 75%(Q3) 백분위수와 사분위간 범위(IQR)를 벡터 연산.
   - multiplier를 적용한 인인과적 상하한 경계선(Lower/Upper Bound) 벡터를 동적 생성.
   - 마스크 행렬에서 True(이상치)인 좌표를 탐색하여, 상한을 초과한 값은 상한선으로, 하한을 미달한 값은 하한선으로 강제 치환(Capping).
4. Output: 원본 데이터프레임과 물리적 셰이프, 타임스탬프 인덱스 축이 100% 보존된 청정 가격 행렬 사출.

주요 기능:
- [Signal-Preserving Winsorization] 이상치 데이터를 무조건 NaN이나 0으로 뭉개지 않고, 경계선값으로 치환하여 극단적 변동성의 '방향성 시그널'을 하위 모델에 온전히 전달함.
- [Pandas Conditional Vectorization] 판다스의 np.where/where 연산을 다차원 브로드캐스팅하여 대규모 고차원 행렬 정제를 루프 없이 단일 텐서 블록 레벨에서 마감함.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 임계치 상하한 조정(Clipping) 정제 기법 채택 vs 타 자산 단면 중립화(Neutralization) 기법 대비:
  - 장점: 개별 자산이 당일 가졌던 고유의 고수익/고위험 알파 국면(Idiosyncratic Shock) 정보를 완전히 파멸시키지 않고 완충된 변동성 정보로 잔존시켜 다운스트림 트리 모델의 학습 기여도를 확보함.
  - 단점: 다변량 AI 탐지 기법(Isolation Forest)이 사출한 마스크와 결합할 때, Isolation Forest 자체는 상하한 선형 경계선 개념이 없으므로 clipping을 위해 일변량 통계량(IQR)을 내부에서 2중 재계산해야 하는 연산 중복이 발생함.
  - 근거: 금융 시계열 데이터에서 꼬리 위험(Tail Risk)은 노이즈인 동시에 중요한 모멘텀 시그널임. 따라서 모든 실험 버킷 중 자산 고유의 방향성 에너지를 가장 훌륭하게 보존하는 Clipping 엔진을 독립 컴포넌트로 완비하는 것이 포트폴리오의 실증주의 철학에 부합함.
"""

import pandas as pd
import numpy as np

from src.preprocessor.tasks.outlier.abstract_refinement import AbstractOutlierRefinement


# ==============================================================================
# Main Class
# ==============================================================================
class ClippingRefinement(AbstractOutlierRefinement):
    """진단 마스크가 포착한 이상치 좌표의 가격 수치를 사분위 임계 하한/상한선으로 수렴 정제하는 구체 엔진 클래스."""

    def __init__(self, multiplier: float = 1.5) -> None:
        """하위 수리 조정 연산에 적용할 IQR 임계 배수를 캡슐화합니다.

        Args:
            multiplier (float): 사분위간 범위에 곱해져 정상 범위를 규정할 통계적 확장 배수 (기본값: 1.5).
        """
        # [설계 의도] 상위 팩토리 설정 허브로부터 전달된 원자적 파라미터를 소유 상태로 잠가,
        # 슬라이딩 배치 연산 구동 시 모든 버킷 간의 통계적 정합 경계선을 일치시킵니다.
        self._multiplier: float = multiplier

    def refine(self, df: pd.DataFrame, mask: pd.DataFrame) -> pd.DataFrame:
        """주입된 이상치 마스크 좌표의 극단값들을 통계적 상하한선 수치로 강제 치환 정제합니다.

        Args:
            df (pd.DataFrame): 전방 레이어에서 1차 보간이 수료되어 유입된 완결 상태의 가격 데이터프레임.
            mask (pd.DataFrame): df와 1:1 대칭 크기를 가지며, 이상치 좌표 정보가 명시된 불리언 마스크 데이터프레임.

        Returns:
            pd.DataFrame: 정상 데이터는 보존되고, 이상치 위치만 상하한 캡(Cap)이 씌워진 청정 가격 데이터프레임.
        """
        # [설계 의도] 원본 주가 데이터프레임의 상태 불변성을 유지하고 사이드 이펙트를 완벽히 차단하기 위해,
        # 정제 연산 수행 전 메모리 상에 완전히 격리된 독립 카피본을 복성합니다.
        refined_df = df.copy()

        # 자산별(Column) 사분위수 및 IQR 통계량 벡터 일괄 계산
        q1: pd.Series = df.quantile(0.25, axis=0)
        q3: pd.Series = df.quantile(0.75, axis=0)
        iqr: pd.Series = q3 - q1

        # [설계 의도] Look-Ahead Bias(미래 참조 편향)를 원천 봉쇄하기 위해, 오직 주입된 
        # 로컬 룩백 윈도우 블록 내부의 독립적 통계량만으로 인과적 상상하한선을 구축합니다.
        lower_bounds: pd.Series = q1 - (self._multiplier * iqr)
        upper_bounds: pd.Series = q3 + (self._multiplier * iqr)

        # [설계 의도] for 루프를 통한 셀 단위 탐색을 배제하고, 판다스의 고속 벡터 연산 API인 .where()를 가동합니다.
        # mask가 True인 위치(이상치) 중, 상한선을 넘은 좌표는 upper_bounds로, 하한선을 미달한 좌표는 lower_bounds로
        # 정확히 정렬 매핑하여 수렴(Winsorization) 연산을 단일 패스로 마감합니다.
        clipped_df = df.clip(lower=lower_bounds, upper=upper_bounds, axis=1)
        
        # mask가 True인 좌표만 clipped_df의 값으로 덮어쓰고, False인 정상 좌표는 원본 refined_df 값을 고수함
        refined_df = refined_df.where(~mask, clipped_df)

        return refined_df