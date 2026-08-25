"""
[모듈 제목]
Airflow DAG Sourcing Module for Historical Silver & Gold Layer Backfill (No Bronze)

[모듈 목적 및 상세 설명]
외부 API를 호출하는 Bronze 수집 태스크를 완전히 배제하고, S3 Bronze 버킷에 이미 영구 적재된
원천 데이터를 읽어 Silver 및 Gold 레이어만 1년 단위로 순차 재생산(Backfill)하는 DAG 모듈입니다.
기존 daily 및 backfill 파이프라인과 동일한 create_dag 팩토리 패턴을 유지하며, 
Airflow UI 상에서 연도별/시장별(Asia, Global)로 독립 관제 및 순차 실행할 수 있도록 구성합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Trigger: Airflow Scheduler가 정의된 CRON 식 및 catchup 설정에 따라 과거 일자별 DAG Run 인스턴스화.
2. Context Injection: 논리적 실행 날짜(data_interval_start)를 타임존에 맞춰 환경 변수(EXECUTION_DATE)로 주입.
3. Silver Phase: BashOperator -> python -m src.main (TARGET_TASK=silver_{task_key}) 구동으로 Bronze S3를 읽어 Silver Parquet 적재.
4. Gold Phase: BashOperator -> python -m src.main (TARGET_TASK=gold_{task_key}) 구동으로 Silver Parquet를 읽어 18대 전처리 후 Gold Parquet 적재.
"""

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
RETRY_DELAY_MINUTES: int = 5

# 연도별 DAG 실행 시 리소스 보호 및 시계열 역산 윈도우 무결성을 위한 단일 순차 실행 보장
MAX_ACTIVE_RUNS: int = 4

# Airflow 컨테이너 내 파이프라인 소스코드 경로
PROJECT_ROOT_DIR: str = "/opt/airflow"

# 백필 대상 연도 목록 (2016 ~ 2026)
TARGET_YEARS = list(range(2016, 2027))


# ==============================================================================
# [Main Factory Function]
# ==============================================================================
def create_silver_gold_backfill_dag(
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
    """Bronze를 제외하고 Silver와 Gold 태스크만 1년 단위로 가동하는 Airflow DAG 팩토리 함수입니다.

    Args:
        dag_id (str): Airflow UI에 노출될 DAG 고유 식별자.
        schedule (str): CRON 표현식 스케줄.
        timezone (str): DAG 실행 기준 타임존 (Asia/Seoul, America/New_York).
        task_key (str): main.py로 전달될 타겟 태스크 키 (daily_asia, daily_global).
        start_year (int): 시작 연도.
        start_month (int): 시작 월.
        start_day (int): 시작 일.
        end_year (Optional[int]): 종료 연도.
        end_month (Optional[int]): 종료 월.
        end_day (Optional[int]): 종료 일.

    Returns:
        DAG: Silver >> Gold 순차 의존성이 구성된 Airflow DAG 객체.
    """
    default_args = {
        "owner": "AssetMind_DE",
        "depends_on_past": True,  # 시계열 순서 보장을 위해 선행 배치 완료 후 후행 배치 실행
        "retries": RETRIES,
        "retry_delay": timedelta(minutes=RETRY_DELAY_MINUTES),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=15),
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
        tags=["backfill", "silver_gold_only", str(start_year), task_key.split("_")[-1]],
    ) as dag:

        # 1. Silver Task : Bronze S3 파일 판독 -> 데이터 타입/스키마 정제 -> 와이드 테이블 병합 -> Silver Parquet 적재
        run_silver = BashOperator(
            task_id=f"run_silver_{task_key}",
            bash_command=f"cd {PROJECT_ROOT_DIR} && export PYTHONPATH={PROJECT_ROOT_DIR} && python -m src.main",
            env={
                "EXECUTION_DATE": "{{ data_interval_start.in_timezone(dag.timezone).strftime('%Y%m%d') }}",
                "TARGET_TASK": f"silver_{task_key}"
            },
            append_env=True,
        )

        # 2. Gold Task : Silver Parquet 판독(20일 윈도우 역산) -> 18대 다형성 전처리 -> Gold Parquet 일별 적재
        run_gold = BashOperator(
            task_id=f"run_gold_{task_key}",
            bash_command=f"cd {PROJECT_ROOT_DIR} && export PYTHONPATH={PROJECT_ROOT_DIR} && python -m src.main",
            env={
                "EXECUTION_DATE": "{{ data_interval_start.in_timezone(dag.timezone).strftime('%Y%m%d') }}",
                "TARGET_TASK": f"gold_{task_key}"
            },
            append_env=True,
        )

        # 3. Task 의존성 제어 (Bronze 제외, Silver 완료 후 Gold 실행)
        run_silver >> run_gold

    return dag


# ==============================================================================
# [DAG Instances Generation (2016 ~ 2026)]
# ==============================================================================
# 자정(00:00) 실행 시 전일(T-1) 데이터를 처리하므로,
# YYYY0101 데이터를 처리하기 위해 start_date는 YYYY-01-02로 지정하고,
# YYYY1231 데이터를 처리하기 위해 end_date는 (YYYY+1)-01-01로 지정합니다.
for target_year in TARGET_YEARS:
    # 1. Asia 실버/골드 백필 파이프라인 (KST 00:00)
    globals()[f"backfill_silver_gold_asia_{target_year}_dag"] = create_silver_gold_backfill_dag(
        dag_id=f"backfill_silver_gold_asia_{target_year}",
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

    # 2. Global 실버/골드 백필 파이프라인 (EST 00:00)
    globals()[f"backfill_silver_gold_global_{target_year}_dag"] = create_silver_gold_backfill_dag(
        dag_id=f"backfill_silver_gold_global_{target_year}",
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