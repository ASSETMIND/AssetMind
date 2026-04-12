"""
애플리케이션 전역에서 발생하는 이벤트를 체계적으로 기록하고 관리하는 싱글톤 기반 로깅 모듈입니다.
단순 텍스트 로그 대신, ELK Stack(Elasticsearch, Logstash, Kibana)이나 AWS CloudWatch와 같은 
중앙화된 로그 수집 시스템이 즉시 파싱할 수 있는 JSON 포맷(Structured Logging)을 표준으로 채택했습니다.

[전체 데이터 흐름 (Input -> Output)]
1. Application Log Call: 애플리케이션 내 로거 호출 (예: `logger.info("message")`)
2. ContextFilter: AsyncIO 또는 Thread Context에서 고유 Request ID를 추출하여 LogRecord에 주입
3. Formatter 처리:
   - 로그 메타데이터(Level, Message, File, Line 등) 추출
   - [Standardization] 시스템 처리를 위한 UTC ISO 8601 시간 포맷 적용
   - [Usability] 개발자 디버깅 편의를 위한 KST(한국 시간) 필드 별도 생성
   - [Safety] 직렬화 불가능한 객체의 자동 문자열 변환(Fail-Safe) 처리
4. Handlers 분배:
   - ConsoleHandler: 표준 출력(stdout)으로 ANSI 색상 적용 텍스트 전송 (개발/컨테이너 모니터링용)
   - TimedRotatingFileHandler: 로컬 파일 시스템에 JSON 포맷으로 일자별 로그 아카이빙 (백업 및 수집기 연동용)

주요 기능:
- [Context Isolation] 비동기 요청(Task) 간 로그 섞임 방지를 위한 Request ID 멱등성 추적
- [Dual Timezone Strategy] 글로벌 표준(UTC)과 로컬 운영 편의성(KST) 동시 지원
- [Crash Prevention] JSON 직렬화 실패로 인한 애플리케이션 중단 방지 로직 (Fail-Safe)
- [Thread Safety] 멀티스레드 환경에서도 안전한 Singleton 초기화 (Double-Checked Locking 패턴)

Trade-off:
1. UTC vs KST (Timezone Strategy):
   - 장점: 글로벌 인프라 표준(UTC) 정합성과 국내 운영 편의성(KST)을 동시에 충족함.
   - 단점: 로그 페이로드 사이즈의 미세한 증가 및 시간 변환 연산에 따른 마이크로초 단위 오버헤드.
   - 근거: 서버 인프라와 중앙 로그 시스템은 UTC 기준으로 동작해야 데이터가 꼬이지 않으나, 실제 장애 발생 시 디버깅을 수행하는 엔지니어에게는 KST가 직관적임. 스토리지 비용을 약간 감수하더라도 MTTR(평균 복구 시간) 단축을 통한 운영 효율성(Operational Efficiency)을 극대화함.
2. JSON Logging vs Text Logging (File Handler):
   - 장점: 로그 수집 에이전트(Fluentd 등)에서 정규표현식(Regex) 기반 파싱 비용을 제거하고 데이터 유실을 방지함.
   - 단점: `json.dumps` 호출에 따른 CPU 연산 비용 발생.
   - 근거: 현대 MSA 및 대용량 데이터 파이프라인 환경에서는 가시성(Observability) 확보가 필수적임. 텍스트 로그 파싱의 취약점을 제거하기 위해 직렬화 비용을 지불하는 것이 시스템 안정성 면에서 압도적으로 유리함.
3. Crash Safety (default=str in json.dumps):
   - 장점: 직렬화 불가능한 객체(Custom Object 등)가 인자로 넘어와도 프로세스가 패닉(Panic)에 빠지지 않음.
   - 단점: 원본 객체의 상세한 내부 구조(Deep Structure)를 잃고 메모리 주소 문자열만 남을 수 있음.
   - 근거: "로깅 시스템의 실패가 메인 비즈니스 로직(ETL 등)을 중단시켜서는 안 된다"는 핵심 방어적 프로그래밍 원칙 준수.
"""

import json
import logging
import os
import re
import socket
import sys
import threading
import uuid
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from src.common.exceptions import ETLError

# ==============================================================================
# [Configuration] Constants
# ==============================================================================
# [설계 의도] ContextVar에서 Request ID를 식별하기 위한 고유 키.
CTX_KEY_REQUEST_ID: str = "request_id"

# [설계 의도] 로그 파일 입출력 시 한글 깨짐 방지를 위한 명시적 인코딩 강제.
DEFAULT_ENCODING: str = "utf-8"

# [설계 의도] 분산 환경에서 어느 노드에서 발생한 로그인지 식별하기 위한 메타데이터.
HOSTNAME: str = socket.gethostname()

# [설계 의도] 단일 노드 내 다중 워커 환경에서 충돌 및 병목을 추적하기 위한 프로세스 ID.
PROCESS_ID: int = os.getpid()

# [설계 의도] 한국 시간(KST)을 표준 UTC 객체로부터 안전하게 파생시키기 위한 타임존 오프셋(UTC+9) 상수.
KST_TIMEZONE: timezone = timezone(timedelta(hours=9))

# [설계 의도] AsyncIO 기반 비동기 환경에서 현재 실행 중인 Task의 컨텍스트(Request ID)를 
# 전역적으로 안전하게 격리 및 유지하기 위한 ContextVar 인스턴스. 초기값은 'system'.
request_id_ctx: ContextVar[str] = ContextVar(CTX_KEY_REQUEST_ID, default="system")


# ==============================================================================
# Log Filters & Formatters
# ==============================================================================
class ContextFilter(logging.Filter):
    """로그 레코드(LogRecord) 객체에 현재 실행 컨텍스트(Request ID 및 한국 시간)를 동적으로 주입하는 필터."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """LogRecord 객체에 사용자 정의 속성을 추가합니다.

        Args:
            record (logging.LogRecord): 로깅 파이프라인을 통과 중인 현재 로그 레코드.

        Returns:
            bool: 항상 True를 반환하여 로그가 파이프라인을 계속 통과하도록 허용.
        """
        # [설계 의도] ContextVar에서 추출한 고유 ID를 레코드에 심어, Formatter가 쉽게 접근하도록 함.
        record.request_id = request_id_ctx.get()
        
        # [설계 의도] 모든 포매터(Text, JSON)가 한국 시간을 중복 계산하지 않고 사용할 수 있도록 필터 단에서 사전 연산 후 주입.
        dt_kst = datetime.fromtimestamp(record.created, tz=KST_TIMEZONE)
        record.korean_time = dt_kst.strftime("%Y-%m-%d %H:%M:%S")
        return True


class JsonFormatter(logging.Formatter):
    """기계(Machine) 파싱 및 로그 수집기(ELK/Datadog 등) 적재를 위한 JSON 포매터."""
    
    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """표준 타임스탬프를 UTC 기반 ISO 8601 포맷으로 변환합니다.

        Args:
            record (logging.LogRecord): 현재 로그 레코드.
            datefmt (Optional[str], optional): 사용하지 않음 (오버라이딩 시그니처 유지용). Defaults to None.

        Returns:
            str: "YYYY-MM-DDTHH:MM:SS.mmmmmmZ" 형태의 ISO 포맷 문자열.
        """
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 최종 JSON 텍스트로 직렬화합니다.

        Args:
            record (logging.LogRecord): 현재 로그 레코드.

        Returns:
            str: JSON 직렬화된 로그 페이로드 문자열.
        """
        log_record: Dict[str, Any] = {
            "time": self.formatTime(record),
            "korean_time": getattr(record, "korean_time", "unknown"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "unknown"),
            "file": record.filename,
            "line": record.lineno,
            "host": HOSTNAME,
            "pid": PROCESS_ID
        }
        
        # [설계 의도] 예외 발생 시 ETLError 계열인지 파악하여 구조화된 에러 데이터를 병합하고,
        # 일반 Exception일 경우 스택 트레이스를 안전하게 추출함.
        if record.exc_info:
            _, exc_value, _ = record.exc_info
            if isinstance(exc_value, ETLError):
                log_record.update(exc_value.to_dict())
                log_record["stack_trace"] = self.formatException(record.exc_info)
            else:
                log_record["exception"] = self.formatException(record.exc_info)
            
        try:
            # [설계 의도] `ensure_ascii=False`를 통해 한글 깨짐을 방지하고, 
            # `default=str`를 통해 직렬화 불가 객체(예: 커스텀 클래스 인스턴스)에 의한 시스템 크래시를 방지(Fail-Safe).
            return json.dumps(log_record, ensure_ascii=False, default=str)
        except Exception:
            # 극한의 예외 상황(str 변환조차 실패하는 등)을 대비한 최후의 보루.
            return json.dumps({
                "level": "ERROR",
                "message": "치명적 오류: 로그 메시지 직렬화 실패",
                "raw_message": str(record.getMessage())
            })


class ColorFormatter(logging.Formatter):
    """로컬 개발 및 컨테이너 로그 모니터링 시 가독성을 극대화하기 위한 ANSI 색상 적용 텍스트 포매터."""
    
    COLORS: Dict[str, str] = {
        "DEBUG": "\033[90m",      # 회색
        "INFO": "\033[32m",       # 녹색
        "WARNING": "\033[33m",    # 노란색
        "ERROR": "\033[31m",      # 빨간색
        "CRITICAL": "\033[1;31m"  # 굵은 빨간색
    }
    RESET: str = "\033[0m"
    DIM: str = "\033[90m"
    BOLD: str = "\033[1m"
    
    # [설계 의도] 트랜잭션 생명주기 가독성을 높이기 위한 포인트 컬러 정의
    START_COLOR: str = "\033[36m" # Cyan
    END_COLOR: str = "\033[35m"   # Magenta
    SUMMARY_COLOR: str = "\033[1;94m" # Bright Blue

    def _format_name_to_pascal(self, name: str) -> str:
        """스네이크 케이스로 들어온 모듈명을 시각적 일관성을 위해 파스칼 케이스로 변환합니다.

        Args:
            name (str): 원본 모듈명 (예: pipeline_service)

        Returns:
            str: 파스칼 케이스로 변환된 모듈명 (예: PipelineService)
        """
        # [설계 의도] KISAuth처럼 이미 Camel/Pascal 형태이거나 언더바가 없는 경우, 첫 글자만 대문자로 보장.
        # 언더바가 있는 경우(pipeline_service) 각 단어를 Capitalize 처리하여 결합함.
        if "_" in name:
            return "".join(word.capitalize() for word in name.split("_"))
        return name[0].upper() + name[1:] if name else name

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드에 레벨별 ANSI 색상을 입혀 터미널 친화적 문자열로 변환합니다."""
        color = self.COLORS.get(record.levelname, self.RESET)
        
        # 1. 시간 표시 (가독성을 위해 Dim 회색 처리)
        time_str = f"{self.DIM}[{getattr(record, 'korean_time', '')}]{self.RESET}"
        
        # 2. 레벨 표시 (가장 눈에 띄어야 하므로 색상 적용)
        level_str = f"{color}{record.levelname:^7}{self.RESET}"
        
        # 3. 모듈 이름 단축 및 파스칼 케이스 통일
        short_name = record.name.split('.')[-1]
        pascal_name = self._format_name_to_pascal(short_name)
        name_str = f"{pascal_name:<20}"
        
        # 4. Request ID 단축 (터미널에서 전체 UUID는 노이즈이므로 앞 8자리만 출력)
        raw_req_id = getattr(record, 'request_id', 'system')
        short_req_id = raw_req_id[:8] if raw_req_id != "system" else "system"
        req_id = f"{self.DIM}[{short_req_id:^8}]{self.RESET}"
        
        # 5. 메시지 포매팅
        msg = record.getMessage()

        # [설계 의도] 에러/경고 발생 시 Raw Dictionary 포맷의 노이즈를 제거하고 가독성을 극대화
        if record.levelno >= logging.WARNING:
            # 5-1. 딕셔너리 형태의 문자열(dict string) 클렌징
            # 패턴: {'error_type': 'XXX', 'message': 'YYY', ...} -> [XXX] YYY
            msg = re.sub(
                r"\{'?error_type'?:\s*['\"]([^'\"]+)['\"],\s*'?message'?:\s*['\"]([^'\"]+)['\"].*?(?:\}|$)", 
                r"[\1] \2", 
                msg
            )

            # 5-2. log_decorator에서 주입한 상세 Details 파트 잘라내기
            if " | Details: " in msg:
                msg = msg.split(" | Details: ")[0]
                
            # 5-3. 콘솔 가독성을 위한 최종 길이 제한 (Fail-Safe)
            if len(msg) > 100:
                msg = msg[:100] + "..."
                
            # 5-4. 안내 문구 일괄 병합 (메시지 처리가 끝난 후 마지막에 한 번만 붙임)
            msg += f" {self.DIM}(상세 내용은 JSON 파일 참조){self.RESET}"

        # 6. 레벨별 하이라이팅 적용
        if record.levelno >= logging.ERROR:
            # 에러 발생 시 전체 붉은색 렌더링
            msg = f"{color}{msg}{self.RESET}"
        elif record.levelno == logging.WARNING:
            msg = f"{color}{msg}{self.RESET}"
        elif record.levelno == logging.INFO:
            # 전체 작업의 성공/실패 여부를 요약하는 핵심 지표(Summary) 메시지 강조
            if "요약" in msg:
                msg = f"{self.SUMMARY_COLOR}{msg}{self.RESET}"
            else:
                # 일반 INFO 로그 내 생명주기 마일스톤 강조
                if "START" in msg:
                    msg = msg.replace("START", f"{self.START_COLOR}{self.BOLD}START{self.RESET}")
                if "END |" in msg:
                    msg = msg.replace("END |", f"{self.END_COLOR}{self.BOLD}END{self.RESET} |")

        return f"{time_str} {level_str} | {name_str} | {req_id} {msg}"


# ==============================================================================
# [Main Class] LogManager
# ==============================================================================
class LogManager:
    """애플리케이션 전역 로깅 환경을 통제하는 Singleton 매니저 클래스."""
    
    _instance: Optional["LogManager"] = None
    _initialized: bool = False
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "LogManager":
        """Double-Checked Locking 패턴을 사용하여 멀티스레드 환경에서 안전한 싱글톤 인스턴스 생성을 보장합니다."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(LogManager, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """환경 설정(Config)을 불러와 로거 레벨 및 핸들러(Console, File)를 초기 세팅합니다."""
        # [설계 의도] 싱글톤이므로 __init__이 여러 번 호출되더라도 초기화는 단 한 번만 수행되도록 방어.
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return

            # [설계 의도] 모듈 최상단에서 ConfigManager를 임포트하면 순환 참조(Circular Import)
            # 문제가 발생할 위험이 있으므로, 초기화 시점에 지연 임포트(Lazy Import)를 수행함.
            from src.common.config import ConfigManager
            
            if ConfigManager._cache:
                config = next(iter(ConfigManager._cache.values()))
            else:
                config = ConfigManager()
                
            self.task_name: str = getattr(config, "task_name", "APP")
            self.log_level: str = getattr(config, "log_level", "INFO")
            self.log_dir_path: str = getattr(config, "log_dir", "logs")
            self.log_filename: str = getattr(config, "log_filename", "app.log")

            self.logger: logging.Logger = logging.getLogger(self.task_name)
            self.logger.setLevel(self.log_level)
            
            # [설계 의도] 상위 로거(Root Logger)로 이벤트가 전파되어 로그가 중복 출력되는 현상 방지.
            self.logger.propagate = False

            ctx_filter = ContextFilter()

            # 핸들러 중복 부착 방지
            if not self.logger.handlers:
                # 1. 터미널(Console) 핸들러 세팅: 사람이 읽기 편한 Color Text 포맷
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(ColorFormatter())
                console_handler.addFilter(ctx_filter)
                self.logger.addHandler(console_handler)

                # 2. 파일(File) 핸들러 세팅: 기계가 파싱하기 편한 JSON 포맷
                self._setup_file_handler(JsonFormatter(), ctx_filter)

            self._initialized = True

    def _setup_file_handler(self, formatter: logging.Formatter, filter_: logging.Filter) -> None:
        """일자별로 파일이 롤링(Rolling)되는 핸들러를 구성하여 로거에 부착합니다.

        Args:
            formatter (logging.Formatter): 파일 출력용 포매터 (주로 JsonFormatter).
            filter_ (logging.Filter): 컨텍스트 주입용 필터.
        """
        log_dir = Path(self.log_dir_path)
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file_path = log_dir / self.log_filename
            
            # [설계 의도] 자정(midnight) 기준으로 로그 파일을 분리하고 최대 7일간 보관하여
            # 서버 스토리지(디스크 공간) 고갈(OOM)을 방지함.
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
            # [설계 의도] 파일 시스템 권한 문제 등으로 파일 핸들러 생성에 실패하더라도,
            # 애플리케이션 전체가 죽지 않고 표준 에러로 원인만 남기도록 Fail-Safe 처리. (print 금지 원칙 준수)
            sys.stderr.write(f"[LogManager] 치명적 오류: 파일 핸들러 설정 실패. {e}\n")

    @classmethod
    def get_logger(cls, name: Optional[str] = None) -> logging.Logger:
        """초기화된 로거 인스턴스(또는 Child Logger)를 반환합니다.

        Args:
            name (Optional[str], optional): 하위 모듈 식별용 로거 이름. Defaults to None.

        Returns:
            logging.Logger: 사용할 준비가 완료된 로거 인스턴스.
        """
        manager = cls()
        if name:
            return manager.logger.getChild(name)
        return manager.logger

    @staticmethod
    def set_context(request_id: Optional[str] = None) -> str:
        """현재 실행 컨텍스트에 고유 Request ID를 할당합니다.

        Args:
            request_id (Optional[str], optional): 명시적으로 주입할 ID. 없을 경우 UUID4로 자동 생성. Defaults to None.

        Returns:
            str: 설정된 Request ID.
        """
        if not request_id:
            request_id = str(uuid.uuid4())
        request_id_ctx.set(request_id)
        return request_id