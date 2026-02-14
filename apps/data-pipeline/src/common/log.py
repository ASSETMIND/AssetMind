"""
로깅 관리 모듈 (Logging Management Module)

애플리케이션 전역에서 사용되는 로깅 시스템을 정의합니다.
단순한 텍스트 로그가 아닌, ELK Stack(Elasticsearch, Logstash, Kibana)이나 
CloudWatch와 같은 로그 수집 시스템이 파싱하기 쉬운 JSON 포맷을 사용합니다.

또한, 비동기(AsyncIO) 환경에서 여러 요청이 동시에 처리될 때, 
각 로그가 어떤 요청(Request)에 속하는지 식별하기 위해 ContextVar를 사용하여
Request ID를 추적합니다.

Classes:
    ContextFilter: 로그 레코드에 ContextVar의 Request ID를 주입하는 필터.
    JsonFormatter: 로그를 JSON 문자열로 변환하는 포매터.
    LogManager: 로거 설정을 초기화하고 인스턴스를 관리하는 싱글톤 클래스.
"""

import sys
import logging
import json
import uuid
from contextvars import ContextVar
from pathlib import Path

from src.common.config import ConfigManager

# ==============================================================================
# [Role 1] Context Variable Definition
# ==============================================================================
# 비동기 작업 흐름(Task) 간에 고유한 상태(Request ID)를 유지하기 위한 컨텍스트 변수입니다.
# 멀티스레드나 AsyncIO 환경에서도 요청 간의 로그 컨텍스트가 섞이지 않도록 보장합니다.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="system")


# ==============================================================================
# [Role 2] Log Filters & Formatters
# ==============================================================================
class ContextFilter(logging.Filter):
    """로그 레코드에 현재 실행 컨텍스트의 Request ID를 주입하는 필터.
    
    모든 로그가 출력되기 직전에 호출되며, `request_id_ctx`에 저장된 값을
    `record.request_id` 속성으로 주입하여 Formatter에서 사용할 수 있게 합니다.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """로그 레코드 필터링 및 속성 주입을 수행합니다.

        Args:
            record (logging.LogRecord): 현재 처리 중인 로그 레코드 객체.

        Returns:
            bool: 항상 True를 반환하여 모든 로그가 통과되도록 합니다.
        """
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    """로그를 구조화된 JSON 포맷으로 변환하는 커스텀 포매터.
    
    사람이 읽기 위한 텍스트 형식이 아닌, 기계가 파싱하기 최적화된 JSON 문자열을 생성합니다.
    분산 환경에서의 트레이싱과 로그 분석 효율성을 높여줍니다.
    """

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 JSON 문자열로 직렬화합니다.

        Args:
            record (logging.LogRecord): 로그 레코드 객체.

        Returns:
            str: JSON 포맷팅된 로그 문자열.
        """
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "unknown"),
            "file": record.filename,
            "line": record.lineno,
        }
        
        # 예외(Exception) 정보가 포함된 경우(Stack Trace), 별도 필드에 담습니다.
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record, ensure_ascii=False)


# ==============================================================================
# [Role 3] LogManager (Singleton)
# ==============================================================================
class LogManager:
    """애플리케이션 전역 로거를 관리하는 싱글톤(Singleton) 클래스.
    
    최초 1회 초기화 시 설정(Config)을 로드하여 핸들러(Console, File)를 부착하고,
    JSON 포맷터와 Context 필터를 적용합니다.
    """
    
    _instance = None
    _initialized = False

    def __new__(cls):
        """싱글톤 패턴: 인스턴스가 메모리에 없을 때만 생성합니다."""
        if cls._instance is None:
            cls._instance = super(LogManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """로거 초기화 및 핸들러 설정을 수행합니다."""
        if self._initialized:
            return
        
        # 1. 설정 로드 (Configuration Loading)
        # ConfigManager를 통해 통합 설정 객체(ConfigManager)를 가져옵니다.
        config = ConfigManager.get_config()

        # 설정 객체로부터 로깅에 필요한 속성을 추출합니다.
        task_name = getattr(config, "task_name", "TASK_DEFAULT")
        log_level = getattr(config, "log_level", "INFO")
        log_dir_path = getattr(config, "log_dir", "logs")

        # 2. 루트 로거 설정 (Root Logger Setup)
        # 프로젝트 전용 로거를 생성하고, 전파(Propagation)를 막아 중복 출력을 방지합니다.
        self.logger = logging.getLogger(task_name)
        self.logger.setLevel(log_level)
        self.logger.propagate = False

        # 공통 컴포넌트 생성
        json_formatter = JsonFormatter()
        ctx_filter = ContextFilter()

        # 3. 콘솔 핸들러 설정 (Console Handler)
        # Docker/Kubernetes 환경에서는 표준 출력(stdout)으로 로그를 내보내는 것이 표준입니다.
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(json_formatter)
        console_handler.addFilter(ctx_filter)
        self.logger.addHandler(console_handler)

        # 4. 파일 핸들러 설정 (File Handler)
        # 로컬 환경에서의 디버깅이나 로그 영구 저장을 위해 파일로도 기록합니다.
        log_dir = Path(log_dir_path)
        try:
            # parents=True를 통해 상위 디렉토리(logs)가 없어도 생성되도록 보장
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_file_path = log_dir / "app.log"
            file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
            file_handler.setFormatter(json_formatter)
            file_handler.addFilter(ctx_filter)
            self.logger.addHandler(file_handler)
            
            # 로그 파일 생성 위치를 명시적으로 알림
            print(f" [LogManager] Log file created at: {log_file_path.absolute()}")
            
        except Exception as e:
            print(f" [LogManager] Failed to create log file handler: {e}")

        self._initialized = True

    @classmethod
    def get_logger(cls, name: str = None) -> logging.Logger:
        """설정된 로거 인스턴스를 반환하는 팩토리 메서드.

        Args:
            name (str, optional): 하위 로거(Child Logger)의 이름. 
                                  지정 시 'TaskName.ChildName' 형태로 반환됩니다.

        Returns:
            logging.Logger: 설정이 완료된 로거 객체.
        """
        manager = cls()
        if name and name != manager.logger.name:
            return manager.logger.getChild(name)
        return manager.logger

    @staticmethod
    def set_context(request_id: str = None) -> str:
        """새로운 작업 컨텍스트 시작 시 Request ID를 설정합니다.
        
        API 요청 진입점(Entrypoint)이나 배치 작업 시작 시 호출하여
        해당 작업 흐름 전체에서 동일한 Request ID를 공유하도록 합니다.

        Args:
            request_id (str, optional): 지정할 Request ID. 없으면 UUID v4를 생성합니다.

        Returns:
            str: 설정된 Request ID.
        """
        if not request_id:
            request_id = str(uuid.uuid4())
        
        request_id_ctx.set(request_id)
        return request_id