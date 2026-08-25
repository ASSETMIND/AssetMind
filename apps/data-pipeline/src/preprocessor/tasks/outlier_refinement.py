"""
이상치 진단 리포트의 불리언 마스크를 해독하여 1차 보간 완료 행렬의 극단값 좌표를 통계적/알고리즘적 정책에 따라 일괄 정제하는 최상위 마스터 정제 태스크

[전체 데이터 흐름 설명 (Input -> Output)]
1. Initialization: 상위 PreprocessorFactory로부터 정제 엔진 제어용 개별 하이퍼파라미터 인자 세트를 풀어서 주입받아 내부 정제 레지스트리 빌드.
2. Input: 전방 보간 태스크의 아티팩트 사전(imputation_artifacts) 및 이상치 진단 태스크의 2중 중첩 마스크 리포트(diagnosis_report).
3. Processing:
   - 입력 구조체들의 무결성 및 필수 분기 요소 상주 여부를 함수 진입점에서 Fail-Fast 가드레일 검증.
   - 3대 보간 기법, 3대 탐지 알고리즘, 2대 정제 정책(Clipping, Masking)을 관통하는 3중 연쇄 루프(Triple Loop) 가동.
   - 각 하위 정제 구체 엔진(ClippingRefinement, MaskingRefinement)에 수리 연산을 위임하여 차원 파괴 없이 값의 제어 수행.
   - 연산 종료 후 최종 생성된 18개 매트릭스를 대상으로 원본 인풋 프레임과의 차원 불변성(Invariant) 정밀 검증 집행.
4. Output: 하위 다형성 모델군이 교차 조합 실험을 즉시 수행할 수 있도록 고유 스트링 키로 정렬된 18대 청정 버킷 사전(Dict) 사출.

주요 기능:
- [Discrete Parameter Injection] 외부 config 객체에 통째로 의존하지 않고 결합도가 완전히 거세된 개별 파라미터 사전 주입 체계 확립.
- [18-Way Cross Combination Framework] 3대 보간 x 3대 탐지 x 2대 정제 조합을 단일 플랫 딕셔너리로 캡슐화하여 사출하는 실험 최적화 인프라 수립.
- [Look-Ahead Bias Defense Guard] 정제 연산 내부에서 미래 시점의 통계량을 절대 참조하지 않고 지정된 로컬 마스크 좌표계 내에서만 인과적 치환을 집행.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 3중 루프를 통한 18대 다형성 실험 버킷 일괄 생성 vs 설정 기반 단일 정제 본만 선택 사출:
  - 장점: 전처리 전방 파이프라인 레이어에서 파생 가능한 모든 데이터 정제 국면을 단 한 번의 배치 기동으로 하위 모델 레이어에 동시 공급하므로, 머신러닝/딥러닝 모델별 최적의 전처리 정답 조합을 찾아내는 정량적 비교 실험의 완전성을 보장함.
  - 단점: 18개의 데이터프레임 카피본이 일시적으로 메모리에 상주하므로 로컬 CPU 힙(Heap) 메모리 점유율이 단기적으로 급상승함.
  - 근거: 본 프로젝트는 190종 대규모 금융 시계열을 다루며 다운스트림에 Ridge, XGBoost, LSTM 앙상블을 대기시키고 있음. 모델별로 전처리 민감도가 완전히 다르므로, 미시적인 메모리 점유 비용을 치르더라도 데이터 기반 실증주의 가치를 극대화하여 취업 시장에서 전처리 엔지니어링 깊이를 강력히 증명하는 것이 압도적으로 이득임.
"""

from typing import Any, Dict
import pandas as pd

from src.common.exceptions import OutlierRefinementExecutionError
from src.preprocessor.tasks.outlier.clipping_refinement import ClippingRefinement
from src.preprocessor.tasks.outlier.masking_refinement import MaskingRefinement


# ==============================================================================
# Main Class
# ==============================================================================
class OutlierRefinement:
    """이상치 진단 마스크 서사를 해독하여 18대 실험 경로 데이터프레임 버킷을 일괄 정제 분기하는 오케스트레이터 태스크 클래스."""

    def __init__(
        self,
        clipping_params: Dict[str, Any],
        algorithmic_masking_params: Dict[str, Any]
    ) -> None:
        """하위 이상치 정제 수리 엔진들을 생성하고 주입된 독립 하이퍼파라미터 세트를 바인딩합니다.

        Args:
            clipping_params (Dict[str, Any]): 통계적 상하한 조정 엔진(multiplier 등)용 파라미터 사전.
            algorithmic_masking_params (Dict[str, Any]): Two-Pass 결측치 치환 엔진(target_value 등)용 파라미터 사전.
        """
        # [설계 의도] 단면 중립화(Neutralization) 기법은 원시 가격(Raw Price) 분포의 시계열 자산 경로를 
        # 심각하게 파괴하는 도메인 부작용이 크므로 과감히 척결하고, 명분이 확실한 2대 정제 엔진 레지스트리만 구축합니다.
        self._refinement_registry: Dict[str, Any] = {
            "clipping": ClippingRefinement(**clipping_params),
            "masking": MaskingRefinement(**algorithmic_masking_params)
        }

    def execute(
        self, 
        imputation_artifacts: Dict[str, pd.DataFrame], 
        diagnosis_report: Dict[str, Dict[str, pd.DataFrame]]
    ) -> Dict[str, pd.DataFrame]:
        """보간 버킷과 진단 마스크의 모든 실험 경로 우주를 조합 순회하여 18개의 최종 정제 데이터 버킷 사전을 형성합니다.

        Args:
            imputation_artifacts (Dict[str, pd.DataFrame]): MissingValueImputation 태스크가 사출한 
                3대 단기 보간 완료 데이터프레임 사전.
            diagnosis_report (Dict[str, Dict[str, pd.DataFrame]]): OutlierDiagnosis 태스크가 발행한 
                2중 중첩 구조의 이상치 불리언 마스크 리포트 사전.

        Returns:
            Dict[str, pd.DataFrame]: 'bucket_impute_[보간기법]_detect_[탐지기법]_refine_[정제정책]' 규격의 
                고유 키 명칭으로 패키징된 총 18개의 최종 청정 데이터프레임 사전 버킷 버퍼.

        Raises:
            OutlierRefinementExecutionError: 주입 인자 누락, 판다스 행렬 매칭 파괴, 또는 
                연산 전후 차원 불변성 붕괴 상황 감지 시 상위 서비스 레이어로의 Fail-Fast 전파를 위해 강제 전파.
        """
        # 함수 진입점 아티팩트들의 타입 무결성 및 계약 충족 여부 선제 가드레일 검증
        self._validate_inputs(imputation_artifacts, diagnosis_report)

        try:
            outlier_refinement_artifacts: Dict[str, pd.DataFrame] = {}
            
            target_imputations = ["bucket_locf", "bucket_log_return", "bucket_moving_average"]
            target_diagnoses = ["iqr", "zscore", "isolation_forest"]

            # [설계 의도] 보간(3종) x 탐지(3종) x 정제(2종) 경로가 결착되는 3중 연쇄 오케스트레이션 루프를 운용하여
            # 총 18개의 병렬 실험 매트릭스 우주를 빌드합니다.
            for impute_key in target_imputations:
                current_price_df = imputation_artifacts[impute_key]
                # 고유 명명 스키마 형성을 위해 'bucket_locf' -> 'locf' 문자열 축약 추출
                impute_name = impute_key.replace("bucket_", "")

                for detect_key in target_diagnoses:
                    current_mask_df = diagnosis_report[impute_key][detect_key]

                    for refine_key, refinement_engine in self._refinement_registry.items():
                        # 최하위 구체 수리 엔진에 정제 책임을 고도로 격리 위임
                        refined_df = refinement_engine.refine(current_price_df, current_mask_df)
                        
                        # 아키텍처 표준 키 명명 계약 명세 매핑 집행
                        artifact_key = f"bucket_impute_{impute_name}_detect_{detect_key}_refine_{refine_key}"
                        outlier_refinement_artifacts[artifact_key] = refined_df

            # [설계 의도] 사출 직전 18개 결과물 전수의 물리 구조를 원본 데이터와 1:1 대조함으로써, 
            # 하위 벡터 연산 레이어에서 발생했을 수 있는 셰이프 파괴나 시계열 축 뒤틀림 리스크를 완벽히 격리 차단합니다.
            self._validate_invariants(imputation_artifacts["bucket_locf"], outlier_refinement_artifacts)

            return outlier_refinement_artifacts

        except Exception as original_error:
            # 내부 수리 파닉 및 인덱스 미스매치 포착 시 구조화된 커스텀 예외 체인 봉인
            raise OutlierRefinementExecutionError(
                message="이상치 다차원 매트릭스 실험 교차 정제(Outlier Triple-Refinement Loop) 연산 중 치명적 오류가 발생했습니다.",
                strategy_type="18_WAY_CROSS_COMBINATION_ORCHESTRATOR",
                original_exception=original_error
            )

    def _validate_inputs(
        self, 
        imputation_artifacts: Dict[str, pd.DataFrame], 
        diagnosis_report: Dict[str, Dict[str, pd.DataFrame]]
    ) -> None:
        """입력 컨텍스트 사전들의 자료구조 타입 및 필수 수리 분기 키의 상주 여부를 엄격하게 가드레일 검증합니다."""
        if not isinstance(imputation_artifacts, dict) or not isinstance(diagnosis_report, dict):
            raise OutlierRefinementExecutionError(
                message="정제 태스크로 주입된 아티팩트 구조들이 유효한 Python Dict 형태가 아닙니다."
            )

        required_buckets = ["bucket_locf", "bucket_log_return", "bucket_moving_average"]
        for bucket_key in required_buckets:
            if bucket_key not in imputation_artifacts or not isinstance(imputation_artifacts[bucket_key], pd.DataFrame):
                raise OutlierRefinementExecutionError(
                    message=f"이상치 정제를 위한 필수 전방 보간 버킷 프레임인 '{bucket_key}' 요소가 손상되었거나 누락되었습니다."
                )
            if bucket_key not in diagnosis_report:
                raise OutlierRefinementExecutionError(
                    message=f"이상치 정제를 위한 필수 진단 리포트 대칭 그룹인 '{bucket_key}' 세트가 누락되었습니다."
                )

    def _validate_invariants(self, sample_df: pd.DataFrame, final_artifacts: Dict[str, pd.DataFrame]) -> None:
        """최종 빌드된 18개 실험 버킷 데이터프레임 전수의 행렬 차원, 타임스탬프 인덱스 및 자산코드 컬럼축 일치 불변성을 검증합니다."""
        # 아키텍처 가드레일: 사출된 최종 버킷 본수가 비즈니스 명세 계약(18개)과 정확히 일치하는지 지엄하게 검동
        if len(final_artifacts) != 18:
            raise OutlierRefinementExecutionError(
                message=f"불변성 파괴 감지: 사출된 최종 실험 데이터프레임의 총 본수({len(final_artifacts)}개)가 아키텍처 계약 본수(18개)와 불합치합니다."
            )

        for artifact_key, refined_df in final_artifacts.items():
            # 차원 불변 조건 충족성 검사 (하위 텐서 셰이프 일치성의 마스터 방어벽)
            if sample_df.shape != refined_df.shape:
                raise OutlierRefinementExecutionError(
                    message=f"불변성 파괴 감지: 최종 청정 버킷 [{artifact_key}]의 차원 셰이프{refined_df.shape}가 원본{sample_df.shape}과 불일치하여 하위 텐서 연산 붕괴 리스크가 포착되었습니다."
                )
            
            # 시계열 인덱스 및 자산 코드 정렬축 보존 상태 정밀 조밀 대조
            if not sample_df.index.equals(refined_df.index) or not sample_df.columns.equals(refined_df.columns):
                raise OutlierRefinementExecutionError(
                    message=f"불변성 파괴 감지: 최종 청정 버킷 [{artifact_key}]의 타임스탬프 인덱스 축 또는 자산코드 정렬 순서가 원본 축과 뒤틀려 데이터 누수 위험이 있습니다."
                )