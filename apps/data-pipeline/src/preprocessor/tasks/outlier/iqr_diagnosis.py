"""
사분위수간 범위(Interquartile Range)를 활용하여 금융 자산별 독립적인 시계열 분포 내 극단적 변동성 이상치를 진단하는 최하위 구체 엔진 컴포넌트

[전체 데이터 흐름 설명 (Input -> Output)]
1. Initialization: 상위 오케스트레이터 태스크로부터 통계량 분기 계산을 위한 배수 임계치(multiplier) 수치 인자를 개별 주입받아 바인딩.
2. Input: 1차 결측치 보간이 완결되어 공백 셀이 존재하지 않는 20거래일 룩백 윈도우 가격 데이터프레임.
3. Processing:
   - 각 자산 컬럼축 단위로 데이터 분포의 25% 지점(Q1)과 75% 지점(Q3)을 판다스 벡터 연산으로 계산.
   - 두 지점의 격차인 사분위간 범위(IQR = Q3 - Q1)에 주입된 multiplier 배수를 적용하여 상하한 임계 경계선 도출.
   - 원본 행렬과 동등한 크기 내에서 임계 경계선을 초과하여 이탈한 좌표를 탐색하여 True로 마스킹 처리.
4. Output: 수리 연산 완료 후 상위 인터페이스 계약 표준에 부합하는 pd.DataFrame(Boolean 타입) 사출.

주요 기능:
- [Non-Parametric Fat-Tail Defense] 평균과 표준편차를 쓰지 않고 백분위수를 활용하여 금융 시계열 특유의 Fat-Tail 분포 왜곡 현상을 상쇄함.
- [Pandas Vectorized Quantile] 컬럼 단위 루프문 없이 190종 이상의 대규모 고차원 행렬 사분위수를 단 1라인의 판다스 내부 C엔진 연산으로 일괄 처리.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 사분위수(IQR) 기반의 일변량 탐지 기법 채택 vs 정규분포(Z-Score) 기반의 탐지 기법 대비:
  - 장점: 극단적인 주가 급등락(Black Swan)이 포함된 작은 윈도우 안에서도 평균의 뒤틀림 현상이 없으므로, 비정상 가격 좌표를 매우 보수적이고 안정적으로 격리해 냄.
  - 단점: 자산 간의 동시 다발적 공분산 구조나 다차원적 연관 패턴(Correlation Breakdown)을 포착할 수 없어 다변량 이상치 검출 능력이 결여됨.
  - 근거: 우리는 다운스트림 실험 버킷에 다변량 모델(Isolation Forest)을 교차 배치해 변수를 통제하고 있음. 따라서 일변량 국면에서는 분포 왜곡에 가장 면역력이 높은 IQR 방식을 기저 엔진으로 확보하는 것이 아키텍처 다형성 관점에서 정석임.
"""

import pandas as pd

from src.preprocessor.tasks.outlier.abstract_diagnosis import AbstractOutlierDiagnosis


# ==============================================================================
# Main Class
# ==============================================================================
class IqrDiagnosis(AbstractOutlierDiagnosis):
    """사분위수 임계 경계선을 빌드하여 가격 매트릭스 내부의 개별 자산별 이상치 좌표를 마스킹하는 구체 진단 클래스."""

    def __init__(self, multiplier: float = 1.5) -> None:
        """하위 통계 연산에 적용할 IQR 배수 파라미터를 캡슐화합니다.

        Args:
            multiplier (float): 사분위간 범위에 곱해져 정상 범위를 확장할 통계 임계 배수 (기본값: 1.5).
        """
        # [설계 의도] 주입된 가중 배수를 인스턴스 정적 상태로 잠가, 매일 기동되는 
        # 슬라이딩 배치 시 시점 간 통계 경계선의 일치성과 결정론적 무결성을 확보함.
        self._multiplier: float = multiplier

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """사분위간 범위와 임계 배수를 결합한 벡터 연산을 통해 이상치 위치를 판별합니다.

        Args:
            df (pd.DataFrame): 전방 보간 레이어에서 NaN 잔차가 완벽히 청정화되어 유입된 가격 데이터프레임.

        Returns:
            pd.DataFrame: 원본 행렬과 인덱스/컬럼이 1:1 일치하는 불리언 마스크 매트릭스.
        """
        # [설계 의도] 판다스의 컬럼 벡터 연산(axis=0)을 직통 호출하여 190종 이상의 자산 컬럼을 
        # Python for 루프 없이 단일 연산 텐서 블록으로 밀어넣어 CPU 인메모리 연산 속도를 극대화함.
        q1: pd.Series = df.quantile(0.25, axis=0)
        q3: pd.Series = df.quantile(0.75, axis=0)
        iqr: pd.Series = q3 - q1

        # [설계 의도] 미래 시점의 통계량을 미리 참조하는 Look-Ahead Bias를 완벽히 차단하기 위해,
        # 오직 현재 주입된 로컬 슬라이딩 윈도우 프레임 내부 정보만을 이용하여 인과적 상하한 경계선을 구축함.
        lower_bound: pd.Series = q1 - (self._multiplier * iqr)
        upper_bound: pd.Series = q3 + (self._multiplier * iqr)

        # [설계 의도] 원본 데이터프레임의 인덱스 축 구조를 파괴하지 않고 유지하기 위해, 
        # 비교 연산의 브로드캐스팅(Broadcasting)을 가동시켜 고속으로 1:1 대칭 매트릭스 마스크를 성형함.
        outlier_mask: pd.DataFrame = (df < lower_bound) | (df > upper_bound)

        return outlier_mask