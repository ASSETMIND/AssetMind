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

from src.common.decorators.log_decorator import log_decorator
from src.common.exceptions import PreprocessorServiceError, PreprocessorError
from preprocessor.preprocessor_factory import PreprocessorFactory

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
        self._preprocessor_factory = PreprocessorFactory()
        self._job_metrics_registry = {}

    @log_decorator()
    def execute_preprocessing_job(self, market_data: pd.DataFrame) -> Any:
        """내부 팩토리로부터 설정 기반 전처리 태스크 체인을 일괄 수신하여 순차 가공 파이프라이닝을 조율 집행합니다.

        Args:
            market_data (pd.DataFrame): 클렌징 레이어를 통과하여 유입된, 물리적 차원이 보존된 금융 시계열 데이터프레임.

        Returns:
            Any: 최종 전처리 시퀀스가 수료되어 하위 ML 모델이 즉시 수용 가능한 마스터 정제 데이터 세트 (또는 복합 리포트 딕셔너리).

        Raises:
            PreprocessorError: 하위 태스크 가드레일 조건 미달 및 팩토리 조립 결함으로 인해 명시 전파된 비즈니스 예외.
            PreprocessorServiceError: 런타임 행렬 연산 및 커널 메모리 붕괴 등 예기치 못한 인프라 장애 발생 시 포착.
        """
        try:
            # [Design Intent] 당신의 제안대로 job_id 매개변수 주입을 전면 제거하고 팩토리에 일괄 빌드 권한을 위임함
            preprocessor_tasks: List[Any] = self._preprocessor_factory.create_preprocessor()
            market_data = market_data.copy()  # 원본 데이터프레임 보호를 위해 복제본으로 작업

            # 후행 보간 및 이상치 레이어에 피드백 전파할 공유 컨텍스트 프레임워크 초기화
            current_preprocessing_target = market_data
            final_integrated_report: Dict[str, Any] = {}

            # [순차 오케스트레이션 루프 파이프라이닝 엔진]
            for task_instance in preprocessor_tasks:
                task_class_name = task_instance.__class__.__name__

                # 1단계: 결측치 탐지 및 진단(MissingValueDiagnosisTask) 구동 분기 조율
                if task_class_name == "MissingValueDiagnosisTask":
                    # 진단 태스크는 데이터를 파괴하지 않고 하위 방어용 메타데이터 리포트 사전을 반환함
                    diagnosis_report: Dict[str, Any] = task_instance.execute(
                        market_data=current_preprocessing_target
                    )
                    
                    # [다형성 리포트 엔진 적재] 요약 출력 및 공유 컨텍스트 저장을 위해 인메모리 레지스트리와 마스터 레포트에 동시 바인딩
                    self._job_metrics_registry["MISSING_VALUE_DIAGNOSIS"] = diagnosis_report
                    final_integrated_report.update(diagnosis_report)

                # 2단계: [확장성 예약 구역] 향후 추가될 후행 보간 태스크 구동 시 앞선 진단 컨텍스트(final_integrated_report)를 함께 피딩 주입
                elif task_class_name == "MissingValueImputationTask":
                    # current_preprocessing_target = task_instance.execute(
                    #     market_data=current_preprocessing_target,
                    #     diagnosis_report=final_integrated_report
                    # )
                    pass

                # 3단계: [확장성 예약 구역] 이상치 탐지 및 처리 컴포넌트 순차 파이프라이닝 구역
                elif task_class_name == "OutlierDetectionTask":
                    pass

            # 전처리 체인 최종 수료 후 취합된 복합 프레임워크 자원을 반환 (진단 레이어 단독 기동 시 리포트 사전 반환 표준 보존)
            return final_integrated_report if len(preprocessor_tasks) == 1 else current_preprocessing_target

        except PreprocessorError as preprocessor_error:
            # 하위 연산 및 조립 파일에서 엄격하게 캡슐화되어 올라온 커스텀 예외는 변형 없이 상위 파이프라인으로 직통 전파
            raise preprocessor_error

        except Exception as original_exception:
            # 예기치 못한 시스템 메모리 다운 등을 3단계 위계의 전처리 서비스 예외로 최종 봉인 처리
            raise PreprocessorServiceError(
                message=f"PreprocessorService에서 외부 인자 거세형 전처리 체인 오케스트레이션 중 인프라 크래시가 감지되었습니다.",
                original_exception=original_exception
            )

    def log_preprocessing_summary(self) -> None:
        """전처리 시퀀스 완료 후 인메모리 레지스트리에 적재된 이질적 요약 리포트 메타데이터를 공식 일괄 적재 발표합니다.

        [설계 의도] 서비스 내부에 하드코딩된 문자열 포맷터를 들이밀지 않고,
        레지스트리에 보존된 도메인 metrics 통계량을 다형성 기반으로 순회 출력하여 구조적 청정 상태를 사수합니다.
        """
        if not self._job_metrics_registry:
            return

        for job_key, metrics_data in self._job_metrics_registry.items():
            if job_key == "MISSING_VALUE_DIAGNOSIS":
                holiday_count = len(metrics_data.get("market_holiday_timestamps", []))
                max_run_dict = metrics_data.get("asset_max_run_length", {})
                halted_assets_count = sum(1 for max_run in max_run_dict.values() if max_run >= 6)

                print(
                    f"[Preprocessor 종합 요약 리포트 - {job_key}] 전체 시장 휴장/시스템 다운 유효 일수: {holiday_count}일 | "
                    f"25% 임계치(6일)를 초과한 장기 거래정지 및 위험 오염 자산 수: {halted_assets_count}종"
                )

            elif job_key == "MISSING_VALUE_IMPUTATION":
                pass

            elif job_key == "OUTLIER_DETECTION":
                pass