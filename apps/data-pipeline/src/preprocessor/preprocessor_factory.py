"""
[외부 설정 파일(.yml)의 활성화 정책을 파싱하여 순차 실행할 전처리 구체 태스크 객체 체인을 일괄 생성하는 팩토리 모듈]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: PreprocessorService 계층으로부터 매개변수 없는 전처리 컴포넌트 빌드 요청 유입.
2. Lookup Sequence: 내부에서 싱글톤 ConfigManager를 즉시 호출하여 preprocessor 정책 내부에 선언된 하위 작업 설정 유무 및 하이퍼파라미터 세트 일괄 로드.
3. Sequential Assembly: 설정에 명시된 하위 작업 키 명칭(missing_value_diagnosis 등)을 순차 검동하여 실행 대상 구체 태스크 인스턴스들을 생성하고 정렬된 리스트에 적재.
4. Output: 상위 오케스트레이터 서비스가 순차 순회 구동할 수 있도록 정렬된 구체 태스크(Task) 인스턴스 리스트(List) 반환.

주요 기능:
- Config-Driven Chain Generation: 외부에서 job_id를 주입받지 않고, 오직 preprocessor.yml 설정 파일의 명세 구조만을 파악하여 실행할 태스크 라인업을 스스로 조립함.
- Decoupling of Pipeline Steps: 서비스 계층에 구체 태스크 클래스의 문자열 매핑이나 생성자 호출 코드를 노출하지 않고 객체 토폴로지 생성 책임을 완벽히 격리함.
- Parameter Resolution Centralization: 개별 전처리 단계별로 요구되는 이질적인 마스킹 임계치, 윈도우 크기 수치들을 설정 허브로부터 가져와 객체에 사전 바인딩 주입함.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 설정 파일 직접 조회를 통한 순차 태스크 리스트 일괄 반환 vs 외부 job_id 매개변수 기반 단일 객체 매번 생성:
  - 장점: 서비스 레이어와 최상위 파이프라인 제어 장치로부터 전처리 세부 실행 마일스톤에 대한 모든 인자 결합도를 거세하여, 설정 파일 수정만으로 정제 파이프라인의 알고리즘 순서와 탑재 여부를 자유롭게 가공할 수 있는 극한의 개방 폐쇄 원칙(OCP)을 실현함.
  - 단점: 팩토리가 다수의 이질적인 태스크 객체들을 한 번에 인스턴스화하여 리스트로 반환하므로, 특정 단계만 단독으로 실행하거나 격리하여 유닛 테스트를 수행할 때 팩토리 내부의 전체 파싱 루틴을 우회해야 하는 가벼운 테스트 부하가 발생함.
  - 근거: 금융 시계열 전처리는 진단 통계량이 보간의 이정표가 되고 보간 결과가 이상치 탐지의 피처가 되는 고도의 선후 관계적 연쇄 결합 구조를 지님. 따라서 개별 단작업을 분리 요청하는 것보다 하나의 원자적 파이프라인 체인으로 묶어 서비스에 일괄 인도하는 구조가 인프라 무결성에 압도적으로 유리함.
"""

from typing import Any, List
from src.common.exceptions import PreprocessorFactoryError
from src.common.config import ConfigManager
from src.preprocessor.tasks.missing_value_diagnosis import MissingValueDiagnosis

# ==============================================================================
# Main Class/Functions
# ==============================================================================
class PreprocessorFactory:
    """전처리 파이프라인의 원자적 태스크 체인 생성을 전담하는 팩토리 클래스.

    외부 매개변수 주입을 전면 차단하고 내부에서 preprocessor.yml 설정을 직접 분석하여,
    활성화된 전처리 구체 태스크 객체들을 순서에 맞게 일괄 조립 생산합니다.
    """

    def __init__(self) -> None:
        """아키텍처 은닉 무결성 표준에 따라 외부 의존 인자가 완벽히 배제된 생성자를 초기화합니다."""
        self._config = ConfigManager.load("preprocessor")

    def create_preprocessor(self) -> List[Any]:
        """설정 파일(.yml)을 직접 조회하여 파이프라인 시퀀스에 대응하는 전처리 구체 태스크 인스턴스 리스트를 생성합니다.

        Returns:
            List[Any]: 하이퍼파라미터 조립이 완료되어 순차 실행(Piping)이 가능한 전처리 구체 태스크 객체들의 정렬된 배열 리스트.

        Raises:
            PreprocessorFactoryError: 설정 파일(.yml) 파싱 실패, 지원하지 않는 전략 명세가 검동될 경우 포착.
        """
        try:
            preprocessor_tasks: List[Any] = []

            # 1. 결측치 탐지 및 진단(MISSING_VALUE_DIAGNOSIS) 컴포넌트 정책 파싱 및 동적 조립
            if "missing_value_diagnosis" in self._config:
                diagnosis_config = self._config.get("missing_value_diagnosis")
                
                lookback_window_size = diagnosis_config.get("lookback_window_size", 20)
                short_gap_threshold_ratio = diagnosis_config.get("short_gap_threshold_ratio", 0.10)
                medium_gap_threshold_ratio = diagnosis_config.get("medium_gap_threshold_ratio", 0.25)
                co_missing_threshold_ratio = diagnosis_config.get("co_missing_threshold_ratio", 0.95)

                preprocessor_tasks.append(
                    MissingValueDiagnosis(
                        lookback_window_size=lookback_window_size,
                        short_gap_threshold_ratio=short_gap_threshold_ratio,
                        medium_gap_threshold_ratio=medium_gap_threshold_ratio,
                        co_missing_threshold_ratio=co_missing_threshold_ratio
                    )
                )

            # 2. [확장성 레이아웃 예약 구역] 결측치 처리(보간) 컴포넌트 설정이 yml에 감지될 경우 체인에 자동 후행 결합
            if "missing_value_imputation" in self._config:
                # imputation_config = self._config.get("missing_value_imputation")
                # preprocessor_task_chain.append(MissingValueImputationTask(...))
                pass

            # 3. [확장성 레이아웃 예약 구역] 이상치 탐지 및 처리 컴포넌트 자동 체인 결합 구역
            if "outlier_detection" in self._config:
                pass

            # 아키텍처 안전 가드레일: 활성화된 전처리 단계가 전혀 없을 경우 파이프라인 데이터 오염 방지를 위해 조기 에러 전파
            if not preprocessor_tasks:
                raise PreprocessorFactoryError(
                    message="preprocessor.yml 설정 내부에서 활성화된 전처리 작업(Job) 명세를 단 하나도 포착하지 못했습니다."
                )

            return preprocessor_tasks

        except PreprocessorFactoryError as factory_error:
            raise factory_error

        except Exception as original_exception:
            raise PreprocessorFactoryError(
                message=f"PreprocessorFactory에서 설정 기반 전처리 체인 조립 중 시스템 크래시가 발생했습니다. 사유: {str(original_exception)}",
                original_exception=original_exception
            )