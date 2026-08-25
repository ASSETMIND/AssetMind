import matplotlib.pyplot as plt
import numpy as np
import optuna


class OptimizerVisualizer:
    """옵티마이저 탐색 이력 및 파라미터 영향도 시각화 전담 클래스."""

    @classmethod
    def plot_convergence(
        cls,
        study: optuna.Study,
        model_name: str
    ) -> plt.Figure:
        """
        Optuna 최적화 수렴 궤적(Convergence)과 fANOVA 중요도 플롯을 2-Subplot Figure로 생성합니다.

        Args:
            study: 최적화가 완료된 Optuna Study 객체
            model_name: 모델 알고리즘 명칭

        Returns:
            plt.Figure: 생성된 Matplotlib Figure 객체
        """
        fig, axes = plt.subplots(1, 2, figsize=(16, 4.5))

        # 1. 수렴 이력 플롯 (Optimization History)
        trials = study.trials
        trial_numbers = [t.number + 1 for t in trials if t.value is not None]
        trial_values = [t.value for t in trials if t.value is not None]

        if trial_values:
            best_values = np.maximum.accumulate(trial_values)
            axes[0].plot(
                trial_numbers, trial_values,
                marker="o", linestyle="none", color="#4A90E2", alpha=0.6, label="Trial Score"
            )
            axes[0].plot(
                trial_numbers, best_values,
                linestyle="-", color="#D0021B", linewidth=2.0, label="Best Score"
            )
            axes[0].legend(loc="lower right", fontsize=8)

        axes[0].set_title(f"[{model_name}] Optimization Convergence History", fontsize=11, fontweight="bold")
        axes[0].set_xlabel("Trial Number", fontsize=9)
        axes[0].set_ylabel("Composite Score", fontsize=9)
        axes[0].grid(True, linestyle="--", alpha=0.5)

        # 2. 파라미터 중요도 플롯 (Hyperparameter Importances via fANOVA)
        try:
            importances = optuna.importance.get_param_importances(study)
            param_names = list(importances.keys())[::-1]
            param_scores = list(importances.values())[::-1]

            axes[1].barh(param_names, param_scores, color="#50E3C2", edgecolor="#333333", alpha=0.85)
            axes[1].set_title(f"[{model_name}] Hyperparameter Importance (fANOVA)", fontsize=11, fontweight="bold")
            axes[1].set_xlabel("Importance Ratio", fontsize=9)
            axes[1].grid(True, linestyle="--", alpha=0.5)
        except Exception:
            axes[1].text(0.5, 0.5, "Importance calculation requires more trials", ha="center", va="center")
            axes[1].set_axis_off()

        plt.tight_layout()
        return fig