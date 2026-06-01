"""
[모듈 제목]
Main Execution Entrypoint Module

[모듈 목적 및 상세 설명]
데이터 수집 및 적재(EL) 파이프라인 서비스를 비동기적으로 실행하는 최상위 애플리케이션 진입점입니다.
환경 변수를 로드하고, 스케줄러(Airflow)로부터 주입받은 파이프라인 태스크(Task)를 실행합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Initialization: `.env` 파일 로드 및 필수 환경 변수(TARGET_TASK) 검증.
2. Orchestration: `PipelineService` 인스턴스화 및 비동기 컨텍스트 매니저 진입.
3. Execution: `run_batch()` 호출을 통해 전체 데이터 파이프라인 가동.
4. Output: 실행 결과 메타데이터 획득 및 시스템 로그 출력, 자원 안전 종료.

주요 기능:
- [Fail-Fast Bootstrapping] 필수 환경 변수 누락 시 즉시 에러를 발생시켜 잘못된 배치 실행 방지.
- [Global Error Handling] `@log_decorator`를 활용하여 최상위 레벨의 예외 포착 및 규격화.
- [Async Entrypoint] 비동기 이벤트 루프 생성 및 메인 코루틴 실행.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. 기본값(Default) 제거 및 환경 변수 강제화:
   - 장점: 파이프라인이 어떤 태스크를 실행하는지 명확히 강제하여, 설정 누락으로 인해 엉뚱한 배치가 도는 대형 사고(Silent Failure)를 원천 차단함.
   - 단점: 로컬 테스트 시 매번 `export TARGET_TASK=...`를 입력해야 하는 번거로움이 생김.
   - 근거: 데이터 파이프라인에서 정합성 훼손 복구 비용은 로컬 테스트의 번거로움보다 수백 배 크므로, 철저한 조기 실패(Fail-Fast) 원칙을 고수하는 것이 실무적으로 올바름.
2. 최상위 함수에 @log_decorator 적용:
   - 장점: try-except 보일러플레이트 없이도 파이프라인 서비스 구동 중 발생하는 치명적 에러를 표준 포맷으로 중앙 집중 로깅할 수 있음.
   - 근거: 횡단 관심사인 로깅과 비즈니스 런타임을 완전히 분리(Decoupling)하여 가독성과 유지보수성을 극대화함.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

from src.pipeline.pipeline_factory import PipelineFactory
from src.common.exceptions import ConfigurationError
from src.common.decorators.log_decorator import log_decorator

# [설계 의도] 하위 모듈들이 임포트되기 전에 환경 변수를 가장 먼저 메모리에 적재
load_dotenv()

# ==============================================================================
# [Configuration] Constants
# ==============================================================================
# [설계 의도] 기본값을 배제하고 순수 환경 변수만 읽음
TARGET_TASK: str = os.environ.get("TARGET_TASK")

# 빈 값(None 또는 빈 문자열) 검증 후 조기 종료(Fail-Fast)
if not TARGET_TASK:
    raise ConfigurationError(
        "치명적 설정 오류: 'TARGET_TASK' 환경 변수가 설정되지 않았습니다. "
        "Airflow BashOperator의 env 설정이나 로컬 환경 변수 주입을 확인하세요."
    )

# ==============================================================================
# [Main Class/Functions]
# ==============================================================================
@log_decorator()
async def main() -> None:
    """지정된 태스크명으로 파이프라인 오케스트레이션 서비스를 비동기 실행합니다.
    
    `PipelineService`의 비동기 컨텍스트 매니저(`async with`)를 활용하여 
    하위 네트워크 리소스(HTTP Session 등)가 누수 없이 안전하게 할당 및 해제되도록 보장합니다.
    """

    # [설계 의도] Airflow BashOperator가 환경변수로 주입한 논리적 실행 날짜(YYYYMMDD)를 획득.
    # Airflow 환경이 아닌 로컬 직접 실행 시에는 None이 되어 파이프라인 서비스 내부의 Fallback(오늘 날짜)이 작동함.
    airflow_exec_date = os.environ.get("EXECUTION_DATE")
    
    if airflow_exec_date:
        logging.getLogger("main").info(f"Airflow 스케줄러 기준 실행일({airflow_exec_date})로 수집을 진행합니다.")

    # [설계 의도] 구체 클래스(PipelineService)의 하드코딩 직접 선언을 폐기하고,
    # 팩토리의 가상 생성 대리자 인터페이스(`PipelineFactory.create`)를 통해 다형성을 확보함.
    # 이 구조는 향후 Silver/Gold 파이프라인이 추가되어 유입되어도 본 코드를 단 한 글자도 수정하지 않는 견고함을 제공함.
    async with PipelineFactory.create(TARGET_TASK) as pipeline:
        result = await pipeline.run_batch(
            execution_date=airflow_exec_date,
            extract_mode="TODAY" 
        )
        logging.getLogger("main").info(f"[{TARGET_TASK}] 실행 완료. 상태: {result.get('status')}")

        # 파이프라인 결과 검증 및 Fail-Fast 강제
        if result and result.get("status") in ["FAIL_PROCESSING", "CRITICAL_SYSTEM_ERROR"]:
            raise RuntimeError(
                f"[{TARGET_TASK}] 파이프라인 내부 가동 중 치명적 배치 오류가 발생했습니다. "
                f"상태코드: {result.get('status')}, 에러상세: {result.get('error_info')}"
            )

if __name__ == "__main__":
    # [설계 의도] 파이썬 비동기 생태계의 최상위 이벤트 루프 생성 및 메인 코루틴 진입점.
    asyncio.run(main())