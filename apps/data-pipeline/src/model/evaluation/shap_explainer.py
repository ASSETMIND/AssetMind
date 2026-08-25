from dataclasses import dataclass
from typing import Any, Dict, List
import numpy as np
import pandas as pd


@dataclass
class ShapExplanationResult:
    """SHAP XAI 분석 완료 산출물 및 기여도 랭킹 DTO."""

    shap_matrix: np.ndarray
    ranking_dataframe: pd.DataFrame
    top_feature_name: str
    feature_names: List[str]

    @property
    def display_dataframe(self) -> pd.DataFrame:
        """대시보드 출력용으로 소수점 및 백분율 포맷팅이 적용된 데이터프레임을 생성합니다."""
        # [설계 의도] 원본 수치 데이터를 보존하면서 UI 렌더링용 포맷팅 뷰(View) 제공
        display_dataframe = self.ranking_dataframe.copy()
        display_dataframe["평균 절대 SHAP (Mean |SHAP|)"] = display_dataframe["평균 절대 SHAP (Mean |SHAP|)"].map(lambda x: f"{x:.6f}")
        display_dataframe["기여도 비중 (Importance %)"] = display_dataframe["기여도 비중 (Importance %)"].map(lambda x: f"{x:.2f}%")
        return display_dataframe


class ShapExplainer:
    """SHAP 기반 정량적 거시 팩터 영향도 해석 전담 클래스."""

    def explain(
        self,
        model: Any,
        X_train: pd.DataFrame
    ) -> ShapExplanationResult:
        """
        모델의 calculate_shap_values 인터페이스를 호출하여 팩터 기여도 및 시장 방향성을 정량화합니다.

        Args:
            model: AbstractModel 규격을 준수하는 챔피언 회귀 모델 인스턴스
            X_train: 학습 세트 피처 행렬

        Returns:
            ShapExplanationResult: SHAP 행렬 및 팩터 랭킹 분석 결과 DTO
        """
        feature_names: List[str] = list(X_train.columns)

        # 1. 다형성 SHAP 인터페이스 호출 및 2차원 매트릭스 변환
        # [설계 의도] 트리/선형 모델 간 반환 타입(List, DataFrame, ndarray) 차이를 단일 2차원 numpy array로 정합성 보장
        raw_shap = model.calculate_shap_values(X_sample=X_train)
        if isinstance(raw_shap, list):
            shap_matrix: np.ndarray = np.array(raw_shap[0])
        elif hasattr(raw_shap, "values"):
            shap_matrix = raw_shap.values
        else:
            shap_matrix = np.array(raw_shap)

        # 2. 정량적 SHAP 피처 기여도 및 시장 편향(Market Bias) 판별
        mean_absolute_shap = np.mean(np.abs(shap_matrix), axis=0)
        total_shap_sum = np.sum(mean_absolute_shap)

        shap_importance_records: List[Dict[str, Any]] = []
        for index, feature_name in enumerate(feature_names):
            feature_values = X_train[feature_name].values
            std_val = np.std(feature_values)
            
            # [설계 의도] 피처값과 SHAP값 간의 피어슨 상관계수로 상승 견인(Bullish) vs 하락 압력(Bearish) 판정 (NaN 결측 안전 방어)
            if std_val > 0 and np.std(shap_matrix[:, index]) > 0:
                corr_val = np.corrcoef(feature_values, shap_matrix[:, index])[0, 1]
                correlation = 0.0 if np.isnan(corr_val) else float(corr_val)
            else:
                correlation = 0.0

            if correlation > 0.1:
                impact_direction = "상승 견인 (Bullish)"
            elif correlation < -0.1:
                impact_direction = "하락 압력 (Bearish)"
            else:
                impact_direction = "중립 / 비선형 (Neutral)"

            shap_importance_records.append({
                "피처 명칭 (Feature Name)": feature_name,
                "평균 절대 SHAP (Mean |SHAP|)": mean_absolute_shap[index],
                "기여도 비중 (Importance %)": (mean_absolute_shap[index] / total_shap_sum) * 100.0 if total_shap_sum > 0 else 0.0,
                "주요 기여 방향성 (Market Bias)": impact_direction
            })

        ranking_dataframe = pd.DataFrame(shap_importance_records).sort_values(
            by="평균 절대 SHAP (Mean |SHAP|)",
            ascending=False
        ).reset_index(drop=True)
        ranking_dataframe.index += 1
        ranking_dataframe.index.name = "Rank"

        top_feature_name: str = ranking_dataframe.iloc[0]["피처 명칭 (Feature Name)"]

        return ShapExplanationResult(
            shap_matrix=shap_matrix,
            ranking_dataframe=ranking_dataframe,
            top_feature_name=top_feature_name,
            feature_names=feature_names
        )