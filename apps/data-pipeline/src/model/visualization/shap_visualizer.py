import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.model.evaluation.shap_explainer import ShapExplanationResult


class ShapVisualizer:
    """SHAP XAI 분석 결과 시각화 전담 클래스."""

    @classmethod
    def plot_importance_and_dependence(
        cls,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        shap_result: ShapExplanationResult,
        top_n: int = 12
    ) -> plt.Figure:
        """
        글로벌 피처 중요도 Bar Plot과 1위 주도 팩터의 Dependence Scatter Plot을 2-Subplot Figure로 생성합니다.

        Args:
            X_train: 학습 세트 피처 행렬
            y_train: 학습 세트 타겟 시계열
            shap_result: ShapExplanationResult DTO
            top_n: 상위 출력 피처 수

        Returns:
            plt.Figure: 생성된 Figure 객체
        """
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        fig, axes = plt.subplots(1, 2, figsize=(20, 7))

        effective_top_n = min(top_n, len(shap_result.feature_names))
        top_features_df = shap_result.ranking_dataframe.head(effective_top_n).iloc[::-1]

        # 1. Global Feature Importance Bar Plot
        axes[0].barh(
            top_features_df["피처 명칭 (Feature Name)"],
            top_features_df["평균 절대 SHAP (Mean |SHAP|)"],
            color="#2b5c8f",
            alpha=0.85,
            edgecolor="black",
            linewidth=0.8
        )
        axes[0].set_title(f"Top {effective_top_n} Global Feature Importance (Mean |SHAP|)", fontsize=14, fontweight="bold", pad=12)
        axes[0].set_xlabel("Mean Absolute SHAP Value (Impact on |Return|)", fontsize=12)
        axes[0].grid(True, linestyle="--", alpha=0.6)

        # 2. Top 1 Feature SHAP Dependence Scatter Plot
        top_1_feature = shap_result.top_feature_name
        top_1_idx = shap_result.feature_names.index(top_1_feature)

        scatter = axes[1].scatter(
            X_train[top_1_feature],
            shap_result.shap_matrix[:, top_1_idx],
            c=y_train,
            cmap="coolwarm",
            alpha=0.85,
            edgecolors="black",
            linewidth=0.6,
            s=80
        )
        cbar = plt.colorbar(scatter, ax=axes[1])
        cbar.set_label("Actual Target Return (T+20)", fontsize=11)
        axes[1].axhline(0, color="gray", linestyle="--", linewidth=1.0)
        axes[1].set_title(f"SHAP Dependence: '{top_1_feature}'", fontsize=14, fontweight="bold", pad=12)
        axes[1].set_xlabel(f"Normalized Value: {top_1_feature}", fontsize=12)
        axes[1].set_ylabel(f"SHAP Value for {top_1_feature}", fontsize=12)
        axes[1].grid(True, linestyle="--", alpha=0.6)

        plt.tight_layout()
        return fig

    @classmethod
    def plot_factor_distribution(
        cls,
        X_train: pd.DataFrame,
        shap_result: ShapExplanationResult,
        champion_model_name: str,
        top_n: int = 12
    ) -> plt.Figure:
        """
        상위 팩터들의 SHAP 기여도 분포(Native Beeswarm 대체 플롯) Figure를 생성합니다.

        Args:
            X_train: 학습 세트 피처 행렬
            shap_result: ShapExplanationResult DTO
            champion_model_name: 대상 챔피언 모델 명칭
            top_n: 상위 출력 피처 수

        Returns:
            plt.Figure: 생성된 Figure 객체
        """
        fig, ax = plt.subplots(figsize=(14, 6))
        effective_top_n = min(top_n, len(shap_result.feature_names))

        top_feature_indices = [
            shap_result.feature_names.index(f)
            for f in shap_result.ranking_dataframe.head(effective_top_n)["피처 명칭 (Feature Name)"]
        ]
        top_feature_labels = list(shap_result.ranking_dataframe.head(effective_top_n)["피처 명칭 (Feature Name)"])

        for plot_idx, feat_idx in enumerate(top_feature_indices):
            feat_shap_vals = shap_result.shap_matrix[:, feat_idx]
            norm_feat_vals = X_train.iloc[:, feat_idx].values

            # [설계 의도] 0~1 정규화 컬러 매핑 (단일 고유값 피처의 0 나눗셈 방어)
            val_range = np.ptp(norm_feat_vals)
            colors = (norm_feat_vals - np.min(norm_feat_vals)) / (val_range if val_range > 0 else 1.0)

            # 점 중첩 완화를 위한 Jitter
            y_jitter = plot_idx + np.random.normal(0, 0.04, size=len(feat_shap_vals))
            ax.scatter(feat_shap_vals, y_jitter, c=colors, cmap="coolwarm", alpha=0.8, edgecolors="none", s=45)

        ax.set_yticks(range(effective_top_n))
        ax.set_yticklabels(top_feature_labels, fontsize=11)
        ax.axvline(0, color="red", linestyle="--", linewidth=1.2, alpha=0.7)
        ax.invert_yaxis()
        ax.set_title(f"SHAP Factor Contribution Distribution: Champion '{champion_model_name}'", fontsize=14, fontweight="bold", pad=15)
        ax.set_xlabel("SHAP Value (Impact on Prediction: < 0 Bearish | > 0 Bullish)", fontsize=12)
        ax.grid(True, linestyle="--", alpha=0.5)

        sm = plt.cm.ScalarMappable(cmap="coolwarm", norm=plt.Normalize(vmin=0, vmax=1))
        sm.set_array([])
        cbar_dist = fig.colorbar(sm, ax=ax, orientation="horizontal", pad=0.15, shrink=0.5)
        cbar_dist.set_label("Feature Value (Low: Blue ➔ High: Red)", fontsize=10)

        plt.tight_layout()
        return fig