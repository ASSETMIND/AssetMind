"""
[모듈 제목]
Airflow PostgreSQL Connection Initialization

[모듈 목적 및 상세 설명]
이 모듈은 Airflow 환경에서 외부 데이터베이스(PostgreSQL 통합 데이터 저장소)에 연결하기 위한 
Connection(연결 정보)을 멱등성(Idempotent)을 보장하며 자동 생성 및 갱신합니다.
사내 표준 로깅 프레임워크(LogManager, log_decorator)를 연동하여 불필요한 콘솔 로그를 억제합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
Input: OS 환경변수로 주입된 PostgreSQL 인증 정보 (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)
Output: Airflow Metadata DB 내 'postgres_conn' Connection 레코드 생성 또는 업데이트

주요 기능:
- 환경변수 기반 연결 정보 동적 할당
- 중복 생성 방지를 위한 기존 Connection 존재 여부 검증 및 Upsert 로직
- 입력값 무결성 검증 (Assertion)
- @log_decorator를 통한 자동 Context 관리 및 에러(ETLError) 규격화

Trade-off: 
- 장점: 인프라 as 코드(IaC) 원칙을 준수하여 수동 설정의 휴먼 에러를 방지함. 사내 로깅 모듈을 적용하여 수백 개의 DAG 실행 시 발생하는 로그 노이즈를 최소화하고, 성공/실패 여부만 명확히 추적할 수 있음.
- 단점: Airflow 메타데이터 DB 세션을 직접 조작하므로, 향후 메이저 버전 업데이트 시 ORM API 변경 사항을 추적해야 할 수 있음.
- 근거: 데이터 엔지니어링의 핵심인 '재현성(Reproducibility)' 확보 및 운영 모니터링 피로도 감소를 위해 해당 구조 채택.
"""

import os
from typing import Optional, Tuple

from airflow.models.connection import Connection
from airflow.utils.session import create_session
from sqlalchemy.orm import Session

# 사내 표준 로깅 및 데코레이터 모듈 임포트
from src.common.log import LogManager
from src.common.log_decorator import log_decorator

# ==========================================
# Constants & Configuration
# ==========================================
CONNECTION_ID: str = "postgres_conn"
CONNECTION_TYPE: str = "postgres"
TARGET_HOST: str = "postgres"  # Docker Compose 내부 네트워크 서비스명
TARGET_PORT: int = 5432        # 내부 통신용 컨테이너 포트

# ==========================================
# Logger Setup
# ==========================================
logger = LogManager.get_logger(__name__)

# ==========================================
# Custom Exceptions
# ==========================================
class ConnectionSetupError(Exception):
    """
    비즈니스 로직에 특화된 예외 클래스.
    환경변수 누락 또는 데이터베이스 연결 생성 실패 시 발생합니다.
    이 예외는 @log_decorator에 의해 시스템 표준인 ETLError로 자동 래핑됩니다.
    """
    pass

# ==========================================
# Main Class/Functions
# ==========================================
def validate_environment_variables() -> Tuple[str, str, str]:
    """
    데이터베이스 연결에 필요한 필수 환경변수의 무결성을 검증하고 추출합니다.

    Returns:
        Tuple[str, str, str]: (사용자명, 비밀번호, 데이터베이스명) 튜플

    Raises:
        ConnectionSetupError: 하나라도 필수 환경변수가 누락된 경우 조기에 실행을 중단(Fail-Fast).
    """
    user: Optional[str] = os.getenv("POSTGRES_USER")
    password: Optional[str] = os.getenv("POSTGRES_PASSWORD")
    db_name: Optional[str] = os.getenv("POSTGRES_DB")

    if not all([user, password, db_name]):
        raise ConnectionSetupError(
            "필수 데이터베이스 환경변수(POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)가 누락되었습니다."
        )

    # 방어적 프로그래밍: Type Hinting을 만족시키기 위한 명시적 단언
    assert user is not None and password is not None and db_name is not None
    return user, password, db_name

@log_decorator(logger_name="InitPostgres", suppress_error=False)
def upsert_postgres_connection() -> None:
    """
    Airflow Meta DB에 PostgreSQL Connection 정보를 멱등성을 보장하며 삽입하거나 업데이트합니다.
    진행 과정의 노이즈 로그는 생략하고, 최종 성공 요약 로그만 출력합니다.
    
    Raises:
        ConnectionSetupError: DB 세션 처리 중 에러가 발생한 경우.
    """
    user, password, db_name = validate_environment_variables()

    try:
        with create_session() as session:
            session: Session  # Type Hinting

            # 1. 기존 Connection 존재 여부 확인
            existing_conn: Optional[Connection] = (
                session.query(Connection)
                .filter(Connection.conn_id == CONNECTION_ID)
                .first()
            )

            # 불필요한 중간 진행 로그 제거 (노이즈 최소화)
            if existing_conn:
                existing_conn.conn_type = CONNECTION_TYPE
                existing_conn.host = TARGET_HOST
                existing_conn.login = user
                existing_conn.password = password
                existing_conn.schema = db_name
                existing_conn.port = TARGET_PORT
            else:
                new_conn = Connection(
                    conn_id=CONNECTION_ID,
                    conn_type=CONNECTION_TYPE,
                    host=TARGET_HOST,
                    login=user,
                    password=password,
                    schema=db_name,
                    port=TARGET_PORT,
                )
                session.add(new_conn)
            
            # 2. 트랜잭션 커밋 및 최종 성공 "요약" 로그 출력 (ColorFormatter 연동)
            session.commit()
            logger.info(f"[요약] Airflow Connection '{CONNECTION_ID}' 갱신/생성 작업이 성공적으로 완료되었습니다.")

    except Exception as e:
        # @log_decorator가 에러를 로깅하므로, 원인을 명확히 하여 다시 던짐(Re-raise)
        raise ConnectionSetupError(f"Airflow Meta DB 세션 트랜잭션 실패: {str(e)}") from e

if __name__ == "__main__":
    # Airflow 컨테이너 내부 실행용 Entry Point
    upsert_postgres_connection()