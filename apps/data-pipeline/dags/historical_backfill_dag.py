"""
[모듈 제목]
Airflow DAG Sourcing Module for Historical Backfill Layer

[모듈 목적 및 상세 설명]
Airflow 오케스트레이터를 활용하여 2016년부터 2021년까지의 과거 금융 데이터 ETL 파이프라인(src.main)을 연도별로 스케줄링하고 실행하는 DAG 정의 모듈입니다.
기존 daily 파이프라인과 동일한 `create_dag` 팩토리 패턴을 사용하여 시스템적 통일성을 유지하고, 연도별 catchup 구간을 명확히 한정하여 백필을 수행합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Trigger: Airflow Scheduler가 정의된 CRON 식 및 catchup 설정에 따라 과거 일자별 DAG Run을 순차 인스턴스화.
2. Context Injection: Airflow의 논리적 실행 날짜(data_interval_start)를 타임존에 맞춰 포맷팅하여 환경 변수로 세팅.
3. Execution: BashOperator가 파이프라인의 루트 디렉토리로 이동하여 `python -m src.main` 실행.
4. Output: 수집/적재 성공 여부에 따라 Airflow Task 상태(Success/Fail) 결정.

주요 기능:
- [Timezone Management] `pendulum` 라이브러리를 활용하여 DAG의 스케줄링 타임존(Asia/Seoul, America/New_York)을 명확히 고정.
- [Task Isolation] Airflow의 워커 메모리 공간과 파이썬 수집 애플리케이션의 메모리/이벤트 루프 공간을 프로세스 레벨에서 분리.
- [Idempotency] `depends_on_past=True` 및 재시도 설정을 통해 시계열 순서 보장 및 장애 복구 능력 확보.
- [Exact Period Alignment] 자정 실행 기준 전일 데이터 수집 메커니즘에 맞춰 1년 단위 범위를 정확히 한정.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거 요약.
- PythonOperator vs BashOperator:
  - 장점: `BashOperator`를 사용하면 기존에 작성된 `src/main.py`의 `asyncio.run()` 이벤트 루프와 Airflow Worker의 비동기 루프 간 충돌을 원천 차단함.
  - 단점: Airflow XCom을 활용한 세부 객체 전달 제약.
  - 근거: 닫힌 생명주기(Closed Lifecycle)를 가지는 수집/정제 아키텍처 특성상 환경 격리와 안정적 실행이 최우선이므로 `BashOperator` 채택.
"""

import os
from datetime import timedelta
from typing import Optional

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

# ==============================================================================
# [Constants & Configuration]
# ==============================================================================
# Task 실패 시 재시도 정책
RETRIES: int = 3
RETRY_DELAY_MINUTES: int = 10

# Airflow DAG 동시 실행 제한 (과거 대량 수집 시 시스템 리소스 보호)
MAX_ACTIVE_RUNS: int = 2

# Airflow 컨테이너 내 파이프라인 소스코드 경로
PROJECT_ROOT_DIR: str = "/opt/airflow"

# 백필 대상 연도 목록 (2016 ~ 2021)
TARGET_YEARS = [2016, 2017, 2018, 2019, 2020, 2021]


# ==============================================================================
# [Main Class/Functions]
# ==============================================================================
def create_dag(
    dag_id: str,
    schedule: str,
    timezone: str,
    task_key: str,
    start_year: int,
    start_month: int,
    start_day: int,
    end_year: Optional[int] = None,
    end_month: Optional[int] = None,
    end_day: Optional[int] = None
) -> DAG:
    """동적 파라미터를 주입받아 Airflow DAG 객체를 생성하는 팩토리 함수입니다.

    Args:
        dag_id (str): Airflow UI에 노출될 DAG의 고유 식별자.
        schedule (str): CRON 표현식 스케줄.
        timezone (str): DAG 실행의 기준이 되는 타임존 (예: Asia/Seoul, America/New_York).
        task_key (str): main.py로 전달될 타겟 태스크 이름 (TARGET_TASK).
        start_year (int): DAG의 시작 연도.
        start_month (int): DAG의 시작 월.
        start_day (int): DAG의 시작 일.
        end_year (Optional[int]): DAG의 종료 연도.
        end_month (Optional[int]): DAG의 종료 월.
        end_day (Optional[int]): DAG의 종료 일.

    Returns:
        DAG: 구성이 완료된 Airflow DAG 객체.
    """
    default_args = {
        "owner": "AssetMind_DE",
        "depends_on_past": True,
        "retries": RETRIES,
        "retry_delay": timedelta(minutes=RETRY_DELAY_MINUTES),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=30),
    }

    start_date = pendulum.datetime(start_year, start_month, start_day, tz=timezone)
    end_date = (
        pendulum.datetime(end_year, end_month, end_day, tz=timezone)
        if end_year is not None and end_month is not None and end_day is not None
        else None
    )

    with DAG(
        dag_id=dag_id,
        default_args=default_args,
        start_date=start_date,
        end_date=end_date,
        schedule=schedule,
        catchup=True,
        max_active_runs=MAX_ACTIVE_RUNS,
        tags=["backfill", str(start_year), task_key.split("_")[-1]],
    ) as dag:

        # 1. Bronze Task : 외부 API에서 원본 데이터 추출 및 S3 적재
        run_bronze = BashOperator(
            task_id=f"run_bronze_{task_key}",
            bash_command=f"cd {PROJECT_ROOT_DIR} && export PYTHONPATH={PROJECT_ROOT_DIR} && python -m src.main",
            env={
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
        run_gold = BashOperator(
            task_id=f"run_gold_{task_key}",
            bash_command=f"cd {PROJECT_ROOT_DIR} && export PYTHONPATH={PROJECT_ROOT_DIR} && python -m src.main",
            env={
                "EXECUTION_DATE": "{{ data_interval_start.in_timezone(dag.timezone).strftime('%Y%m%d') }}",
                "TARGET_TASK": f"gold_{task_key}"
            },
            append_env=True,
        )

        # 4. Task 의존성 (흐름) 제어
        run_bronze >> run_silver >> run_gold

    return dag


# ==============================================================================
# [DAG Instances Generation (2016 ~ 2021)]
# ==============================================================================
# 자정(00:00) 실행 시 전일 데이터를 수집하므로, 
# YYYY0101 데이터를 수집하기 위해 start_date는 YYYY-01-02로 지정하고,
# YYYY1231 데이터를 수집하기 위해 end_date는 (YYYY+1)-01-01로 지정합니다.
for target_year in TARGET_YEARS:
    # 1. Asia 백필 파이프라인 (KST 00:00)
    globals()[f"backfill_asia_{target_year}_dag"] = create_dag(
        dag_id=f"backfill_asia_{target_year}",
        schedule="0 0 * * *",
        timezone="Asia/Seoul",
        task_key="daily_asia",
        start_year=target_year,
        start_month=1,
        start_day=2,
        end_year=target_year + 1,
        end_month=1,
        end_day=1
    )

    # 2. Global 백필 파이프라인 (EST 00:00)
    globals()[f"backfill_global_{target_year}_dag"] = create_dag(
        dag_id=f"backfill_global_{target_year}",
        schedule="0 0 * * *",
        timezone="America/New_York",
        task_key="daily_global",
        start_year=target_year,
        start_month=1,
        start_day=2,
        end_year=target_year + 1,
        end_month=1,
        end_day=1
    )