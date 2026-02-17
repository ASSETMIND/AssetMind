"""
[데이터 수집 서비스 (Extractor Service)]

상위 파이프라인(Pipeline Layer)과 하위 수집기(Extractor Layer)를 중재하는 Facade 서비스입니다.
개별 수집 요청(Single) 및 일괄 병렬 요청(Batch)을 처리하며,
HTTP 클라이언트의 생명주기와 예외 처리를 중앙에서 관리합니다.

데이터 흐름 (Data Flow):
Client -> Service.extract_job(job_id) -> Factory.create() -> Extractor.extract() -> ResponseDTO (Normalized)

주요 기능:
- [Lifecycle Management] HTTP 세션(Connection Pool) 생성 및 종료 관리
- [Parameter Merging] Config 정책 파라미터와 런타임 파라미터의 동적 병합
- [Concurrency] asyncio.gather를 이용한 다건 수집 병렬 처리
- [Normalization] Provider별 상이한 응답 코드를 표준 상태(success)로 통일

Trade-off:
- Internal Lifecycle Management:
    - 장점: Service가 Http Client의 생성과 소멸을 제어하므로 자원 관리가 명확하고 누수가 방지됨.
    - 단점: 외부에서 주입받는 경우보다 결합도가 약간 높아짐 (Test 시 주입 가능하도록 설계하여 완화).
    - 근거: Connection Pool은 전역적으로 공유되거나 서비스 단위로 관리되는 것이 I/O 성능상 유리함.

- Partial Success in Batch:
    - 장점: 10개 중 1개가 실패해도 나머지 9개의 데이터를 확보할 수 있음 (가용성 우선).
    - 단점: 클라이언트가 반환된 리스트에서 에러 객체(Exception)를 직접 필터링해야 함.
    - 근거: 데이터 수집 파이프라인은 'All-or-Nothing'보다 'Best-Effort' 방식이 운영 효율성이 높음.
"""

import asyncio
from typing import List, Dict, Optional, Any, Union, Tuple

from src.common.config import ConfigManager
from src.common.log import LogManager
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ConfigurationError, ETLError, ExtractorError

from src.extractor.adapters.http_client import AsyncHttpAdapter
from src.extractor.extractor_factory import ExtractorFactory


class ExtractorService:
    """수집 계층(Extractor Layer)의 진입점(Entry Point) 클래스.

    Facade 패턴을 적용하여 복잡한 하위 시스템(Factory, Auth, Http)을 숨기고,
    클라이언트에게 단순화된 인터페이스(extract_job, extract_batch)를 제공합니다.

    Attributes:
        _config (ConfigManager): 애플리케이션 전역 설정 객체.
        _http_client (Optional[AsyncHttpAdapter]): HTTP 요청을 처리하는 어댑터 인스턴스.
        _owns_client (bool): 클라이언트 인스턴스의 생명주기 관리 권한 여부.
                             True인 경우 Context Manager 종료 시 세션을 닫습니다.
    """

    def __init__(
        self, 
        config: ConfigManager, 
        http_client: Optional[AsyncHttpAdapter] = None
    ):
        """ExtractorService 인스턴스를 초기화합니다.

        Args:
            config (ConfigManager): 전역 설정 객체.
            http_client (Optional[AsyncHttpAdapter]): 외부에서 주입된 HTTP 클라이언트. 
                None일 경우 Context Manager 진입 시 내부에서 생성합니다.
        """
        self._config = config
        self._logger = LogManager.get_logger("ExtractorService")
        
        # Rationale: Dependency Injection(테스트 용이성)과 
        # Standalone Usage(사용 편의성)를 모두 지원하기 위한 분기 처리입니다.
        if http_client:
            self._http_client = http_client
            self._owns_client = False  # 외부 자원이므로 서비스가 닫지 않음
        else:
            self._http_client = None
            self._owns_client = True   # 내부 자원이므로 서비스가 관리함

    async def __aenter__(self) -> "ExtractorService":
        """Async Context Manager 진입점: HTTP 클라이언트 초기화.

        Returns:
            ExtractorService: 초기화된 서비스 인스턴스.
        """
        # Rationale: Connection Pool은 비용이 큰 자원이므로, 
        # 실제 사용 시점(Context Entry)에 초기화하여 불필요한 리소스 점유를 방지합니다.
        if self._http_client is None and self._owns_client:
            self._http_client = AsyncHttpAdapter(timeout=30)
            self._logger.info("ExtractorService의 내부 HTTP client 초기화.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async Context Manager 종료점: 리소스 정리.

        Args:
            exc_type: 예외 타입 (발생 시).
            exc_val: 예외 값 (발생 시).
            exc_tb: 트레이스백 객체.
        """
        # Rationale: 직접 생성한 클라이언트(_owns_client=True)인 경우에만
        # 세션을 닫아 리소스 누수(Memory Leak, Socket Exhaustion)를 방지합니다.
        if self._owns_client and self._http_client:
            await self._http_client.close()
            self._logger.info("ExtractorService 내부 HTTP client 종료.")

    def _ensure_client(self):
        """HTTP 클라이언트 초기화 상태를 검증하는 Guard Clause.

        Raises:
            RuntimeError: HTTP 클라이언트가 초기화되지 않은 상태에서 호출 시 발생.
        """
        if not self._http_client:
            raise RuntimeError(
                "HTTP Client is not initialized. Use 'async with ExtractorService(...) as service:' pattern."
            )

    def _normalize_response(self, response: RequestDTO) -> ExtractedDTO:
        """다양한 Provider의 성공 응답을 표준 포맷으로 통일합니다 (Normalization).
        
        Rationale:
            Provider별로 성공 코드가 상이함(KIS='0', UPBIT='OK', FRED='200').
            이를 Facade 계층에서 'status: success'로 정규화하여
            상위 모듈이 구체적인 Provider 구현을 몰라도 되게 함 (Information Hiding).

        Args:
            response (RequestDTO): 원본 응답 객체.

        Returns:
            ExtractedDTO: 메타데이터(status)가 정규화된 응답 객체.
        """
        meta = response.meta
        
        # 1. Fast Path: 이미 정규화된 경우 즉시 반환
        if meta.get("status") == "success":
            return response

        # 2. Standardization Logic
        raw_status = meta.get("status_code")

        # Robustness Logic: status_code가 결측(None)되거나 비어있는("") 경우
        # 이를 암묵적 성공으로 간주하고 표준 성공 코드(200)로 보정합니다.
        if raw_status is None or raw_status == "":
            meta["status"] = "success"
            meta["status_code"] = 200
            return response

        # 다양한 형태의 status_code를 문자열로 변환하고 대문자화하여 비교 단순화
        status_code_str = str(raw_status).strip().upper()
        
        # 성공으로 간주할 수 있는 모든 코드 집합
        SUCCESS_CODES = {"200", "0", "OK", "SUCCESS"}

        if status_code_str in SUCCESS_CODES:
            meta["status"] = "success"
        
        return response

    async def extract_job(
        self, 
        job_id: str, 
        override_params: Optional[Dict[str, Any]] = None
    ) -> ExtractedDTO:
        """단일 수집 작업을 실행하고 정규화된 응답을 반환합니다.

        Args:
            job_id (str): 실행할 작업 식별자 (YAML Policy Key).
            override_params (Optional[Dict]): 런타임에 덮어쓸 파라미터 (기본 설정보다 우선함).

        Returns:
            ResponseDTO: 수집 결과 데이터 및 정규화된 메타데이터.

        Raises:
            ExtractorError: 작업 ID가 없거나 수집 중 치명적 오류 발생 시.
        """
        self._ensure_client()
        
        # 1. Policy Lookup
        # Rationale: Job ID가 없는 것은 런타임 에러가 아니라 '설정 오류'입니다.
        policy = self._config.extraction_policy.get(job_id)
        if not policy:
            raise ConfigurationError(
                message=f"Job ID '{job_id}'를 찾을 수 없습니다.",
                key_name="job_id"
            )
        try:
            # 2. Parameter Merging
            # Rationale: Config 불변성 보장을 위해 얕은 복사(.copy()) 사용
            final_params = policy.params.copy()
            if override_params:
                final_params.update(override_params)

            # 3. Factory Delegation
            # Factory가 Provider 타입에 맞는 Extractor를 생성하고 Auth 전략을 주입합니다.
            extractor = ExtractorFactory.create_extractor(
                job_id=job_id,
                http_client=self._http_client,
                config=self._config
            )
            
            request_dto = RequestDTO(job_id=job_id, params=final_params)

            # 4. Execution & Normalization
            response = await extractor.extract(request_dto)
            
            # 하위 시스템의 복잡성을 숨기고 표준화된 응답 반환
            return self._normalize_response(response)

        except ETLError as e:
            # 이미 ETLError로 래핑된 예외는 그대로 상위로 전파
            raise e

        except Exception as e:
            raise ExtractorError(
                message=f"Job '{job_id}' 작업 중 예상치 못한 오류가 발생.",
                details={
                    "job_id": job_id,
                    "step": "execution_layer",
                    "raw_error_type": type(e).__name__
                },
                original_exception=e, # 원본 스택트레이스 보존
            )

    async def extract_batch(
        self, 
        job_requests: List[Union[str, Tuple[str, Dict[str, Any]]]]
    ) -> List[Union[RequestDTO, Exception]]:
        """다수의 수집 작업을 병렬로 실행합니다 (Batch Processing).

        Args:
            job_requests (List): 실행할 작업 목록. 
                - Job ID 문자열 ("job_id") 
                - 또는 (ID, Param) 튜플 ("job_id", {"param": "value"})

        Returns:
            List[Union[RequestDTO, Exception]]: 결과 목록.
            성공 시 RequestDTO, 실패 시 Exception 객체가 리스트에 포함됨 (부분 성공 보장).
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
        # Rationale: return_exceptions=True를 사용하여 개별 작업의 실패가 
        # 전체 배치 프로세스를 중단시키지 않도록 격리(Isolation)합니다.
        self._logger.info(f"{len(tasks)} 개의 작업을 병렬로 실행합니다.")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. Summary Logging
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        self._logger.info(f"배치 작업 완료. 성공: {success_count}/{len(tasks)}")
        
        return results