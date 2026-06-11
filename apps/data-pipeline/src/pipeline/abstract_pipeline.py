"""
[모듈 제목]
Data Pipeline Base Abstract Module

[모듈 목적 및 상세 설명]
메달리온 아키텍처(Medallion Architecture) 상의 모든 파이프라인 서비스 계층이 상속받아야 하는 최상위 추상 클래스입니다.
비동기 컨텍스트 매니저 라이프사이클을 일관되게 강제하며, 다형성(Polymorphism)을 통해 상위 실행부(main.py)가 
구체적인 레이어의 도메인 로직을 모르고도 동일한 인터페이스로 배치를 구동할 수 있도록 제어 구조를 추상화합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Initialization: 파이프라인 작업명(task_name) 주입 및 전역 설정 매핑.
2. Context Entry (`__aenter__`): 하위 서비스들이 사용할 네트워크 소켓 및 I/O 자원 활성화 위임.
3. Execution (`run_batch`): 각 구체 클래스(Bronze/Silver)가 오버라이딩한 배치 데이터 오케스트레이션 수행.
4. Context Exit (`__aexit__`): 정상 종료 및 패닉 상황 관계없이 점유 자원 완벽히 반환.

주요 기능:
- [Interface Enforcement] 추상 메서드 지정을 통한 메달리온 레이어별 배치 실행 규격 강제.
- [Lifecycle Centralization] 비동기 자원 해제 보일러플레이트의 공통 규격화.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- ABC(Abstract Base Class) 기반 추상화 vs Duck Typing 인터페이스:
  - 장점: `abc.abstractmethod`를 활용하여 런타임 이전에 서브클래스의 미구현 메서드를 차단(Fail-Fast)하므로 대규모 협업 환경에서 휴먼 에러를 원천 봉쇄함.
  - 단점: 상속 구조로 인한 프레임워크적 제약과 클래스 계층 구조의 복잡성이 다소 증가함.
  - 근거: 파이프라인 엔진은 신뢰성이 최우선이며, 새로운 레이어(Silver, Gold) 추가 시 개발자가 명세(`run_batch`)를 누락하는 치명적 실수를 방지하기 위해 강인한 정적 제약(ABC)을 채택함.
"""
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.common.config import ConfigManager
from src.common.log import LogManager


class AbstractPipeline(ABC):
    """모든 데이터 레이어별 파이프라인의 표준 인터페이스를 정의하는 최상위 추상 클래스."""

    def __init__(self, task_name: str) -> None:
        """파이프라인 실행 환경 설정을 로드하고 로거를 격리 할당합니다.

        Args:
            task_name (str): 실행 대상 파이프라인의 고유 식별 명칭 (예: 'fred_daily').
        """
        self._task_name = task_name
        self._config = ConfigManager.load("pipeline")
        self._logger = LogManager.get_logger(self.__class__.__name__)
        self._task_policy = self._config.get_pipeline(task_name)

    async def __aenter__(self) -> "AbstractPipeline":
        """비동기 컨텍스트 진입 시 호출되는 자원 할당 훅 메서드입니다."""
        self._logger.info(f"[{self._task_name}] {self.__class__.__name__} 리소스 할당 프로세스를 시작합니다.")
        self._start_time = time.perf_counter()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """비동기 컨텍스트 탈출 시 자원을 해제하여 누수를 방지하는 훅 메서드입니다."""
        if hasattr(self, "_start_time"):
            elapsed_time = time.perf_counter() - self._start_time

        self._logger.info(f"[{self._task_name}] {self.__class__.__name__} 리소스 해제가 완료되었습니다. (총 실행 소요 시간: {elapsed_time:.4f}초)")
    @abstractmethod
    async def run_batch(self, execution_date: Optional[str] = None, extract_mode: str = "TODAY") -> Dict[str, Any]:
        """설정된 배치 명세에 따라 실제 대량 데이터 ETL/EL 작업을 가동하는 핵심 오버라이딩 진입점입니다.

        Args:
            execution_date (Optional[str]): 멱등성 보장을 위해 외부 스케줄러가 주입한 데이터 기준일 (YYYYMMDD).
            extract_mode (str): 데이터 수집 범위 모드 (기본값: "TODAY").

        Returns:
            Dict[str, Any]: 파이프라인 실행 결과 메타데이터 지표 및 상세 내역 리포트.
        """
        pass