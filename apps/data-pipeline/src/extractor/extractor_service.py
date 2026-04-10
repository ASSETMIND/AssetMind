"""
상위 파이프라인(Pipeline Layer)과 하위 데이터 수집기(Extractor Layer) 군을 중재하는 Facade 패턴의 서비스 계층입니다.
개별 수집 요청(Single) 및 일괄 병렬 요청(Batch)을 처리하며, 비동기 HTTP 클라이언트의 생명주기(Lifecycle)와 
예외 처리 로직을 중앙에서 통제하여 도메인 복잡성을 캡슐화합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 클라이언트(스케줄러/파이프라인)로부터 job_id 및 오버라이드 파라미터 유입.
2. Initialization: 비동기 컨텍스트(`async with`) 진입 시 HTTP Connection Pool 활성화.
3. Delegation: ExtractorFactory에 job_id와 HTTP 클라이언트를 전달하여 구체화된 수집기 인스턴스 획득.
4. Execution: 수집기 템플릿 메서드(`extract`) 호출 및 원본 데이터 획득.
5. Normalization: 서로 다른 Provider(KIS, UPBIT, FRED 등)의 응답 코드를 파이프라인 표준 상태('success')로 정규화.
6. Output: 부분 성공(Partial Success)이 보장된 결과 DTO 리스트 또는 단일 객체 반환.

주요 기능:
- [Lifecycle Management] 비동기 컨텍스트 매니저를 통한 HTTP 세션(Connection Pool)의 안전한 생성 및 종료.
- [Parameter Merging] Config에 정의된 정적 정책 파라미터와 런타임 동적 파라미터의 유연한 병합.
- [Concurrency] `asyncio.gather`를 활용한 다건 수집 작업의 비동기 병렬 처리.
- [Normalization] 외부 API 제공자별로 상이한 성공 코드(예: '0', '200', 'OK')를 시스템 표준 포맷으로 통일.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. Internal Lifecycle Management (owns_client):
   - 장점: 서비스 객체가 내부적으로 HTTP 클라이언트의 생성과 소멸을 직접 제어하므로 소켓 누수(Socket Leak)를 완벽히 방지함.
   - 단점: 외부에서 의존성을 주입받는 순수 DI(Dependency Injection) 방식에 비해 결합도가 미세하게 상승함.
   - 근거: 네트워크 I/O 성능 극대화를 위해 Connection Pool은 서비스 단위로 밀접하게 관리되는 것이 유리하며, 테스트 시 외부 주입을 허용하는 하이브리드 설계로 결합도 단점을 완화함.
2. Partial Success in Batch (`return_exceptions=True`):
   - 장점: 100개의 배치 수집 중 단 1개가 실패하더라도 나머지 99개의 데이터를 정상적으로 확보하여 파이프라인의 가용성(Availability)을 극대화함.
   - 단점: 호출자(Client) 측에서 반환된 리스트를 순회하며 정상 데이터와 에러 객체(Exception)를 직접 분기/필터링해야 하는 책임이 전가됨.
   - 근거: 대용량 데이터 파이프라인 환경에서는 하나의 API 지연/실패로 전체 배치가 롤백되는 'All-or-Nothing' 방식보다 부분 성공을 허용하는 'Best-Effort' 방식이 운영 효율성 측면에서 압도적으로 유리함.
"""

import asyncio
from typing import List, Dict, Optional, Any, Union, Tuple

from src.common.config import ConfigManager
from src.common.log import LogManager
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ConfigurationError, ETLError, ExtractorError

from src.common.decorators.log_decorator import log_decorator

from src.extractor.adapters.http_client import AsyncHttpAdapter
from src.extractor.extractor_factory import ExtractorFactory


class ExtractorService:
    """수집 계층(Extractor Layer)의 진입점(Entry Point) 역할을 수행하는 서비스 클래스.

    Facade 패턴을 적용하여 복잡한 하위 시스템(Factory, Auth, Http)의 상호작용을 캡슐화하고,
    클라이언트에게 단순화된 고수준 인터페이스(`extract_job`, `extract_batch`)를 제공합니다.

    Attributes:
        _config (ConfigManager): 수집 정책이 포함된 애플리케이션 전역 설정 객체.
        _logger (logging.Logger): 클래스별 격리된 로깅을 위한 인스턴스.
        _http_client (Optional[AsyncHttpAdapter]): 비동기 HTTP 요청을 처리하는 어댑터 인스턴스.
        _owns_client (bool): 클라이언트 인스턴스의 생명주기 관리 주체 여부.
                             True인 경우 서비스 종료 시 커넥션 풀을 직접 해제합니다.
    """

    def __init__(self, http_client: Optional[AsyncHttpAdapter] = None):
        """ExtractorService 인스턴스를 초기화합니다.

        Args:
            http_client (Optional[AsyncHttpAdapter], optional): 외부에서 주입된 HTTP 클라이언트.
                None일 경우 Context Manager 진입 시 내부에서 전용 클라이언트를 생성합니다. Defaults to None.
        """
        self._config = ConfigManager.load("extractor")
        self._logger = LogManager.get_logger("ExtractorService")
        
        # [설계 의도] 단위 테스트를 위한 의존성 주입(Dependency Injection)과 
        # 실제 운영 환경에서의 독립적 사용(Standalone Usage)을 모두 지원하기 위한 하이브리드 생명주기 제어.
        if http_client:
            self._http_client = http_client
            self._owns_client = False  # 외부 자원이므로 서비스가 임의로 닫지 않음
        else:
            self._http_client = None
            self._owns_client = True   # 내부 자원이므로 컨텍스트 종료 시 서비스가 회수함

    async def __aenter__(self) -> "ExtractorService":
        """비동기 컨텍스트 매니저 진입 훅(Hook). HTTP 클라이언트 연결 풀을 초기화합니다.

        Returns:
            ExtractorService: 초기화가 완료된 현재 서비스 인스턴스.
        """
        # [설계 의도] 커넥션 풀(Connection Pool)은 비용이 큰 자원이므로 인스턴스 생성 시점이 아닌, 
        # 실제 I/O가 발생하는 시점(Context Entry)에 지연 초기화(Lazy Initialization)하여 불필요한 리소스 점유를 방지함.
        if self._http_client is None and self._owns_client:
            self._http_client = AsyncHttpAdapter()
            self._logger.info("ExtractorService 내부 HTTP 클라이언트를 초기화합니다.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료 훅(Hook). 사용이 끝난 네트워크 리소스를 안전하게 정리합니다.

        Args:
            exc_type (Optional[type]): 예외 발생 시 예외 타입.
            exc_val (Optional[Exception]): 예외 발생 시 예외 객체.
            exc_tb (Optional[TracebackType]): 예외 발생 시 트레이스백 정보.
        """
        # [설계 의도] 서비스가 직접 생성한 클라이언트(_owns_client=True)인 경우에만
        # 세션을 명시적으로 닫아 메모리 누수 및 소켓 고갈(Socket Exhaustion)을 방지함.
        if self._owns_client and self._http_client:
            await self._http_client.close()
            self._logger.info("ExtractorService 내부 HTTP client 종료.")

    def _ensure_client(self):
        """HTTP 클라이언트의 초기화 상태를 강제 검증하는 Guard Clause.

        Raises:
            RuntimeError: `async with` 구문을 사용하지 않고 외부에서 메서드를 직접 호출한 경우.
        """
        if not self._http_client:
            raise RuntimeError(
                "HTTP Client is not initialized. Use 'async with ExtractorService(...) as service:' pattern."
            )

    def _normalize_response(self, response: RequestDTO) -> ExtractedDTO:
        """다양한 Provider의 이질적인 성공 응답 코드를 시스템 표준 포맷으로 통일(Normalization)합니다.
        
        [설계 의도]
        API 제공자별로 성공 코드가 상이함(KIS='0', UPBIT='OK', FRED='200').
        이를 Facade 계층에서 'status: success'로 정규화함으로써, 
        상위 파이프라인 모듈이 하위 Provider의 구체적인 구현 명세를 몰라도 되도록 정보 은닉(Information Hiding)을 달성함.

        Args:
            response (RequestDTO): 수집기(Extractor)가 반환한 원본 응답 객체.

        Returns:
            ExtractedDTO: 시스템 표준 상태 코드(status)가 맵핑된 정규화 응답 객체.
        """
        meta = response.meta
        
        # 1. Fast Path: 이미 정규화 과정을 거친 경우 즉시 반환하여 연산 비용 절감
        if meta.get("status") == "success":
            return response

        # 2. Standardization Logic: 원시 상태 코드 추출
        raw_status = meta.get("status_code")

        # [설계 의도] Robustness Logic. API 제공자 측 버그로 status_code가 결측(None)되거나 
        # 비어있는("") 상태로 200 OK 응답이 온 경우, 이를 암묵적 성공으로 간주하고 표준 코드로 자가 보정(Self-healing)함.
        if raw_status is None or raw_status == "":
            meta["status"] = "success"
            meta["status_code"] = 200
            return response

        # 상태 코드가 정수형(200)이든 문자열('OK')이든 안전하게 대조하기 위한 대문자 문자열 정규화
        status_code_str = str(raw_status).strip().upper()
        
        # 시스템 내 모든 Provider의 정상 상태 코드 집합
        SUCCESS_CODES = {"200", "0", "OK", "SUCCESS"}

        if status_code_str in SUCCESS_CODES:
            meta["status"] = "success"
        
        return response

    async def extract_job(
        self, 
        job_id: str, 
        override_params: Optional[Dict[str, Any]] = None
    ) -> ExtractedDTO:
        """단일 데이터 수집 작업을 실행하고 정규화된 응답을 반환합니다.

        Args:
            job_id (str): 실행할 수집 작업의 고유 식별자 (YAML Policy Key 매핑용).
            override_params (Optional[Dict[str, Any]], optional): 런타임에 동적으로 주입하여 정적 설정을 덮어쓸 파라미터 맵. Defaults to None.

        Returns:
            ExtractedDTO: 수집이 완료된 원본 데이터 및 정규화된 메타데이터를 포함한 DTO.

        Raises:
            ConfigurationError: 작업 ID에 해당하는 정책이 설정 파일에 없는 경우.
            ExtractorError: 수집 팩토리 조립 실패 또는 수집 과정 중 비즈니스/네트워크 에러 발생 시.
        """
        self._ensure_client()
        
        # 1. Policy Lookup
        # [설계 의도] Job ID 매핑 실패는 일시적 런타임 에러가 아니라 파이프라인의 '정적 설정 오류'이므로 
        # ConfigurationError로 분리하여 인프라 팀이 즉각 인지하도록 함.
        policy = self._config.get_extractor(job_id)
        if not policy:
            raise ConfigurationError(
                message=f"Job ID '{job_id}'를 찾을 수 없습니다.",
                key_name="job_id"
            )
        try:
            # 2. Parameter Merging
            # [설계 의도] 전역 Config 객체의 상태 불변성(Immutability)을 보장하기 위해 얕은 복사(.copy())를 수행한 뒤 덮어씀.
            final_params = policy.params.copy()
            if override_params:
                final_params.update(override_params)

            # 3. Factory Delegation
            # [설계 의도] Factory 패턴을 활용하여 구체화된 수집기 생성 책임을 위임. 
            # 서비스 계층은 오직 인터페이스(IExtractor)의 extract 메서드만 호출함.
            extractor = ExtractorFactory.create_extractor(
                job_id=job_id,
                http_client=self._http_client
            )
            
            request_dto = RequestDTO(job_id=job_id, params=final_params)
            response = await extractor.extract(request_dto)
            
            # 하위 시스템의 복잡성을 숨기고 시스템 표준 상태로 정규화하여 반환
            return self._normalize_response(response)

        except ETLError as e:
            # [설계 의도] 하위 계층에서 이미 시스템 표준 규격인 ETLError로 래핑한 예외는 중복 래핑하지 않고 그대로 전파(Bypass).
            raise e

        except Exception as e:
            # [설계 의도] 파이썬 내장 에러(KeyError 등) 발생 시 구조화된 도메인 에러(ExtractorError)로 강제 변환하여 로깅 추적성 확보.
            raise ExtractorError(
                message=f"Job '{job_id}' 작업 중 예상치 못한 오류가 발생.",
                details={
                    "job_id": job_id,
                    "step": "execution_layer",
                    "raw_error_type": type(e).__name__
                },
                original_exception=e, # 트러블슈팅을 위한 원본 콜스택 보존
            )

    @log_decorator()
    async def extract_batch(
        self, 
        job_requests: List[Union[str, Tuple[str, Dict[str, Any]]]]
    ) -> List[Union[RequestDTO, Exception]]:
        """다수의 수집 작업을 비동기 병렬로 일괄 실행합니다 (Batch Processing).

        Args:
            job_requests (List[Union[str, Tuple[str, Dict[str, Any]]]]): 실행할 수집 작업 목록. 
                - 단순 식별자: "job_id" 문자열 
                - 동적 파라미터 포함: ("job_id", {"param": "value"}) 형태의 튜플

        Returns:
            List[Union[RequestDTO, Exception]]: 병렬 수집 결과 목록.
                성공한 작업은 반환 객체가, 실패한 작업은 Exception 객체가 리스트에 포함되어 반환됨 (부분 성공 보장).
        """
        tasks = []
        
        # 1. Task Preparation
        for req in job_requests:
            if isinstance(req, str):
                tasks.append(self.extract_job(req))
            elif isinstance(req, tuple):
                tasks.append(self.extract_job(req[0], req[1]))
            else:
                self._logger.warning(f"잘못된 배치 요청 형식: {req}")
        
        if not tasks:
            return []

        # 2. Parallel Execution
        # [설계 의도] return_exceptions=True 플래그를 사용하여 특정 수집 타스크의 네트워크 실패나 파싱 예외가 
        # 전체 배치 루프를 크래시(Crash)시키지 않도록 태스크 간 격리(Isolation) 환경을 구성함.
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. Summary Logging
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        self._logger.info(f"배치 수집 요약 지표 - 총 {len(tasks)}건 중 {success_count}건 성공")
        
        return results