"""
[모듈 제목]
Airflow DAG Sourcing Module for Bronze Layer

[모듈 목적 및 상세 설명]
Airflow 오케스트레이터를 활용하여 Bronze ETL 파이프라인(src.main)을 일 단위로 스케줄링하고 실행하는 DAG(Directed Acyclic Graph) 정의 모듈입니다.
비동기 기반으로 작성된 독립적인 파이썬 수집 애플리케이션의 진입점을 Bash 환경을 통해 트리거합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Trigger: Airflow Scheduler가 정의된 CRON 식(매일 자정 KST)에 따라 DAG를 인스턴스화.
2. Context Injection: Airflow의 논리적 실행 날짜(data_interval_end)를 환경 변수로 세팅.
3. Execution: BashOperator가 파이프라인의 루트 디렉토리로 이동하여 `python -m src.main` 실행.
4. Output: 수집/적재 성공 여부에 따라 Airflow Task 상태(Success/Fail) 결정.

주요 기능:
- [Timezone Management] `pendulum` 라이브러리를 활용하여 DAG의 스케줄링 타임존을 'Asia/Seoul(KST)'로 명확히 고정.
- [Task Isolation] Airflow의 워커 메모리 공간과 파이썬 수집 애플리케이션의 메모리/이벤트 루프 공간을 프로세스 레벨에서 분리.
- [Idempotency] 파이프라인 실패 시 재시도(Retry) 횟수 및 백오프(Backoff) 딜레이를 설정하여 일시적 네트워크 장애 방어.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- PythonOperator vs BashOperator:
  - 장점: `BashOperator`를 사용하면 기존에 작성된 `src/main.py`의 `asyncio.run()` 이벤트 루프와 Airflow Worker의 비동기 루프 간 충돌(RuntimeError: Event loop is already running)을 완벽히 원천 차단할 수 있음. 또한 의존성이 격리되어 의도치 않은 패키지 충돌이 방지됨.
  - 단점: Airflow XCom을 활용하여 파이썬 객체를 태스크 간 직접 주고받는 것이 번거로워짐 (표준 출력 파싱 필요).
  - 근거: 현재 아키텍처는 `src/main.py`가 데이터를 수집하고 S3에 적재하는 닫힌 생명주기(Closed Lifecycle)를 가지고 있으므로, 복잡한 XCom 통신보다 환경의 **격리와 안정적인 비동기 실행**이 압도적으로 중요함. 따라서 `BashOperator` 채택이 최적임.
"""

import os
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

# ==============================================================================
# [Constants & Configuration]
# ==============================================================================
# 매직 스트링 배제 및 유지보수를 위한 상수 정의
DAG_ID: str = "bronze_daily_sourcing_pipeline"
SCHEDULE_CRON: str = "0 0 * * *"  # KST 기준 매일 자정 00:00 실행 (테스트용)
TIMEZONE: str = "Asia/Seoul"

# Task 실패 시 재시도 정책
RETRIES: int = 2
RETRY_DELAY_MINUTES: int = 5

# Airflow 컨테이너 내 파이프라인 소스코드 경로
PROJECT_ROOT_DIR: str = "/opt/airflow"


# ==============================================================================
# [Custom Exceptions]
# ==============================================================================
class BronzeDAGConfigurationError(Exception):
    """Bronze DAG 설정 또는 런타임 환경 구성 중 발생하는 에러를 정의하는 사용자 정의 예외."""
    pass


# ==============================================================================
# [Main Class/Functions]
# ==============================================================================
# KST 타임존이 적용된 기본 파라미터 구성
default_args = {
    "owner": "data_engineering_team",
    "depends_on_past": False,  # 과거 배치 실패가 현재 배치 실행을 막지 않음
    "start_date": pendulum.datetime(2026, 4, 20, tz=TIMEZONE),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": RETRIES,
    "retry_delay": timedelta(minutes=RETRY_DELAY_MINUTES),
}

with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description="Macro Data & Stock VTS API Daily Sourcing Pipeline",
    schedule=SCHEDULE_CRON,
    catchup=False,  # 과거 누락된 배치를 한꺼번에 재실행하지 않음 (API 쿼터 보호)
    tags=["bronze", "EL", "daily"],
) as dag:

    # [설계 의도] 
    # src 디렉토리가 파이썬 패키지로 정상 인식되도록 PYTHONPATH를 현재 경로로 명시하고,
    # python -m 옵션을 사용하여 src.main 모듈을 실행합니다.
    run_bronze_pipeline = BashOperator(
        task_id="run_bronze_main_app",
        bash_command=f"cd {PROJECT_ROOT_DIR} && export PYTHONPATH={PROJECT_ROOT_DIR} && python -m src.main",
        # [설계 의도] Airflow의 {{ ds_nodash }} (예: 20260421)를 환경변수로 주입하여, 
        # 향후 main.py에서 해당 날짜를 수집 기준일(execution_date)로 활용할 수 있도록 대비함.
        env={**os.environ, "AIRFLOW_EXECUTION_DATE": "{{ ds_nodash }}"},
        append_env=True,
    )

    # 단일 Task이므로 의존성(>> 연산) 생략
    run_bronze_pipeline