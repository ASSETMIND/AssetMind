"""
[모듈 제목]
Infrastructure Connectivity Health Check DAG

[모듈 목적 및 상세 설명]
이 모듈은 Airflow 환경에서 외부 시스템(PostgreSQL, LocalStack 등)과의 통신 상태를 정기적으로 점검합니다.
단순 연결 확인을 넘어, 실제 Query 실행 가능 여부를 판단하여 인프라의 가용성을 보장합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Trigger: Airflow Scheduler (또는 수동 실행)
2. Process: PostgresHook을 통한 Meta DB 및 Integrated DB 세션 오픈 시도
3. Validation: 'SELECT 1' 쿼리 수행을 통한 통신 무결성 검증
4. Output: 사내 표준 로거를 통한 결과 기록 및 DAG 성공/실패 상태 업데이트

주요 기능:
- PostgreSQL(Integrated DB) 연결성 검사
- 사내 표준 로깅 데코레이터(@log_decorator)를 통한 실행 이력 관리
- Airflow UI Graph View를 통한 직관적인 인프라 상태 모니터링

Trade-off:
- 장점: 인프라 장애를 데이터 파이프라인 실행 전 조기에 감지(Fail-Fast)할 수 있으며, 장애 이력이 Airflow 메타데이터에 남으므로 사후 분석(Post-mortem)에 유리함.
- 단점: 아주 미세한 수준의 스케줄러 부하와 로그 데이터가 발생함.
- 근거: 대규모 데이터 플랫폼 운영 시 'Observability(관측 가능성)' 확보는 성능 최적화보다 우선순위가 높음.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

from src.common.log import LogManager
from src.common.decorators.log_decorator import log_decorator

# ==========================================
# Constants & Configuration
# ==========================================
# 3단계에서 생성한 Connection ID 사용
TARGET_CONN_ID: str = "postgres_conn"
DAG_ID: str = "infra_connectivity_health_check"

# ==========================================
# Logger Setup
# ==========================================
logger = LogManager.get_logger(__name__)

# ==========================================
# Custom Exceptions
# ==========================================
class DatabaseConnectivityError(Exception):
    """DB 통신 실패 시 발생하는 커스텀 예외 (ETLError로 자동 래핑됨)"""
    pass

# ==========================================
# Main Logic Functions
# ==========================================

@log_decorator(logger_name="HealthCheck", suppress_error=False)
def check_postgres_connectivity(**context: Any) -> str:
    """
    PostgresHook을 사용하여 통합 데이터베이스와의 통신을 검증합니다.

    Args:
        **context: Airflow Task Instance context

    Returns:
        str: 성공 시 상태 메시지 반환

    Raises:
        DatabaseConnectivityError: 연결 실패 또는 쿼리 실행 오류 시 발생
    """
    try:
        # 1. PostgresHook 초기화 (방어적 프로그래밍)
        hook = PostgresHook(postgres_conn_id=TARGET_CONN_ID)
        
        # 2. 실제 연결 시도 및 가벼운 쿼리 실행
        # Rationale: 연결만 확인하는 것이 아니라, 실제 데이터 Read 권한이 있는지 확인하기 위해 'SELECT 1' 수행
        connection = hook.get_conn()
        cursor = connection.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        
        if result and result[0] == 1:
            success_msg = f"[요약] DB('{TARGET_CONN_ID}') 통신 및 쿼리 실행이 정상적으로 확인되었습니다."
            logger.info(success_msg)
            return success_msg
        
        raise DatabaseConnectivityError("쿼리 결과가 예상과 다릅니다.")

    except Exception as e:
        error_msg = f"DB('{TARGET_CONN_ID}') 연결 실패: {str(e)}"
        logger.error(error_msg)
        raise DatabaseConnectivityError(error_msg) from e

# ==========================================
# DAG Definition
# ==========================================
default_args: Dict[str, Any] = {
    "owner": "DataPlatform-Admin",
    "depends_on_past": False,
    "start_date": datetime(2024, 4, 27),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description="인프라 연결성 정기 점검용 DAG",
    schedule_interval="@hourly",  # 실무에서는 시간 단위 혹은 배치 전 확인용으로 설정
    catchup=False,
    tags=["infra", "health-check", "monitoring"],
) as dag:

    test_db_connection = PythonOperator(
        task_id="check_postgres_connectivity",
        python_callable=check_postgres_connectivity,
    )

    test_db_connection