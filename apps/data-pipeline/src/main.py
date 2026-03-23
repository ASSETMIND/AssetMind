"""
[모듈 제목]
Main Execution Entrypoint Module

[모듈 목적 및 상세 설명]
데이터 수집 및 적재(EL) 파이프라인 서비스를 비동기적으로 실행하는 최상위 애플리케이션 진입점입니다.
환경 변수를 로드하고, 스케줄러(Cron/Airflow) 또는 사용자가 정의한 파이프라인 태스크(Task)의 이름을 주입하여 전체 배치를 가동합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Initialization: `.env` 파일로부터 시스템 구동에 필요한 환경 변수 로드.
2. Task Injection: `pipeline.yml`에 정의된 타겟 태스크 이름(`TARGET_TASK`) 식별 및 주입.
3. Orchestration: `PipelineService` 인스턴스화 및 비동기 컨텍스트 매니저 진입.
4. Execution: `run_batch()` 호출을 통해 전체 데이터 파이프라인 가동.
5. Output: 실행 결과 메타데이터 획득 및 시스템 로그 출력, 사용된 네트워크 리소스 안전 종료.

주요 기능:
- [Environment Bootstrapping] `dotenv`를 활용하여 런타임에 필요한 민감 정보(API 키, DB 접속 정보 등)를 메모리에 안전하게 적재.
- [Task Injection] 실행할 파이프라인의 구체적인 작업명(예: 'daily_macro_batch')을 동적으로 주입하여 유연성 확보.
- [Async Entrypoint] `asyncio.run()`을 통해 비동기 이벤트 루프를 생성하고 메인 코루틴 실행.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- Hardcoded Target Task (`TARGET_TASK`) vs CLI Arguments (`argparse`):
  - 장점: 로컬 개발 환경이나 고정된 컨테이너 환경에서 실행 파일(`python main.py`)만으로 즉각적인 테스트와 실행이 가능하여 초기 개발 생산성이 매우 높음.
  - 단점: 다양한 태스크를 동적으로 분기 실행해야 하는 멀티 테넌트(Multi-tenant) 환경이나 복잡한 Airflow DAG 연동 시, 매번 소스 코드를 수정하거나 별도의 진입 래퍼(Wrapper)를 만들어야 하는 유연성 부족이 발생함.
  - 근거: 현재 파이프라인의 주요 실행 단위가 'daily_macro_batch' 하나로 고정되어 작동하는 단계이므로, 불필요한 CLI 파싱 로직을 추가하여 코드 복잡도를 높이기보다 명확하고 단순한 상수를 사용하는 것이 유지보수에 유리함. 향후 동적 실행 요구사항이 발생할 때 `argparse` 또는 환경변수 오버라이딩을 도입하는 점진적 리팩토링이 바람직함.
"""

import asyncio
import logging
from dotenv import load_dotenv

from src.pipeline_service import PipelineService

# [설계 의도] 애플리케이션 진입 직후 최우선적으로 환경 변수를 로드하여,
# 하위 모듈들이 임포트될 때 필수적인 환경 변수(API Key, 엔드포인트 등)가 누락되어 
# 런타임 에러가 발생하는 것을 원천 방지함.
load_dotenv()

# ==============================================================================
# [Configuration] Constants
# ==============================================================================
# [설계 의도] 실행할 기본 태스크 이름 지정. pipeline.yml 파일에 정의된 태스크 키와 
# 정확히 일치해야 파이프라인이 구동됨. 향후 동적 실행 기능(argparse) 도입 시 기본값(Default)으로 활용 가능.
TARGET_TASK: str = "daily_macro_batch"

# ==============================================================================
# Custom Exceptions
# ==============================================================================
# Main 레벨의 전용 예외는 정의하지 않음 (하위 도메인 예외를 그대로 수용)

# ==============================================================================
# [Main Class/Functions]
# ==============================================================================
async def main() -> None:
    """지정된 태스크명으로 파이프라인 오케스트레이션 서비스를 비동기 실행합니다.
    
    `PipelineService`의 비동기 컨텍스트 매니저(`async with`)를 활용하여 
    하위 네트워크 리소스(HTTP Session 등)가 누수 없이 안전하게 할당 및 해제되도록 보장합니다.
    """
    # [설계 의도] 기존 "pipeline"이라는 잘못된 범용 명칭 대신, 
    # pipeline.yml에 실제로 존재하는 "daily_macro_batch"를 명시적으로 주입하여 
    # 초기화 시점의 설정 에러(ConfigurationError) 및 빈 작업(EMPTY_JOBS) 상태를 조기 방지함.
    async with PipelineService(TARGET_TASK) as pipeline:
        result = await pipeline.run_batch()
        
        # [설계 의도] 내장 print() 함수 사용을 엄격히 금지하고 시스템 표준 로거(logging)를 활용.
        # 이를 통해 파이프라인의 최종 결과가 콘솔뿐만 아니라 ELK/Datadog 등의 중앙 로그 수집기에 정상 적재되도록 보장함.
        logging.getLogger("main").info(f"파이프라인 최종 결과: {result}")

if __name__ == "__main__":
    # [설계 의도] 파이썬 비동기 생태계의 최상위 이벤트 루프 생성 및 메인 코루틴 진입점.
    asyncio.run(main())