"""
[PreprocessorService]

[상위 파이프라인 레이어의 단일 진입점으로서 팩토리가 일괄 생성한 전처리 태스크 체인의 데이터 흐름과 다형성 요약을 통합 제어하는 서비스 계층]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 상위 파이프라인 컨트롤러로부터 매개변수 주입 없이 원본 금융 시계열 데이터프레임(market_data)만 유입.
2. Build Chain Request: 내부 팩토리의 `create_preprocessor()`를 매개변수 없이 기동하여 yml 설정 기반으로 정렬된 구체 태스크 인스턴스 리스트 일괄 수신.
3. Pipe Execution Loop: 중앙 횡단 관심사 로깅 데코레이터 하에서 태스크 리스트를 순회하며 데이터프레임과 진단 메타데이터를 상호 피드백 피파이프라이닝 처리하고 이질적 metrics 요약본을 누적 적재.
4. Output: 하위 벡터 연산 가드레일 예외를 Fail-Fast로 관리하며 최종 정제와 통계적 마스킹 계량이 완벽히 수료된 마스터 결과 프레임워크 반환.

주요 기능:
- Param-Free Pipeline Entry (execute_preprocessing_job): 서비스 진입점 파라미터에서 job_id를 완벽히 척결하여 상위 호출자의 전처리 비즈니스 종속성을 원천 제로화함.
- Sequential Pipeline Context Orchestration: 첫 번째 진단 태스크가 뱉어낸 metrics(진단 리포트 구조체) 컨텍스트를 서비스 내부 상태에 보존한 뒤, 이를 후행 보간 태스크 실행 시점에 매끄럽게 피딩 연결하는 중재자 역할 수행.
- Polymorphic Summary Reporting (log_preprocessing_summary): 이질적인 정제 통계 구조를 지닌 하위 결과물들을 서비스 코드의 손상 없이 다형성 기반으로 순회하며 단 1회 종합 공식 정산 로깅 처리함.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 팩토리 일괄 빌드를 통한 무인자 순차 오케스트레이션 루프 운용 vs 외부 스케줄러 기반 개별 단계 순차 호출 조율:
  - 장점: 전처리 도메인의 내부 실행 시퀀스 권한이 상위 레이어로 유출되지 않으므로 파이프라인 전체의 캡슐화가 완벽해지며, 전처리 단계가 4단계에서 8단계로 확장되거나 특정 실험에서 이상치 처리를 제외하더라도 상위 스케줄러 코드는 영구히 수정 면제권을 획득함.
  - 단점: 순차 루프 내부에서 데이터프레임 가공 객체와 진단 메타데이터 객체가 유동적으로 교차 파이프라이닝되므로, 루프 제어문 내부의 `isinstance` 검동 조건이나 데이터 컨텍스트 스와핑 코드가 미시적으로 정교해져 서비스 내부 복잡성이 소폭 상승함.
  - 근거: 프로덕션급 MLOps 인프라의 최고 덕목은 '지속 가능한 확장성'과 '설정 기반 제어'임. 전처리 내부 순서가 바뀔 때마다 상위 메인 파이프라인 코드를 재배포해야 하는 구조는 상용 환경에서 심각한 인프라 다운타임 리스크를 유발하므로 서비스 내부에서 은닉 오케스트레이션 루프를 돌리는 방식이 절대적으로 정당함.
"""

from typing import Dict, Any, List
import pandas as pd

from src.common.config import ConfigManager
from src.common.log import LogManager
from src.common.decorators.log_decorator import log_decorator
from src.common.exceptions import PreprocessorServiceError, PreprocessorError
from src.preprocessor.preprocessor_factory import PreprocessorFactory

# ==============================================================================
# Main Class/Functions
# ==============================================================================
class PreprocessorService:
    """전처리 파이프라인의 오케스트레이터 및 파사드(Facade) 역할을 수행하는 서비스 클래스.

    외부 인자 종속성이 완벽히 제거된 단순 인터페이스 execute_preprocessing_job() 메서드를 제공하며,
    내부 팩토리가 빌드한 순차 태스크 체인을 순회 구동하여 고차원 시계열을 정제합니다.

    Attributes:
        _preprocessor_factory (PreprocessorFactory): 내부에서 캡슐화되어 전처리 하위 태스크 체인 생성을 일괄 전담하는 아키텍처 팩토리 인스턴스.
        _job_metrics_registry (Dict[str, Any]): 이질적인 하위 태스크들이 순차 수행된 후 생성한 고유 요약 metrics 데이터를 작업 명칭별로 보존하는 인메모리 레지스트리.
    """

    def __init__(self) -> None:
        """기존 ExtractorService 표준 은닉 구조를 완벽히 미러링하여 하위 기구를 자율 인스턴스화합니다."""
        self._config = ConfigManager.load("preprocessor")
        self._logger = LogManager.get_logger("PreprocessorService")
        self._preprocessor_factory = PreprocessorFactory()
        self._job_metrics_registry = {}
        

    @log_decorator()
    def execute_preprocessing_job(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """팩토리가 조립한 구체 태스크 체인을 순회하며 순차적 전처리 파이프라이닝을 총괄 제어합니다.

        Args:
            market_data (pd.DataFrame): Ingestion 레이어에서 적재되어 넘어온 
                20거래일 슬라이딩 Lookback 윈도우 원본 금융 시계열 행렬.

        Returns:
            Dict[str, Any]: 다운스트림 모델 레이어가 직접 소비할 최종 정제 데이터 버킷 및 마스크 행렬 패키지.

        Raises:
            PreprocessorServiceError: 체인 오케스트레이션 구동 중 예기치 못한 인프라 자원 부족 
                또는 수리 연산 패닉 발생 시 최상위 파이프라인 감지를 위해 전파.
        """
        # [설계 의도] 하위 연산 레이어 진입 전 오케스트레이터 입구에서 인풋 행렬의 데이터 형식을 엄격하게 검증하여,
        # 규격이 파괴된 인스턴스가 내부 루프에 진입해 전체 시스템을 오염시키는 현상을 방어함.
        if not isinstance(market_data, pd.DataFrame):
            raise PreprocessorServiceError(
                message="서비스 레이어로 주입된 입력 데이터 매트릭스가 유효한 pd.DataFrame 구조가 아닙니다."
            )

        try:
            # [설계 의도] 원본 마켓 데이터의 불변성을 보장하고, 파이프라인 전반의 다중 앙상블 버킷 연산 도중 
            # 발생할 수 있는 상호 데이터 참조 오염(Side-Effect)을 원천 차단하기 위해 명시적 깊은 복사를 수행함.
            current_df = market_data.copy()

            # [설계 의도] 내부 팩토리의 create_preprocessor()를 기동하여 preprocessor.yml 설정 파일의 
            # 활성화 정책 구조에 맞춰 정렬된 구체 태스크 체인(List[AbstractTask])을 일괄 수신함.
            preprocessor_tasks = self._preprocessor_factory.create_preprocessor()

            # [설계 의도] 특정 태스크가 이전 단계의 결과물(진단서 리포트 등)을 요구하는 선후 종속성 문제를 
            # 상태 저장소 격리 원칙에 맞춰 안전하게 중계하기 위해 파이프라인 임시 공유 사전을 개설함.
            pipeline_context: Dict[str, Any] = {}
            final_artifacts: Dict[str, Any] = {}

            # 정렬된 태스크 체인 순차 실행 오케스트레이션 루프
            for task in preprocessor_tasks:
                task_name = task.__class__.__name__

                if task_name == "MissingValueDiagnosis":
                    # [설계 의도] 1단계 결측치 진단 태스크를 집행하여 휴장일 및 연속 결측장 사전을 획득하고,
                    # 서비스 마스터 메타데이터 레지스트리의 제1지점(MISSING_VALUE_DIAGNOSIS)에 즉시 동기화함.
                    diagnosis_report = task.execute(current_df)
                    pipeline_context["diagnosis_report"] = diagnosis_report
                    self._job_metrics_registry["MISSING_VALUE_DIAGNOSIS"] = diagnosis_report
                    
                elif task_name == "MissingValueImputation":
                    # [설계 의도] 2단계 1차 보간(Pass 1)을 수행하여 3대 기초 가격 버킷 사전을 빌드함.
                    # 임퓨터 내부에 요약 메타 리포트가 상주할 경우 이를 제2지점(MISSING_VALUE_IMPUTATION)에 격리 보존함.
                    imputation_result = task.execute(current_df, pipeline_context["diagnosis_report"])
                    pipeline_context["imputation_artifacts"] = imputation_result
                    
                    if "imputation_summary_report" in imputation_result:
                        self._job_metrics_registry["MISSING_VALUE_IMPUTATION"] = imputation_result["imputation_summary_report"]
                    else:
                        self._job_metrics_registry["MISSING_VALUE_IMPUTATION"] = imputation_result

                elif task_name == "OutlierDiagnosis":
                    # [설계 의도] 3단계 이상치 다차원 매트릭스 교차 진단을 트리거하여 불리언 마스크 리포트를 빌드하고,
                    # 이를 오염도 스캔용 소스로 가동하기 위해 제3지점(OUTLIER_DIAGNOSIS) 레지스트리에 정밀 바인딩함.
                    outlier_report = task.execute(pipeline_context["imputation_artifacts"])
                    pipeline_context["outlier_diagnosis_report"] = outlier_report
                    self._job_metrics_registry["OUTLIER_DIAGNOSIS"] = outlier_report

                elif task_name == "OutlierRefinement":
                    # [설계 의도] 4단계 이상치 정제 태스크를 기동하여 18대 전처리 다형성 분기 우주를 사출함.
                    refinement_result = task.execute(
                        pipeline_context["imputation_artifacts"],
                        pipeline_context["outlier_diagnosis_report"]
                    )
                    
                    # [설계 의도] Two-Pass Imputation & Algorithmic Masking 아키텍처 연쇄 최종 안전벽 기동.
                    # refine_masking 정책으로 인해 인위적 NaN이 주입된 9대 실험 버킷을 스캔하여 시계열 인과 결을 보존하는 보간 연쇄 집행.
                    for artifact_key, bucket_df in refinement_result.items():
                        if "_refine_masking" in artifact_key:
                            refinement_result[artifact_key] = bucket_df.ffill(axis=0).bfill(axis=0).fillna(0.0)
                    
                    # 최종 청정 데이터프레임 버킷 취합 및 다운스트림 텐서 방어벽 목적의 마스크 쌍 패키징 싱크
                    final_artifacts.update(refinement_result)
                    final_artifacts["missing_indicator_mask"] = pipeline_context["imputation_artifacts"]["missing_indicator_mask"]
                    final_artifacts["target_sample_weights"] = pipeline_context["imputation_artifacts"]["target_sample_weights"]
                    
                    # 마스터 메타데이터 레지스트리의 최종 제4지점(OUTLIER_REFINEMENT)에 정제 결과 프레임 세트를 전사 싱크 적재.
                    self._job_metrics_registry["OUTLIER_REFINEMENT"] = refinement_result

            target_date = market_data.index[-1]
            for artifact_key, artifact_df in final_artifacts.items():
                if isinstance(artifact_df, pd.DataFrame):
                    final_artifacts[artifact_key] = artifact_df.loc[[target_date]]

            return final_artifacts

        except PreprocessorError as preprocessor_error:
            # 하위 태스크 수리 연산 내부에서 완벽하게 구조화되어 래핑되어 올라온 커스텀 예외는 직통 전파
            raise preprocessor_error

        except Exception as original_exception:
            # 예기치 못한 인프라 장애나 하드웨어 패닉 상황을 전처리 서비스 예외인 PreprocessorServiceError로 최종 봉인 전파
            raise PreprocessorServiceError(
                message="PreprocessorService에서 전처리 시퀀스 체인 오케스트레이션 구동 중 치명적인 시스템 크래시가 감지되었습니다.",
                original_exception=original_exception
            )

    def log_preprocessing_summary(self) -> None:
        """4대 요약 레지스트리에 보존된 메타데이터를 트리 구조로 실시간 동적 해독하여 계층형 정산 리포트를 공식 발표합니다.

        [설계 의도] 각 전처리 태스크가 독립적으로 적재한 상이한 통계 구조체를 서비스 코드가 유연하게 
        소화할 수 있도록 방어적 가드 인덱싱을 장착하고, 정밀한 수리 계량을 거쳐 시각화 로그를 사출합니다.
        """
        if not self._job_metrics_registry:
            self._logger.warning("레지스트리 허브 내부에 정산 발표할 전처리 실행 metrics 메타데이터가 존재하지 않습니다.")
            return

        self._logger.info("[Preprocessor 종합 요약 리포트]")

        # 1단계 요약 정산: MISSING_VALUE_DIAGNOSIS
        if "MISSING_VALUE_DIAGNOSIS" in self._job_metrics_registry:
            diag_data = self._job_metrics_registry["MISSING_VALUE_DIAGNOSIS"]
            holiday_count = len(diag_data.get("market_holiday_timestamps", []))
            max_run_dict = diag_data.get("asset_max_run_length", {})
            halted_count = sum(1 for r in max_run_dict.values() if r >= 6)
            
            self._logger.info(" 1. MISSING_VALUE_DIAGNOSIS (결측치 시공간 탐지 및 진단 국면)")
            self._logger.info(f"  ├── 시장 공통 휴장 / 시스템 다운 전체 암전 일수 : {holiday_count} 일")
            self._logger.info(f"  └── 25% 임계치(6일) 초과 장기 거래정지 및 격리 자산수 : {halted_count} 종")
            self._logger.info("  │")

        # 2단계 요약 정산: MISSING_VALUE_IMPUTATION
        if "MISSING_VALUE_IMPUTATION" in self._job_metrics_registry:
            impute_data = self._job_metrics_registry["MISSING_VALUE_IMPUTATION"]
            # 리포트 사전이거나 통 통째 딕셔너리일 경우를 모두 대비한 방어적 안전 계량 가동
            short_count = impute_data.get("short_term_locf_asset_count", 0) if isinstance(impute_data, dict) else 0
            medium_count = impute_data.get("medium_term_kalman_asset_count", 0) if isinstance(impute_data, dict) else 0
            long_count = impute_data.get("long_term_neutralized_asset_count", 0) if isinstance(impute_data, dict) else 0
            
            self._logger.info("2. MISSING_VALUE_IMPUTATION (결측치 다형성 라우팅 보간 국면)")
            self._logger.info(f"  ├── 단기 결측 처리 자산 수 (LOCF/LogReturn/MA 병렬 분기)  : {short_count} 종")
            self._logger.info(f"  ├── 중기 결측 처리 자산 수 (단변량 Kalman Filter 평활화)  : {medium_count} 종")
            self._logger.info(f"  └── 장기 결측 격리 무력화 자산 수 (Loss Neutralization 마스크) : {long_count} 종")
            self._logger.info("  │")

        # 3단계 요약 정산: OUTLIER_DIAGNOSIS
        if "OUTLIER_DIAGNOSIS" in self._job_metrics_registry:
            outlier_diag_data = self._job_metrics_registry["OUTLIER_DIAGNOSIS"]
            self._logger.info("3. OUTLIER_DIAGNOSIS (이상치 다차원 매트릭스 교차 진단 국면)")
            
            bucket_keys = list(outlier_diag_data.keys())
            for b_idx, b_key in enumerate(bucket_keys):
                is_last_bucket = (b_idx == len(bucket_keys) - 1)
                b_prefix = "  └──" if is_last_bucket else "  ├──"
                self._logger.info(f"{b_prefix} 국면 버킷 명칭: [{b_key}]")
                
                engines_dict = outlier_diag_data[b_key]
                engine_keys = list(engines_dict.keys())
                for e_idx, e_key in enumerate(engine_keys):
                    mask_df = engines_dict[e_key]
                    total_cells = mask_df.size
                    outlier_cells = mask_df.sum().sum()
                    contamination_ratio = (outlier_cells / total_cells) * 100 if total_cells > 0 else 0.0
                    
                    e_parent_prefix = "        " if is_last_bucket else "  │   "
                    e_child_prefix = "└──" if (e_idx == len(engine_keys) - 1) else "├──"
                    
                    self._logger.info(
                        f"{e_parent_prefix}{e_child_prefix} 수리 엔진 [{e_key:<16}] -> 오염도: "
                        f"{contamination_ratio:>5.2f}% (총 {outlier_cells:>3}개 비정상 좌표 검출)"
                    )
            self._logger.info("  │")

        # 4단계 요약 정산: OUTLIER_REFINEMENT
        if "OUTLIER_REFINEMENT" in self._job_metrics_registry:
            refine_data = self._job_metrics_registry["OUTLIER_REFINEMENT"]
            total_buckets = len(refine_data)
            clipping_count = sum(1 for k in refine_data.keys() if "_refine_clipping" in k)
            masking_count = sum(1 for k in refine_data.keys() if "_refine_masking" in k)
            
            self._logger.info("4. OUTLIER_REFINEMENT (이상치 실험 경로 사출 및 복원 국면)")
            self._logger.info(f"  ├── 총 병렬 분기 사출 완료된 최종 전처리 실험 우주 버킷 본수 : {total_buckets} 종")
            self._logger.info(f"  ├── 변동성 방향성 보존형 상하한 조정 (Clipping Refine) 버킷 : {clipping_count} 종")
            self._logger.info(f"  └── Two-Pass Imputation 연쇄 수료형 마스킹 (Masking Refine) 버킷  : {masking_count} 종")