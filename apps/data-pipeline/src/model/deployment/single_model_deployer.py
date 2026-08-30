import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from src.model.evaluation.single_model_evaluator import ChampionModelDTO


@dataclass
class DeploymentVerificationResult:
    """챔피언 모델 역직렬화 및 추론 무결성 검증 결과 DTO."""

    artifact_path: str
    file_size_kb: float
    restored_model: Any
    single_sample_latency_ms: float
    final_test_metrics: Dict[str, float]
    feature_count: int


class SingleModelDeployer:
    """챔피언 모델의 프로덕션 직렬화 저장, 복원 검증 및 배포 명세서 사출기."""

    @classmethod
    def save(
        cls,
        model: Any,
        artifact_path: str = "champion_model.pkl"
    ) -> str:
        """
        챔피언 모델 인스턴스를 디스크 파일로 직렬화 저장합니다.

        Args:
            model: AbstractModel 규격을 준수하는 챔피언 회귀 모델 인스턴스
            artifact_path: 저장 대상 피클 파일 경로

        Returns:
            str: 저장 완료된 아티팩트 파일 경로
        """
        # [설계 의도] 모델 바이너리 디스크 직렬화 저장만 단독 수행 (단일 책임)
        model.save_artifact(artifact_path)
        file_size_kb = os.path.getsize(artifact_path) / 1024.0
        print(f"💾 [Artifact Saved] '{artifact_path}' (크기: {file_size_kb:.2f} KB)")
        return artifact_path

    @classmethod
    def verify(
        cls,
        champion_dto: ChampionModelDTO,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        artifact_path: str = "champion_model.pkl"
    ) -> DeploymentVerificationResult:
        """
        저장된 아티팩트를 역직렬화 로드하여 무결성, 예측값 재현성 및 단일 추론 레이턴시를 검증합니다.

        Args:
            champion_dto: 챔피언 모델 메타데이터 DTO
            X_test: 실전 검증용 Test 피처 행렬
            y_test: 실전 검증용 Test 타겟 시계열
            artifact_path: 검증 대상 피클 파일 경로

        Returns:
            DeploymentVerificationResult: 검증 지표 및 복원 모델 캡슐화 DTO

        Raises:
            FileNotFoundError: 아티팩트 파일이 디스크에 존재하지 않는 경우
            AssertionError: 모델 학습 상태, 피처 정합성, 예측 시계열이 일치하지 않는 경우
        """
        if not os.path.exists(artifact_path):
            raise FileNotFoundError(f"검증 대상 아티팩트 '{artifact_path}' 파일이 존재하지 않습니다.")

        file_size_kb = os.path.getsize(artifact_path) / 1024.0

        # 1. 동일 클래스의 새 빈 인스턴스 생성 후 로드
        restored_model = champion_dto.model.__class__()
        restored_model.load_artifact(artifact_path)

        # 2. 상태 복원 무결성 검증
        assert restored_model.is_fitted, "복원된 모델의 학습 상태(is_fitted)가 유효하지 않습니다."
        assert restored_model.feature_names == champion_dto.model.feature_names, "피처 리스트 정합성이 일치하지 않습니다."

        # 3. 원본 모델 vs 복원 모델 예측값 동일성(Identity) 및 레이턴시 측정
        original_predictions = champion_dto.model.predict(X_test=X_test)

        infer_start_time = time.perf_counter()
        restored_predictions = restored_model.predict(X_test=X_test)
        total_infer_latency_ms = (time.perf_counter() - infer_start_time) * 1000.0
        single_sample_latency_ms = total_infer_latency_ms / len(X_test) if len(X_test) > 0 else 0.0

        np.testing.assert_allclose(
            original_predictions.values,
            restored_predictions.values,
            rtol=1e-7,
            atol=1e-7,
            err_msg="원본 모델과 복원 모델의 예측 시계열이 일치하지 않습니다."
        )

        final_test_metrics = restored_model.evaluate(X_test=X_test, y_test=y_test)

        return DeploymentVerificationResult(
            artifact_path=artifact_path,
            file_size_kb=file_size_kb,
            restored_model=restored_model,
            single_sample_latency_ms=single_sample_latency_ms,
            final_test_metrics=final_test_metrics,
            feature_count=len(restored_model.feature_names)
        )

    @classmethod
    def summarize(
        cls,
        champion_dto: ChampionModelDTO,
        verification_result: DeploymentVerificationResult
    ) -> pd.DataFrame:
        """
        최종 챔피언 모델의 프로덕션 배포 사출서(Deployment Specification) 데이터프레임을 생성합니다.
        """
        # [설계 의도] DTO 계약에 따라 캡슐화된 최적 하이퍼파라미터 딕셔너리를 읽어 표준 Key=Value 문자열로 포맷팅
        if champion_dto.best_hyperparameters:
            formatted_items = []
            for key, value in champion_dto.best_hyperparameters.items():
                if isinstance(value, float):
                    formatted_items.append(f"{key}={value:.4f}")
                else:
                    formatted_items.append(f"{key}={value}")

            formatted_hyperparameters = ", ".join(formatted_items)
        else:
            formatted_hyperparameters = "Default Specification"

        # [설계 의도] 6대 평가 계층 기반 10대 다차원 지표 전수 정산 레코드 구축
        records: List[Dict[str, Any]] = [
            # 1. 모델 기본 메타데이터
            {"항목 (Field)": "챔피언 모델 알고리즘 (Algorithm)", "세부 내용 (Value)": champion_dto.name},
            {"항목 (Field)": "모델 아티팩트 경로 (Artifact Path)", "세부 내용 (Value)": verification_result.artifact_path},
            {"항목 (Field)": "아티팩트 파일 크기 (File Size)", "세부 내용 (Value)": f"{verification_result.file_size_kb:.2f} KB"},
            {"항목 (Field)": "최종 투입 피처 수 (Feature Dimension)", "세부 내용 (Value)": f"{verification_result.feature_count} Features"},
            {"항목 (Field)": "최적 하이퍼파라미터 (Best Parameters)", "세부 내용 (Value)": formatted_hyperparameters},
            
            # 2. HPO Walk-Forward CV 기초 성과
            {"항목 (Field)": "Walk-Forward CV 평균 적중률 (CV MDA)", "세부 내용 (Value)": f"{champion_dto.cv_mda * 100.0:.2f}%"},
            {"항목 (Field)": "Walk-Forward CV 평균 제곱근 오차 (CV RMSE)", "세부 내용 (Value)": f"{champion_dto.cv_rmse:.6f}"},
            
            # 3. Out-of-Sample Test 6대 평가 계층 10대 지표 전수
            {"항목 (Field)": "[L1] 테스트 방향성 적중률 (Test MDA)", "세부 내용 (Value)": f"{champion_dto.test_mda * 100.0:.2f}%"},
            {"항목 (Field)": "[L1] 테스트 평균 제곱근 오차 (Test RMSE)", "세부 내용 (Value)": f"{champion_dto.test_rmse:.6f}"},
            {"항목 (Field)": "[L1] 테스트 평균 절대 오차 (Test MAE)", "세부 내용 (Value)": f"{champion_dto.test_mae:.6f}"},
            {"항목 (Field)": "[L2] 테스트 순위 정보 계수 (Test Rank IC)", "세부 내용 (Value)": f"{champion_dto.test_rank_ic:.4f}"},
            {"항목 (Field)": "[L2] 테스트 팩터 정보 비율 (Test ICIR)", "세부 내용 (Value)": f"{champion_dto.test_icir:.2f}"},{"항목 (Field)": "[L3] 테스트 신호 샤프 지수 (Test Signal Sharpe)", "세부 내용 (Value)": f"{champion_dto.test_sharpe:.2f}"},
            {"항목 (Field)": "[L3] 테스트 소르티노 지수 (Test Sortino Ratio)", "세부 내용 (Value)": f"{champion_dto.test_sortino:.2f}"},
            {"항목 (Field)": "[L3] 테스트 최대 낙폭 (Test Max Drawdown)", "세부 내용 (Value)": f"{champion_dto.test_mdd * 100.0:.2f}%"},
            {"항목 (Field)": "[L4] 테스트 Newey-West 알파 통계량 (Factor t-stat)", "세부 내용 (Value)": f"{champion_dto.test_tstat:.2f} (p={champion_dto.test_pvalue:.4f})"},
            {"항목 (Field)": "[종합] 4대 계층 가중 복합 스코어 (Composite Score)", "세부 내용 (Value)": f"{champion_dto.composite_score:.4f}"},
            
            # 4. 프로덕션 서빙 SLA 및 배포 가드레일
            {"항목 (Field)": "[L6] 단일 추론 지연 시간 (Per-Sample Latency)", "세부 내용 (Value)": f"{verification_result.single_sample_latency_ms:.4f} ms"},
            {"항목 (Field)": "서빙 배포 적격 상태 (Production Readiness)", "세부 내용 (Value)": "VERIFIED & READY TO SERVE"}
        ]
        return pd.DataFrame(records).set_index("항목 (Field)")