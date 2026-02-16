"""
로깅 관리 모듈 (Logging Management Module)

애플리케이션 전역에서 발생하는 이벤트를 체계적으로 기록하고 관리하는 모듈입니다.
단순 텍스트 로그 대신, ELK Stack(Elasticsearch, Logstash, Kibana)이나
AWS CloudWatch와 같은 중앙화된 로그 수집 시스템이 즉시 파싱할 수 있는
JSON 포맷(Structured Logging)을 표준으로 채택했습니다.

[전체 데이터 흐름 (Input -> Output)]
1. Application Log Call: 로거 호출 (logger.info("message"))
2. ContextFilter: AsyncIO/Thread Context에서 고유 Request ID 추출 및 주입
3. JsonFormatter:
   - 로그 메타데이터(Level, Message, File 등) 추출
   - [Standardization] 시스템 처리를 위한 UTC ISO 8601 시간 포맷 적용
   - [Usability] 개발자 디버깅 편의를 위한 KST(한국 시간) 필드 별도 생성
   - [Safety] 직렬화 불가능한 객체의 자동 문자열 변환 처리
4. Handlers:
    - ConsoleHandler: 표준 출력(stdout)으로 JSON 전송 (Container/Kubernetes 환경 표준)
    - TimedRotatingFileHandler: 로컬 파일 시스템에 일자별 로그 아카이빙 (Backup)

주요 기능:
- [Context Isolation] 비동기 요청(Task) 간 로그 섞임 방지를 위한 Request ID 추적
- [Dual Timezone Strategy] 글로벌 표준(UTC)과 로컬 운영 편의성(KST) 동시 지원
- [Crash Prevention] JSON 직렬화 실패로 인한 애플리케이션 중단 방지 로직 (Fail-Safe)
- [Thread Safety] 멀티스레드 환경에서도 안전한 Singleton 초기화 (Double-Checked Locking)

Trade-off & Design Decisions:
1. UTC vs KST (Timezone Strategy):
   - 결정: `time`(UTC)과 `korean_time`(KST) 필드를 동시에 기록.
   - 근거: 서버 인프라와 로그 수집 시스템은 글로벌 표준인 UTC를 기준으로 동작해야 데이터 정합성이 유지됨.
     반면, 실제 운영 및 디버깅을 담당하는 개발자는 KST가 직관적임.
     약간의 데이터 사이즈 증가(Overhead)를 감수하고, 운영 효율성(Operational Efficiency)을 극대화함.

2. JSON Logging vs Text Logging:
   - 결정: JSON 포맷 사용.
   - 근거: 텍스트 파싱(Regex) 비용을 제거하고, 로그 수집 파이프라인에서의 데이터 유실을 방지함.
     `json.dumps` 연산 비용이 발생하지만, Observability 확보가 현대 MSA 환경에서 더 중요함.

3. Crash Safety (default=str):
   - 결정: JSON 직렬화 실패 시 에러를 뱉는 대신 `str()`로 변환하여 기록.
   - 근거: "로깅 실패가 비즈니스 로직을 중단시켜선 안 된다"는 원칙 준수.
"""

import sys
import logging
import json
import uuid
import socket
import os
import threading
from datetime import datetime, timedelta, timezone
from contextvars import ContextVar
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from typing import Optional, Dict, Any

# ==============================================================================
# [Dependency] External Configuration
# ==============================================================================
# 설정 모듈 의존성. 부재 시 ImportError를 발생시켜 배포 시점에 문제를 인지하도록 함(Fail Fast).
from src.common.config import ConfigManager
from src.common.exceptions import ETLError

# ==============================================================================
# Constants & Configuration
# ==============================================================================
CTX_KEY_REQUEST_ID = "request_id"
DEFAULT_ENCODING = "utf-8"

# [Metadata Optimization]
# 호스트명과 PID는 런타임 중 변하지 않으므로 모듈 로드 시점에 1회만 연산하여 캐싱합니다.
# 이는 매 로그 기록 시 발생하는 불필요한 System Call(syscall)을 제거합니다.
HOSTNAME = socket.gethostname()
PROCESS_ID = os.getpid()

# ==============================================================================
# [Role 1] Context Variable Definition
# ==============================================================================
# AsyncIO 및 멀티스레드 환경에서 각 요청의 고유 ID를 안전하게 격리/전달하기 위한 변수
request_id_ctx: ContextVar[str] = ContextVar(CTX_KEY_REQUEST_ID, default="system")


# ==============================================================================
# [Role 2] Log Filters & Formatters
# ==============================================================================
class ContextFilter(logging.Filter):
    """로그 레코드에 현재 실행 컨텍스트의 Request ID를 주입하는 필터."""

    def filter(self, record: logging.LogRecord) -> bool:
        # ContextVar에서 값 추출 -> LogRecord 속성으로 주입
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    """로그를 구조화된 JSON 포맷으로 변환하는 커스텀 포매터.
    
    [Dual Timezone Strategy 적용]
    - time: UTC (시스템 표준, 로그 수집기 인덱싱용)
    - korean_time: KST (사람의 눈으로 확인하는 디버깅용)
    """

    # KST 타임존 상수 (UTC+9) 미리 정의
    KST_TIMEZONE = timezone(timedelta(hours=9))

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """타임존 혼동 방지를 위해 UTC 시간을 ISO 8601 포맷(Z 접미사)으로 반환합니다."""
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 JSON 문자열로 직렬화합니다."""
        
        # 1. UTC 시간 (Standard)
        utc_time = self.formatTime(record)
        
        # 2. KST 시간 (Human Readable)
        dt_kst = datetime.fromtimestamp(record.created, tz=self.KST_TIMEZONE)
        kst_time_str = dt_kst.strftime("%Y-%m-%d %H:%M:%S")

        # 3. 로그 데이터 구성
        log_record: Dict[str, Any] = {
            "time": utc_time,             # 기계용 (UTC ISO8601)
            "korean_time": kst_time_str,  # 사람용 (KST Local)
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "unknown"),
            "file": record.filename,
            "line": record.lineno,
            "host": HOSTNAME,    # 인프라 레벨 식별자 (어느 서버인가?)
            "pid": PROCESS_ID    # 프로세스 레벨 식별자 (어느 워커인가?)
        }
        
        # 4. Exception 정보 처리 (ETLError의 구조화된 필드 우선)
        if record.exc_info:
            _, exc_value, _ = record.exc_info
            
            # ETLError인 경우 to_dict()의 구조화된 필드를 로그 최상위에 병합
            if isinstance(exc_value, ETLError):
                log_record.update(exc_value.to_dict())
                # 스택 트레이스는 별도 필드로 분리하여 가독성 확보
                log_record["stack_trace"] = self.formatException(record.exc_info)
            else:
                # 일반 예외는 기존 방식 유지
                log_record["exception"] = self.formatException(record.exc_info)
            
        try:
            # [Fail-Safe] default=str 옵션을 통해 직렬화 불가능 객체(Set, Object 등)가 와도
            # 에러를 내지 않고 문자열로 변환하여 로깅을 성공시킴. (매우 중요)
            return json.dumps(log_record, ensure_ascii=False, default=str)
        except Exception:
            # JSON 변환조차 실패하는 최악의 경우, 안전한 텍스트로 폴백하여 시스템 크래시 방지
            return json.dumps({
                "level": "ERROR",
                "message": "치명적 오류: 로그 메시지 직렬화 실패",
                "raw_message": str(record.getMessage())
            })


# ==============================================================================
# [Role 3] LogManager (Singleton)
# ==============================================================================
class LogManager:
    """애플리케이션 전역 로거를 관리하는 Thread-Safe 싱글톤 클래스.
    
    설계 의도:
    - 프로그램 생명주기 내 단일 로거 인스턴스 보장.
    - Double-Checked Locking 패턴을 사용하여 멀티스레드 환경에서도 안전하게 초기화.
    """
    
    _instance: Optional["LogManager"] = None
    _initialized: bool = False
    _lock: threading.Lock = threading.Lock() # 초기화 동시성 제어용 Lock

    def __new__(cls) -> "LogManager":
        if cls._instance is None:
            with cls._lock:
                # Lock 획득 후 다시 확인 (Double-Check)
                if cls._instance is None:
                    cls._instance = super(LogManager, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """설정을 로드하고 핸들러를 부착합니다. (1회만 실행됨)"""
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return

            # 1. Configuration Loading
            config = ConfigManager.get_config()
            self.task_name = getattr(config, "task_name", "APP")
            self.log_level = getattr(config, "log_level", "INFO")
            self.log_dir_path = getattr(config, "log_dir", "logs")
            self.log_filename = getattr(config, "log_filename", "app.log")

            # 2. Root Logger Setup
            self.logger = logging.getLogger(self.task_name)
            self.logger.setLevel(self.log_level)
            self.logger.propagate = False

            # 공통 컴포넌트
            json_formatter = JsonFormatter()
            ctx_filter = ContextFilter()

            # 3. Handler Setup (중복 방지)
            if not self.logger.handlers:
                # [Console Handler] stdout -> Docker/K8s Log Collector
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(json_formatter)
                console_handler.addFilter(ctx_filter)
                self.logger.addHandler(console_handler)

                # [File Handler] Local Backup -> Disk Full 방지(Rotation)
                self._setup_file_handler(json_formatter, ctx_filter)

            self._initialized = True

    def _setup_file_handler(self, formatter: logging.Formatter, filter_: logging.Filter) -> None:
        """파일 핸들러(TimedRotatingFileHandler)를 안전하게 설정합니다."""
        log_dir = Path(self.log_dir_path)
        
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file_path = log_dir / self.log_filename
            
            # 매일 자정(midnight)에 로그 파일을 회전시키고, 최근 7일치만 보관
            file_handler = TimedRotatingFileHandler(
                filename=log_file_path,
                when="midnight",
                interval=1,
                backupCount=7,
                encoding=DEFAULT_ENCODING
            )
            file_handler.setFormatter(formatter)
            file_handler.addFilter(filter_)
            self.logger.addHandler(file_handler)
            
        except OSError as e:
            # 파일 시스템 권한 문제 등으로 실패 시 stderr로 경고 (App Crash 방지)
            sys.stderr.write(f"[LogManager] 치명적 오류: 파일 핸들러 설정 실패. {e}\n")

    @classmethod
    def get_logger(cls, name: Optional[str] = None) -> logging.Logger:
        """설정된 로거 인스턴스를 반환합니다."""
        manager = cls()
        if name:
            return manager.logger.getChild(name)
        return manager.logger

    @staticmethod
    def set_context(request_id: Optional[str] = None) -> str:
        """새로운 요청 컨텍스트의 Request ID를 설정합니다."""
        if not request_id:
            request_id = str(uuid.uuid4())
        request_id_ctx.set(request_id)
        return request_id