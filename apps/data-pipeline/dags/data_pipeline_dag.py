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
# Task 실패 시 재시도 정책
RETRIES: int = 3
RETRY_DELAY_MINUTES: int = 10

# Airflow 컨테이너 내 파이프라인 소스코드 경로
PROJECT_ROOT_DIR: str = "/opt/airflow"

# ==============================================================================
# [Main Class/Functions]
# ==============================================================================
def create_dag(dag_id: str, schedule: str, timezone: str, task_key: str, start_year: int, start_month: int, start_day: int) -> DAG:
    """동적 파라미터를 주입받아 Airflow DAG 객체를 생성하는 팩토리 함수입니다.
    
    Args:
        dag_id (str): Airflow UI에 노출될 DAG의 고유 식별자.
        schedule (str): CRON 표현식 스케줄.
        timezone (str): DAG 실행의 기준이 되는 타임존 (예: Asia/Seoul).
        task_key (str): main.py로 전달될 타겟 태스크 이름 (TARGET_TASK).
        start_year (int): DAG의 시작 연도.
        start_month (int): DAG의 시작 월.
        start_day (int): DAG의 시작 일.
    Returns:
        DAG: 구성이 완료된 Airflow DAG 객체.
    """
    # [설계 의도] 타임존이 명확히 적용된 start_date를 설정하여
    # 글로벌 환경에서도 논리적 실행 날짜 오작동이 발생하지 않도록 강제함.
    default_args = {
        "owner": "AssetMind_DE",
        "depends_on_past": True,
        "retries": RETRIES,
        "retry_delay": timedelta(minutes=RETRY_DELAY_MINUTES),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=30),
    }

    with DAG(
        dag_id=dag_id,
        default_args=default_args,
        start_date=pendulum.datetime(start_year, start_month, start_day, tz=timezone),
        schedule=schedule,
        catchup=True,
        max_active_runs=10,
        tags=["daily", task_key.split('_')[-1]],
    ) as dag:
        
        # 1. Bronze Task : 외부 API에서 원본 데이터 추출 및 S3 적재
        run_bronze = BashOperator(
            task_id=f"run_bronze_{task_key}",
            bash_command=f"cd {PROJECT_ROOT_DIR} && export PYTHONPATH={PROJECT_ROOT_DIR} && python -m src.main",
            env={
                # [설계 의도] 무조건 UTC로 파싱되는 {{ ds_nodash }} 대신, 
                # DAG에 할당된 타임존(dag.timezone)을 기준으로 논리적 실행일(data_interval_start)을 포맷팅합니다.
                # 이를 통해 KST, EST 등 타임존과 무관하게 데이터의 "목표 대상일(Target Date)"이 정확히 주입됩니다.
                "EXECUTION_DATE": "{{ data_interval_start.in_timezone(dag.timezone).strftime('%Y%m%d') }}",
                "TARGET_TASK": f"bronze_{task_key}"
            },
            append_env=True,
            pool="external_api_pool"
        )

        # 2. Silver Task : 내부 원본 데이터 검증 및 정제 후 통합하여 S3 적재 
        run_silver = BashOperator(
            task_id=f"run_silver_{task_key}",
            bash_command=f"cd {PROJECT_ROOT_DIR} && export PYTHONPATH={PROJECT_ROOT_DIR} && python -m src.main",
            env={
                "EXECUTION_DATE": "{{ data_interval_start.in_timezone(dag.timezone).strftime('%Y%m%d') }}",
                "TARGET_TASK": f"silver_{task_key}"
            },
            append_env=True,
        )

        # 3. Gold Task : 피쳐 엔지니어링 및 파생변수 생성 후 PostgreSQL 적재

        # 4. Task 의존성 (흐름) 제어
        run_bronze >> run_silver

    return dag

# ==========================================================
# DAG 인스턴스 생성
# ==========================================================
# 1. Asia 파이프라인 (KST 00:00)
daily_asia_dag = create_dag(
    dag_id="daily_asia",
    schedule="0 0 * * *",
    timezone="Asia/Seoul",
    task_key="daily_asia",
    start_year=2000,
    start_month=1,
    start_day=2
)

# 2. Global 파이프라인 (EST 00:00)
daily_global_dag = create_dag(
    dag_id="daily_global",
    schedule="0 0 * * *",
    timezone="America/New_York",
    task_key="daily_global",
    start_year=2000,
    start_month=1,
    start_day=2
)