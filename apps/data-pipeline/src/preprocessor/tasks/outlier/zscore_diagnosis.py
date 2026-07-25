"""
정규분포 점수(Z-Score)의 표준편차 거리를 활용하여 금융 자산별 단기 변동성 임계 범위를 초과하는 이례 이상치를 진단하는 최하위 구체 엔진 컴포넌트

[전체 데이터 흐름 설명 (Input -> Output)]
1. Initialization: 상위 오케스트레이터 태스크로부터 변동성 임계 경계선 설정을 위한 Z-Score threshold 임계치 수치 인자를 개별 주입받아 바인딩.
2. Input: 1차 결측치 보간이 완결되어 공백 셀이 존재하지 않는 20거래일 룩백 윈도우 가격 데이터프레임.
3. Processing:
   - 각 자산 컬럼축 단위로 로컬 윈도우 내부의 평균(Mean)과 표준편차(Std)를 판다스 벡터 연산으로 산출.
   - 각 가격 데이터 포인트와 평균과의 편차를 표준편차로 나누어 정밀한 표준화 점수(Z-Score Matrix) 빌드.
   - 산출된 Z-Score 절대값이 외부 주입 임계치(threshold)를 초과하여 벗어난 좌표를 탐색하여 True로 마스킹 처리.
4. Output: 수리 연산 완료 후 상위 인터페이스 계약 표준에 부합하는 pd.DataFrame(Boolean 타입) 사출.

주요 기능:
- [Parametric Volatility Tracking] 시계열의 단기 변동성 확장(Volatility Clustering) 현상에 연동되는 동적 표준화 임계 구간 설정.
- [Pandas Matrix Broadcasting] 별도의 자산별 루프 제어 없이 행렬 전체를 한 번에 연산하여 CPU 캐시 효율 및 인메모리 처리 속도 극대화.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 정규분포(Z-Score) 기반의 일변량 탐지 기법 채택 vs 사분위수(IQR) 기반의 탐지 기법 대비:
  - 장점: 주가의 움직임이 비교적 안정적인 평시 국면(Normal Regime)에서 발생하는 미시적인 비정상 충격 패턴과 변동성 이탈 징후를 IQR 대비 훨씬 정밀하고 민감하게 포착함.
  - 단점: 데이터 내부의 극단적 스파이크(Spike) 오염이 이미 존재할 경우, 평균과 표준편차 자체가 심각하게 비대해져 실제 이상치를정상 데이터로 오판하는 '통계치 왜곡 전염(Masking Effect)'에 취약함.
  - 근거: 우리는 전방 레이어에서 1차 보간(Pass 1)을 수행하여 비정상 공백을 메운 정제된 행렬을 입력받음. 또한, 오탐지 공백은 머신러닝 다변량 모델(Isolation Forest) 버킷과 병렬 교차 대조하여 상호 보완하도록 실험 우주를 설계했으므로, 전통 계량학적 기준인 Z-Score 엔진을 배치하는 것이 타당함.
"""

import pandas as pd

from src.preprocessor.tasks.outlier.abstract_diagnosis import AbstractOutlierDiagnosis


# ==============================================================================
# Main Class
# ==============================================================================
class ZScoreDiagnosis(AbstractOutlierDiagnosis):
    """정규화 점수 매트릭스를 연산하여 주입된 임계 임계 배수를 벗어난 자산별 이상치 좌표를 마스킹하는 구체 진단 클래스."""

    def __init__(self, threshold: float = 3.0) -> None:
        """하위 수리 연산에 적용할 Z-Score 표준편차 임계 파라미터를 캡슐화합니다.

        Args:
            threshold (float): 평균으로부터 표준편차의 몇 배수까지를 정상 범주로 인정할 것인지 규정하는 임계치 (기본값: 3.0).
        """
        # [설계 의도] 외부 yaml 설정에서 명시한 통계적 가드레일 배수를 인스턴스 소유로 동적 바인딩하여,
        # 연산 레이어의 하드코딩을 배제하고 파이프라인의 유연한 하이퍼파라미터 튜닝을 보장함.
        self._threshold: float = threshold

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """평균과 표준편차를 활용한 표준화 점수 연산을 통해 이상치 위치를 판별합니다.

        Args:
            df (pd.DataFrame): 전방 보간 레이어에서 NaN 잔차가 완벽히 청정화되어 유입된 가격 데이터프레임.

        Returns:
            pd.DataFrame: 원본 행렬과 인덱스/컬럼이 1:1 일치하는 불리언 마스크 매트릭스.
        """
        # [설계 의도] 판다스의 컬럼 벡터 통계량 산출 로직(axis=0)을 가동하여 190종 이상의 자산 컬럼 데이터 전역의
        # 로컬 대표 통계치(mean, std Series)를 단 1회의 선형 메모리 스캔으로 초고속 확보함.
        means: pd.Series = df.mean(axis=0)
        stds: pd.Series = df.std(axis=0)

        # [설계 의도] 금융 시계열 데이터프레임의 특정 컬럼 내 변동성이 제로(0)에 수렴하여 분모가 0이 되는
        # 수리적 패닉(ZeroDivisionError / NaN Anomaly) 현상을 방어하기 위해 안전 가드 수치를 하한선으로 적용함.
        min_std_protection = 1e-8
        stds = stds.replace(0.0, min_std_protection)

        # [설계 의도] 미래 시점의 전체 가격 통계량을 미리 당겨와 판정함으로써 인과 관계를 파괴하는 미래 참조 편향(Look-Ahead Bias)을
        # 완벽 차단하기 위해, 오직 입력으로 들어온 과거 룩백 윈도우 시퀀스 내부 통계량만을 한정 계산에 사용함.
        z_scores: pd.DataFrame = (df - means) / stds

        # [설계 의도] 판다스의 브로드캐스팅 연산을 트리거하여 절대값 Z-Score가 설정 임계치를 초과하는지 검증하고,
        # 원본과 완벽한 차원 불변성(Invariant) 계약을 충족하는 1:1 불리언 마스크 프레임을 사출함.
        outlier_mask: pd.DataFrame = z_scores.abs() > self._threshold

        return outlier_mask