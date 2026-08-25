import datetime
import logging
import os
from typing import Any, Dict, List, Optional
import matplotlib.pyplot as plt
import pandas as pd
import mlflow
from mlflow.tracking import MlflowClient

# [MLflow 콘솔 URL 링크 전역 완벽 차단]
logging.disable(logging.INFO)

# MLflow 내부 로거 및 핸들러 일괄 무음화
for logger_name in list(logging.root.manager.loggerDict.keys()):
    if "mlflow" in logger_name:
        target_logger = logging.getLogger(logger_name)
        target_logger.setLevel(logging.ERROR)
        target_logger.handlers.clear()
        target_logger.propagate = False


class MLflowTracker:
    """AssetMind 모델링 실험 및 아티팩트를 관리하는 MLflow 전용 추적기 클래스."""

    def __init__(self, experiment_name: str = "02_Single_Model_FineTuning") -> None:
        """
        추적기를 초기화하고 MLflow 실험 네임스페이스를 바인딩합니다.

        Args:
            experiment_name: 대상 MLflow Experiment 명칭
        """
        self.experiment_name: str = experiment_name
        self.tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        mlflow.set_tracking_uri(self.tracking_uri)
        
        self.client: MlflowClient = MlflowClient()
        self._ensure_active_experiment()
        
        # 모델명 -> run_id 매핑 레지스트리
        self.run_id_map: Dict[str, str] = {}

    def _ensure_active_experiment(self) -> None:
        """실험이 소프트 삭제 상태인 경우 자동 복구 후 활성화합니다."""
        existing_experiment = self.client.get_experiment_by_name(self.experiment_name)
        if existing_experiment is not None and existing_experiment.lifecycle_stage == "deleted":
            self.client.restore_experiment(existing_experiment.experiment_id)
        
        mlflow.set_experiment(self.experiment_name)
        active_exp = mlflow.get_experiment_by_name(self.experiment_name)
        print(f"🎯 [MLflow Tracker Active] Experiment: '{self.experiment_name}' (ID: {active_exp.experiment_id})")

    def start_hpo_run(self, model_name: str) -> str:
        """
        단일 모델 HPO용 독립 Run을 생성하고 Run ID를 반환합니다.

        Args:
            model_name: 모델 알고리즘 명칭 (예: ElasticNet, XGBoost)
        """
        with mlflow.start_run(run_name=f"HPO_{model_name}") as run:
            run_id: str = run.info.run_id
            self.run_id_map[model_name] = run_id
            mlflow.set_tag("algorithm", model_name)
            return run_id

    def log_hpo_result(
        self,
        model_name: str,
        result_dto: Any,
        fig: Optional[Any] = None
    ) -> str:
        """
        단일 회귀 모델의 HPO 결과(최적 파라미터, CV 지표, 수렴 시각화)를 신규 독립 Run으로 영속화하고,
        후속 파이프라인(평가, XAI, 배포) 연동을 위해 run_id_map을 최신화합니다.
        """
        current_time_str = datetime.datetime.now().strftime("%m%d_%H%M%S")
        run_name = f"HPO_{model_name}_{current_time_str}"

        # [설계 의도] 매 HPO 시도마다 고유 Run을 생성하여 파라미터 덮어쓰기 에러 원천 차단
        with mlflow.start_run(run_name=run_name) as active_run:
            active_run_id = active_run.info.run_id
            
            # [핵심] 최신 run_id를 레지스트리에 갱신하여 Cell 3, 4, 5와의 참조 정합성 보장
            self.run_id_map[model_name] = active_run_id

            # 1. 태그 설정 (모델 계열 및 실험 단계)
            mlflow.set_tag("algorithm", model_name)
            mlflow.set_tag("model_family", model_name)
            mlflow.set_tag("pipeline_stage", "Stage 2 - Single Model HPO")

            # 2. 최적 파라미터 및 탐색 메타데이터 로깅
            if result_dto.best_hyperparameters:
                mlflow.log_params(result_dto.best_hyperparameters)
            mlflow.log_param("trials_executed", result_dto.trials_executed)
            mlflow.log_param("search_time_seconds", round(result_dto.total_search_time_seconds, 2))

            # 3. 교차검증(CV) 성능 지표 로깅
            cv_metrics = getattr(result_dto, "tuned_cross_validation_metrics", {})
            if isinstance(cv_metrics, dict):
                if "mean_mda" in cv_metrics:
                    mlflow.log_metric("cv_mean_mda", cv_metrics["mean_mda"])
                if "mean_rmse" in cv_metrics:
                    mlflow.log_metric("cv_mean_rmse", cv_metrics["mean_rmse"])
                if "mean_mae" in cv_metrics:
                    mlflow.log_metric("cv_mean_mae", cv_metrics["mean_mae"])

            # Optuna 최적 목적함수 점수(Best Objective Value) 안전 로깅
            study_obj = getattr(result_dto, "study", None)
            if study_obj is not None and hasattr(study_obj, "best_value"):
                mlflow.log_metric("hpo_best_score", float(study_obj.best_value))

            # 4. 수렴 궤적 시각화 아티팩트 영속화
            if fig is not None:
                mlflow.log_figure(fig, artifact_file=f"figures/{model_name}_hpo_convergence.png")

            return active_run_id

    def log_test_evaluation(
        self,
        model_name: str,
        test_metrics: Dict[str, float],
        latency_ms: float,
        cv_mda_delta: float,
        cv_rmse_delta: float
    ) -> None:
        """Holdout Test 세트 평가 지표와 튜닝 개선폭(Delta)을 로깅합니다."""
        run_id = self.run_id_map.get(model_name)
        if run_id:
            with mlflow.start_run(run_id=run_id):
                mlflow.log_metrics({
                    "test_mda": test_metrics["MDA"],
                    "test_rmse": test_metrics["RMSE"],
                    "test_mae": test_metrics["MAE"],
                    "test_latency_ms": latency_ms,
                    "cv_mda_delta": cv_mda_delta,
                    "cv_rmse_delta": cv_rmse_delta
                })

    def log_benchmark_and_champion(
        self,
        ranked_dataframe: pd.DataFrame,
        champion_model_name: str,
        summary_dataframe: pd.DataFrame
    ) -> None:
        """전체 모델의 랭킹 및 Champion/Challenger 태그를 지정하고 비교표 CSV를 저장합니다."""
        # 1. 태깅 일괄 갱신
        for rank_idx, row in ranked_dataframe.iterrows():
            m_name = row["알고리즘 (Algorithm)"]
            run_id = self.run_id_map.get(m_name)
            if run_id:
                with mlflow.start_run(run_id=run_id):
                    is_champ = (m_name == champion_model_name)
                    mlflow.set_tags({
                        "model_rank": rank_idx + 1,
                        "is_champion": str(is_champ),
                        "model_tier": "champion" if is_champ else "challenger"
                    })

        # 2. 1위 Champion Run에 비교 정산표 CSV 저장
        champ_run_id = self.run_id_map.get(champion_model_name)
        if champ_run_id:
            with mlflow.start_run(run_id=champ_run_id):
                csv_path = "model_benchmark_comparison.csv"
                summary_dataframe.to_csv(csv_path, index=False, encoding="utf-8-sig")
                mlflow.log_artifact(csv_path, artifact_path="reports")
                if os.path.exists(csv_path):
                    os.remove(csv_path)

    def log_xai_reports(
        self,
        champion_model_name: str,
        shap_ranking_dataframe: pd.DataFrame,
        fig_importance: plt.Figure,
        fig_distribution: plt.Figure,
        top_driver_feature: str
    ) -> None:
        """SHAP XAI 플롯 이미지들과 팩터 기여도 CSV를 Champion Run의 xai/ 폴더에 적재합니다."""
        champ_run_id = self.run_id_map.get(champion_model_name)
        if champ_run_id:
            with mlflow.start_run(run_id=champ_run_id):
                # 1. 차트 이미지 로깅
                mlflow.log_figure(fig_importance, artifact_file="xai/shap_importance_dependence.png")
                mlflow.log_figure(fig_distribution, artifact_file="xai/shap_factor_distribution.png")
                
                # 2. 정산 CSV 저장
                csv_path = "shap_feature_importance_ranking.csv"
                shap_ranking_dataframe.to_csv(csv_path, index=True, encoding="utf-8-sig")
                mlflow.log_artifact(csv_path, artifact_path="xai")
                if os.path.exists(csv_path):
                    os.remove(csv_path)
                
                # 3. Top Factor 태그
                mlflow.set_tag("top_shap_feature", top_driver_feature)

    def register_champion_model(
        self,
        champion_model_name: str,
        artifact_path: str,
        deployment_summary_dataframe: pd.DataFrame,
        single_sample_latency_ms: float,
        registry_model_name: str = "Champion_AssetMind_Regressor"
    ) -> None:
        """모델 바이너리를 MinIO에 저장하고, MLflow Model Registry에 공식 등록합니다."""
        champ_run_id = self.run_id_map.get(champion_model_name)
        if champ_run_id:
            with mlflow.start_run(run_id=champ_run_id):
                # 1. 모델 가중치 아티팩트 업로드
                mlflow.log_artifact(artifact_path, artifact_path="model")
                
                # 2. 배포 명세서 CSV 및 메트릭 기록
                report_path = "champion_model_deployment_spec.csv"
                deployment_summary_dataframe.to_csv(report_path, index=True, encoding="utf-8-sig")
                mlflow.log_artifact(report_path, artifact_path="reports")
                if os.path.exists(report_path):
                    os.remove(report_path)

                mlflow.set_tag("serving_status", "READY_TO_SERVE")
                mlflow.log_metric("single_sample_latency_ms", single_sample_latency_ms)

                # 3. Model Registry 공식 버전 등록 (404 Search 엔드포인트 우회 및 Client 직접 등록)
                try:
                    # [설계 의도] 1단계: 모델 컨테이너 존재 여부 확인 및 생성 (기존 등록 시 예외 안전 무시)
                    try:
                        self.client.create_registered_model(name=registry_model_name)
                    except Exception:
                        pass

                    # [설계 의도] 2단계: 표준 아티팩트 소스 URI 기반 정식 신규 버전 발급
                    source_uri: str = f"runs:/{champ_run_id}/model"
                    model_version = self.client.create_model_version(
                        name=registry_model_name,
                        source=source_uri,
                        run_id=champ_run_id
                    )
                    print(f"🎯 [MLflow Model Registry] '{registry_model_name}' (Version: {model_version.version}) 정식 승격 완료")
                except Exception as ex:
                    # [설계 의도] Registry 서비스 장애 시에도 전체 파이프라인 중단을 방어하는 Fail-Safe 로깅
                    print(f"⚠️ [MLflow Model Registry] 등록 우회 처리: {ex}")