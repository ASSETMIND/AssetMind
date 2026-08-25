"""
이상치 진단 마스크 정보를 기반으로 비정상 극단값 좌표를 np.nan(결측치)으로 변환하여 후방 Two-Pass 보간 연쇄를 트리거하는 최하위 구체 정제 엔진

[전체 데이터 흐름 설명 (Input -> Output)]
1. Initialization: 상위 오케스트레이터 태스크로부터 문자열 포맷 또는 정적 인자(target_value)를 주입받아 내부 결측치 지시자 값으로 바인딩.
2. Input: 1차 보간 완료 가격 데이터프레임(df) 및 대응되는 이상치 진단 불리언 마스크 매트릭스(mask).
3. Processing:
   - 원본 가격 데이터의 상태 불변성 확보를 위해 명시적 깊은 복사 수행.
   - 판다스의 고속 마스킹 벡터 연산을 가동하여 마스크 행렬에서 True(이상치)인 좌표의 가격을 np.nan으로 일괄 강제 치환.
4. Output: 이상치 좌표가 결측 상태로 격리 전사되어 후방 Pass 2 보간 처리가 즉시 가동될 수 있는 데이터프레임 사출.

주요 기능:
- [Two-Pass Pipeline Bridge] 이상치를 인위적 결측치로 치환함으로써, 기존에 고도화가 수료된 결측치 보간 엔진(MissingValueImputation)을 그대로 재사용하는 완벽한 DRY 원칙 구현.
- [Pandas High-Speed Masking] Python Level의 셀 순회 없이 대규모 행렬 전역의 이상치 수치를 단 1회의 연산 블록으로 NaN 청쇄 마감.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 이상치 좌표의 NaN 마스킹 후 재보간 기법 채택 vs 정적 상하한 조정(Clipping) 기법 대비:
  - 장점: 극단적인 변동성 쇼크나 전산 노이즈 수치 자체를 행렬 내부에서 완전히 소거한 후, 시계열 인과 결에 맞춰 부드러운 예측 곡선(Kalman Filter 등)으로 재성형하므로 하위 선형 모델의 예측 안정성을 극대화함.
  - 단점: 이상치를 NaN으로 바꾼 순간 데이터의 원본 정보가 소실되므로, 당일 장세에 진짜 실재했던 시장 충격(Tail Risk) 시그널의 에너지 크기가 평탄화되는 정보 거세 리스크가 존재함.
  - 근거: 우리는 모든 전처리 조합 우주를 27대 분기 버킷으로 동시 사출하여 하위 모델군이 스스로 정량 평가하도록 설계함. 트리 기반 모델과 선형 모델 각각에 최적화된 전처리 입력을 제공하기 위해, 마스킹 엔진을 독립 컴포넌트로 확보하는 것이 실증주의 관점에서 필수적임.
"""

from typing import Any, Optional
import numpy as np
import pandas as pd

from src.preprocessor.tasks.outlier.abstract_refinement import AbstractOutlierRefinement


# ==============================================================================
# Main Class
# ==============================================================================
class MaskingRefinement(AbstractOutlierRefinement):
    """진단 마스크가 지목한 이상치 위치의 수치들을 np.nan 결측치 상태로 치환 격리하는 구체 엔진 클래스."""

    def __init__(self, target_value: Any = "NaN") -> None:
        """하위 마스킹 연산에 적용할 결측치 표기 속성을 캡슐화합니다.

        Args:
            target_value (Any): 외부 yaml에서 유입되는 결측 타겟 지시자 (기본값: "NaN").
        """
        # [설계 의도] 외부 설정 파일 스키마에서 문자열 "NaN" 형태로 유입되더라도, 
        # 판다스 내부의 정밀한 부동소수점 결측 연산이 가동되도록 np.nan 실체로 수렴 바인딩합니다.
        if str(target_value).upper() in ["NAN", "NONE", "NULL"]:
            self._mask_value: float = np.nan
        else:
            self._mask_value = np.nan

    def refine(self, df: pd.DataFrame, mask: pd.DataFrame) -> pd.DataFrame:
        """주입된 이상치 마스크 좌표의 극단값들을 np.nan 결측치로 강제 변환 정제합니다.

        Args:
            df (pd.DataFrame): 전방 레이어에서 1차 보간이 수료되어 유입된 완결 상태의 가격 데이터프레임.
            mask (pd.DataFrame): df와 1:1 대칭 크기를 가지며, 이상치 좌표 정보가 명시된 불리언 마스크 데이터프레임.

        Returns:
            pd.DataFrame: 정상 데이터는 보존되고, 이상치 위치만 np.nan으로 공백화된 가격 데이터프레임.
        """
        # [설계 의도] 원본 주가 데이터프레임의 상태 불변성을 유지하고 사이드 이펙트를 완벽히 차단하기 위해,
        # 정제 연산 수행 전 메모리 상에 완전히 격리된 독립 카피본을 복성합니다.
        refined_df = df.copy()
        numeric_columns = df.select_dtypes(include=[np.number]).columns

        if not numeric_columns.empty:
            numeric_mask = mask[numeric_columns].astype(bool)
            refined_df.loc[:, numeric_columns] = refined_df[numeric_columns].mask(numeric_mask, np.nan)

        return refined_df