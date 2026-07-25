"""
머신러닝 기반 다변량 고립 포레스트(Isolation Forest) 알고리즘을 활용하여 자산 간 상관 구조를 파괴하는 다차원 이상치를 진단하는 최하위 구체 엔진 컴포넌트

[전체 데이터 흐름 설명 (Input -> Output)]
1. Initialization: 상위 오케스트레이터 태스크로부터 AI 모델 제어를 위한 contamination(오염 비율) 및 random_state(난수 시드) 인자를 주입받아 바인딩.
2. Input: 1차 결측치 보간이 완결되어 공백 셀이 존재하지 않는 20거래일 룩백 윈도우 가격 데이터프레임.
3. Processing:
   - 다변량 공간 연산을 위해 입력 데이터프레임을 전치(Transpose)하여 자산을 샘플(Samples)로, 20일의 시퀀스를 피처(Features)로 구조 변환.
   - 무작위 분할 트리 구조를 생성하여 다른 자산들의 데이터 결(Trend)로부터 고속으로 고립되는 이상 경로 자산 검출.
   - 모델 예측 결과 이상치로 판명된 자산 컬럼의 해당 윈도우 내 전 시점을 True로 매핑하는 브로드캐스팅 마스크 행렬 형성.
4. Output: 수리 연산 완료 후 상위 인터페이스 계약 표준에 부합하는 pd.DataFrame(Boolean 타입) 사출.

주요 기능:
- [Multivariate Correlation Capture] 일변량 통계량(IQR, Z-Score)으로는 잡을 수 없는 자산 간의 상대적 공분산 파괴 및 오염 피처 스펙트럼 포착.
- [Deterministic AI Execution] random_state 시드를 내부 고정하여 슬라이딩 윈도우 배치가 매일 반복 실행되더라도 동일 인풋에 대해 일관된 결정론적 무결성 확보.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 자산축 전치 기반의 다변량 Isolation Forest 채택 vs 타임스탬프축 기준의 이상 일자 탐지 대비:
  - 장점: 190종 이상의 고차원 자산 우주(Universe) 속에서 정상적인 시장 충격을 넘어선 벤더사 전산 데이터 오염 및 특정 자산의 비정상 동학을 공간적으로 완벽히 분리해 냄.
  - 단점: 자산 자체를 이상치로 지목하여 윈도우 전체를 마스킹하므로 미시적인 단일 날짜의 스파이크 충격에 대해 과도한 전역 마스킹(Over-Masking)을 유발할 리스크가 있음.
  - 근거: 미시적 단일 좌표 오염은 전방에 배치된 IQR 및 Z-Score 버킷이 촘촘하게 상호 보완하며 잡아내고 있음. 따라서 AI 레이어에서는 모델의 가중치를 통째로 뒤틀어버리는 '상관관계 붕괴 자산 경로' 자체를 격리하는 방어벽 역할을 수행하는 것이 절대적으로 타당함.
"""

from typing import Optional
import pandas as pd
from sklearn.ensemble import IsolationForest

from src.preprocessor.tasks.outlier.abstract_diagnosis import AbstractOutlierDiagnosis


# ==============================================================================
# Main Class
# ==============================================================================
class IsolationForestDiagnosis(AbstractOutlierDiagnosis):
    """고립 포레스트 트리를 빌드하여 자산 간 다차원 공분산 궤적을 이탈한 이상치 좌표를 마스킹하는 머신러닝 구체 진단 클래스."""

    def __init__(self, contamination: float = 0.05, random_state: int = 42) -> None:
        """하위 머신러닝 연산 및 트리 분할 제어에 주입할 하이퍼파라미터를 캡슐화합니다.

        Args:
            contamination (float): 데이터 블록 내에서 이상치로 규정할 자산의 예상 비율 범위 (기본값: 0.05).
            random_state (int): 의사결정 트리의 무작위 분할 시 결정론적 재현성을 보장하기 위한 난수 고정 시드 (기본값: 42).
        """
        # [설계 의도] 팩토리 레이어에서 파싱된 순수 하이퍼파라미터를 안전하게 전사 바인딩하여,
        # 연산 엔진 내부의 유연한 실험 분기 튜닝 가용성을 극대화합니다.
        self._contamination: float = contamination
        self._random_state: int = random_state

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """전치 행렬 기반의 고립 트리 모델 피팅을 통해 상관관계가 파괴된 다변량 이상치 위치를 판별합니다.

        Args:
            df (pd.DataFrame): 전방 보간 레이어에서 NaN 잔차가 완벽히 청정화되어 유입된 가격 데이터프레임.

        Returns:
            pd.DataFrame: 원본 행렬과 인덱스/컬럼이 1:1 일치하는 불리언 마스크 매트릭스.
        """
        # [설계 의도] Isolation Forest는 행(Row)을 샘플 단위로 인지하므로, 주가 데이터프레임을 명시적으로 
        # 전치(.T)하여 190여 종의 자산을 '샘플'로, 20거래일의 시계열 가격 변동을 '피처'로 치환하여 피팅을 수행합니다.
        df_transposed: pd.DataFrame = df.T

        # [설계 의도] 고차원 공간 데이터의 병렬 연산 및 분할 트리 연산의 인프라 효율을 극대화하기 위해, 
        # 내부 CPU 자원을 모두 가동하는 n_jobs=-1 멀티프로레싱 가드레일을 장착합니다.
        model: IsolationForest = IsolationForest(
            contamination=self._contamination,
            random_state=self._random_state,
            n_jobs=-1
        )

        # 모델 피팅 및 예측 집행 (-1: 다변량 고립 이상치, 1: 정상 패턴)
        predictions = model.fit_predict(df_transposed)
        
        # 이상치 자산 목록 필터링용 불리언 시리즈 변환
        is_outlier_asset: pd.Series = pd.Series(predictions == -1, index=df_transposed.index)

        # [설계 의도] 원본 가격 데이터프레임과 완벽하게 대칭되는 불변성(Invariant) 차원 계약을 사수하기 위해,
        # 기본 디폴트 상태가 전 차원 정상(False)인 마스크 프레임을 선제 구축한 후 슬라이싱 매핑합니다.
        outlier_mask: pd.DataFrame = pd.DataFrame(False, index=df.index, columns=df.columns)

        # [설계 의도] 머신러닝 모델이 지목한 이상 자산들의 컬럼 위치를 포착하여 해당 자산의 20거래일 전체 경로 좌표를
        # True로 마스킹합니다. 이를 통해 후행 정제 레이어가 Two-Pass 기반 재보간 연쇄를 트리거하도록 신호를 발행합니다.
        outlier_mask.loc[:, is_outlier_asset] = True

        return outlier_mask