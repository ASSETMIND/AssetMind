"""
전방 보간 레이어가 사출한 다중 국면 실험 버킷별 데이터프레임을 대상으로 통계적/머신러닝 기반 이상치 검출을 총괄 수행하는 최상위 마스터 진단 태스크

[전체 데이터 흐름 설명 (Input -> Output)]
1. Initialization: 상위 PreprocessorFactory로부터 하위 3대 알고리즘별 개별 하이퍼파라미터 인자 세트를 풀어서 분해 주입받아 내부 진단 엔진 레지스트리 빌드.
2. Input: 전방 보간 태스크(MissingValueImputation)의 단방향 연산 결과로 도출된 3대 보간 완료 pd.DataFrame 사전(Dict).
3. Processing:
   - 입력 데이터프레임 구조의 무결성 및 필수 국면 버킷 존재 여부 가드레일 검증 수행.
   - 3대 보간 국면 버킷을 Outer Loop로 순회하고, 레지스트리에 적재된 3대 이상치 진단 엔진(IQR, Z-Score, Isolation Forest)을 Inner Loop로 교차 호출.
   - 각 데이터 블록의 로컬 변동성 통계량을 바탕으로 차원 변형 없이 1:1 매칭되는 불리언 마스크 행렬(이상치는 True, 정상은 False) 계산.
   - 연산 수료 후 입력 행렬과 출력 마스크 행렬 간의 불변성(Invariant) 차원 정합성 검증 집행.
4. Output: 후행 정제 태스크(OutlierRefinement)가 다차원 실험 분기 처리를 즉시 기동할 수 있도록 다중 중첩 사전 구조의 진단 리포트(Dict) 사출.

주요 기능:
- [Discrete Parameter Injection] 통 config 객체 의존성을 제거하고 원자적 파라미터 주입을 실현하여 컴포넌트 간 결합도 원천 차단.
- [Cross-Combination Diagnostic Matrix] 3대 보간 버킷과 3대 탐지 알고리즘의 교차 조합 매트릭스를 빌드하여 다운스트림 실험 후보 우주(Universe) 극대화.
- [Look-Ahead Bias Short-Circuiting] 미래 통계량을 참조하지 않고 인풋으로 유입된 순수 룩백 윈도우 블록 내부 정보만으로 차원 격리 통계량 산출.
- [Invariant Defensive Validation] 연산 전후의 셰이프 및 인덱스 정합성을 엄격하게 강제하여 데이터 오염의 후방 전파 차단.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 모든 전처리(보간 x 탐지) 교차 실험 경로 일괄 사출 vs 설정 기반 단일 탐지 알고리즘 활성화 스위칭 운용:
  - 장점: 다운스트림 모델 계층의 다형성 그리드 서치(Grid Search) 및 하이퍼파라미터 조합 최적화 우주를 극대화하여 '데이터 기반 실증주의' 가치를 완벽히 구현함.
  - 단점: 다중 중첩 사전 구조(Nested Dictionary) 연산 및 동시 병렬 탐지로 인해 단기 인메모리(In-Memory) 점유율이 상승하고 서비스 레이어 내부의 오케스트레이션 제어 복잡도가 소폭 증가함.
  - 근거: 특정 금융 시계열 보간 국면 하에서 어떤 이상치 진단 모델(통계 vs ML)이 하위 모델군(선형, 트리, 딥러닝)의 가중치 왜곡 방어에 최적인지는 정량 실험 전까지 확정 불가함. 따라서 인프라의 미시적 연산 부하 비용보다 오염 자산 조기 차단 및 실험 신뢰도 확보에 따른 성능적 이득이 절대적으로 큼.
"""

from typing import Any, Dict
import pandas as pd

from src.common.exceptions import OutlierDiagnosisExecutionError
from src.preprocessor.tasks.outlier.iqr_diagnosis import IqrDiagnosis
from src.preprocessor.tasks.outlier.zscore_diagnosis import ZScoreDiagnosis
from src.preprocessor.tasks.outlier.isolation_forest_diagnosis import IsolationForestDiagnosis


# ==============================================================================
# Main Class
# ==============================================================================
class OutlierDiagnosis:
    """다중 전방 보간 버킷을 입력받아 3대 알고리즘 교차 연산을 수행하고 중첩 사전 구조의 진단 마스크 리포트를 발행하는 마스터 태스크 클래스."""

    def __init__(
        self,
        iqr_params: Dict[str, Any],
        zscore_params: Dict[str, Any],
        isolation_forest_params: Dict[str, Any]
    ) -> None:
        """하위 이상치 진단 수리 엔진들을 생성하고 주입된 개별 파라미터 세트를 사전 캡슐화 바인딩합니다.

        Args:
            iqr_params (Dict[str, Any]): 사분위수 기반 탐지 엔진(multiplier 등)용 하이퍼파라미터 사전.
            zscore_params (Dict[str, Any]): 정규분포 변동성 탐지 엔진(threshold 등)용 하이퍼파라미터 사전.
            isolation_forest_params (Dict[str, Any]): 다변량 머신러닝 탐지 엔진(contamination, random_state 등)용 하이퍼파라미터 사전.
        """
        # [설계 의도] 하위 엔진 컴포넌트들이 외부 설정 스키마의 물리적 구조에 종속되는 문제를 방어하기 위해,
        # 풀어진 파라미터 사전을 각 구체 클래스 생성자 레벨에 직통 분해 주입(Composite Pattern)하여 격리합니다.
        self._diagnosis_registry: Dict[str, Any] = {
            "iqr": IqrDiagnosis(**iqr_params),
            "zscore": ZScoreDiagnosis(**zscore_params),
            "isolation_forest": IsolationForestDiagnosis(**isolation_forest_params)
        }

    def execute(self, imputation_artifacts: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, pd.DataFrame]]:
        """전방 보간 버킷 프레임들을 교차 분석하여 이상치 위치 좌표를 명시한 불리언 마스크 리포트를 발행합니다.

        Args:
            imputation_artifacts (Dict[str, pd.DataFrame]): MissingValueImputation 태스크가 사출한 
                3대 단기 보간 완료 데이터프레임 버킷(bucket_locf, bucket_log_return, bucket_moving_average).

        Returns:
            Dict[str, Dict[str, pd.DataFrame]]: 보간 버킷 키와 탐지 알고리즘 키가 2중 중첩 매핑된 
                최종 불리언 마스크 데이터프레임 패키지 구조체.

        Raises:
            OutlierDiagnosisExecutionError: 하위 넘파이/사이킷런 연산 장애, 특이 행렬 패닉, 또는 
                입출력 데이터프레임 구조 붕괴 상황 포착 시 최상위 오케스트레이터 감지를 위해 강제 전파.
        """
        # [설계 의도] 인풋 데이터가 내부 시퀀스 루프에 유입되어 가짜 섀이프로 전체 통계량을 파괴하는 현상을 막기 위해,
        # 함수 진입점에서 비즈니스 규칙 및 인자 정합성을 Fail-Fast 규격으로 선제 가드레일 검증합니다.
        self._validate_inputs(imputation_artifacts)

        try:
            outlier_diagnosis_report: Dict[str, Dict[str, pd.DataFrame]] = {}
            target_buckets = ["bucket_locf", "bucket_log_return", "bucket_moving_average"]

            # [설계 의도] 어떤 보간 국면과 어떤 이상치 탐지 통계 알고리즘의 결합이 하위 예측 모델의 손실 함수 수렴에
            # 최적인지 실증하기 위해, 단일 선택 처리를 배제하고 모든 교차 실험 우주(Universe)를 병렬 분기 연산 적재합니다.
            for bucket_key in target_buckets:
                current_df = imputation_artifacts[bucket_key]
                outlier_diagnosis_report[bucket_key] = {}

                for engine_key, diagnostic_engine in self._diagnosis_registry.items():
                    # 각 구체 진단 엔진에 연산을 위임하여 1:1 대칭 크기의 pd.DataFrame(Boolean Metric) 형성
                    boolean_mask = diagnostic_engine.detect(current_df)
                    outlier_diagnosis_report[bucket_key][engine_key] = boolean_mask

            # [설계 의도] 루프 연산 도중 판다스 내부 정렬 축 뒤틀림이나 유실로 인해 다운스트림 텐서 모양이 붕괴되는 리스크를
            # 영구 박멸하기 위해, 데이터 사출 직전 인아웃 매트릭스의 물리적 불변성(Invariant) 검증 가동을 강제합니다.
            self._validate_invariants(imputation_artifacts, outlier_diagnosis_report)

            return outlier_diagnosis_report

        except Exception as original_error:
            raise OutlierDiagnosisExecutionError(
                message="이상치 다중 매트릭스 실험 교차 진단(Outlier Cross-Diagnosis Loop) 연산 중 치명적 런타임 오류가 발생했습니다.",
                strategy_type="CROSS_COMBINATION_ORCHESTRATOR",
                original_exception=original_error
            )

    def _validate_inputs(self, imputation_artifacts: Dict[str, pd.DataFrame]) -> None:
        """입력 컨텍스트 사전의 객체 타입 및 필수 보간 버킷 키 상주 여부를 엄격하게 가드레일 검증합니다."""
        if not isinstance(imputation_artifacts, dict):
            raise OutlierDiagnosisExecutionError(
                message="진단 태스크로 주입된 아티팩트 버킷이 유효한 Python Dict 구조가 아닙니다.",
                strategy_type=self.__class__.__name__
            )

        required_keys = ["bucket_locf", "bucket_log_return", "bucket_moving_average"]
        for key in required_keys:
            if key not in imputation_artifacts or not isinstance(imputation_artifacts[key], pd.DataFrame):
                raise OutlierDiagnosisExecutionError(
                    message=f"이상치 진단을 위한 필수 전방 보간 완료 데이터프레임 버킷인 '{key}' 요소를 파싱할 수 없습니다.",
                    strategy_type=self.__class__.__name__
                )

    def _validate_invariants(
        self, 
        imputation_artifacts: Dict[str, pd.DataFrame], 
        report: Dict[str, Dict[str, pd.DataFrame]]
    ) -> None:
        """연산 전후 데이터프레임의 인덱스, 컬럼 셰이프 및 불리언 타입의 완벽한 1:1 대칭 정합성을 검증합니다."""
        for bucket_key, engines in report.items():
            orig_df = imputation_artifacts[bucket_key]
            for engine_key, mask_df in engines.items():
                
                # 차원 불변 조건 충족성 검사 (행과 열의 크기가 원본과 소수점 1자리의 오차도 없이 일치해야 함)
                if orig_df.shape != mask_df.shape:
                    raise OutlierDiagnosisExecutionError(
                        message=f"불변성 파괴 감지: 버킷 [{bucket_key}] 내 엔진 [{engine_key}]의 출력 마스크 셰이프{mask_df.shape}가 원본{orig_df.shape}과 불일치합니다.",
                        strategy_type=engine_key
                    )
                
                # 인덱스 및 컬럼 명칭 정렬축 보존 유무 조밀 정밀 검사
                if not orig_df.index.equals(mask_df.index) or not orig_df.columns.equals(mask_df.columns):
                    raise OutlierDiagnosisExecutionError(
                        message=f"불변성 파괴 감지: 버킷 [{bucket_key}] 내 엔진 [{engine_key}]의 시계열 타임스탬프 인덱스 또는 자산코드가 원본 축과 뒤틀려 있습니다.",
                        strategy_type=engine_key
                    )