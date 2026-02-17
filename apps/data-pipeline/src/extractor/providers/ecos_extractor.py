"""
ECOS(한국은행 경제통계시스템) 데이터 수집기 구현체 (ECOS Extractor)

이 모듈은 한국은행(BOK)의 Open API(ECOS)를 사용하여 거시경제 및 금융 데이터를 수집하는 역할을 담당합니다.
KIS 수집기와 동일한 파이프라인(AbstractExtractor)을 따르지만, ECOS API 특유의
'Path Variable' 기반 요청 구조를 처리하기 위해 파라미터 병합 로직을 URL 생성 로직으로 대체했습니다.

데이터 흐름 (Data Flow):
RequestDTO(job_id) -> Load Policy -> Build Path-based URL -> Async API Call -> Check Result Code -> ResponseDTO

주요 기능:
- 설정(Config)과 요청(Request) 파라미터를 결합하여 ECOS 표준 URL 동적 생성
- Static API Key 관리 및 URL 내 주입 (Query String 미사용)
- ECOS 고유 응답 구조(JSON) 파싱 및 'INFO-000' 성공 코드 검증
- 수집 실패 시 도메인 표준 예외(ExtractorError) 발생

Trade-off:
- Explicit URL Construction (Path Variable):
    - 장점: ECOS API는 파라미터 순서가 엄격한 Path 방식(/Key/Type/Lang/...)을 강제하므로, 
      Dict 기반의 Query String(?key=value)보다 명시적인 URL 조립이 필수적임.
    - 단점: URL의 세그먼트 순서(StatCode -> Cycle -> Date...)가 변경되면 코드를 수정해야 함.
    - 근거: API 명세 준수가 일반화된 유연성보다 우선시되어야 하는 인프라 계층임.
"""

from datetime import datetime
from typing import Any

from src.common.config import ConfigManager
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ETLError, ExtractorError
from src.common.interfaces import IHttpClient

from src.common.decorators.log_decorator import log_decorator
from src.common.decorators.rate_limit_decorator import rate_limit
from src.common.decorators.retry_decorator import retry

from src.extractor.providers.abstract_extractor import AbstractExtractor

class ECOSExtractor(AbstractExtractor):
    """설정(Config)에 정의된 정책을 기반으로 동작하는 한국은행(ECOS) 데이터 수집기.

    Attributes:
        config (ConfigManager): 애플리케이션의 전체 설정 정보를 담고 있는 객체.
    """

    def __init__(self, http_client: IHttpClient, config: ConfigManager):
        """ECOSExtractor를 초기화합니다.

        Args:
            http_client (IHttpClient): HTTP 요청 클라이언트.
            config (ConfigManager): 앱 설정 객체.
        """
        # 부모 클래스(AbstractExtractor) 초기화 (여기서 config 기본 검증 수행됨)
        super().__init__(http_client, config)

        # Rationale: Fail-Fast 원칙. ECOS 수집기 인스턴스화 시점에 필수 인증키와 URL 유무를 확인.
        if not config.ecos.base_url:
            raise ExtractorError("Critical Config Error: 'ecos.base_url' is empty.")
        if not config.ecos.api_key:
            raise ExtractorError("Critical Config Error: 'ecos.api_key' is missing.")

    def _validate_request(self, request: RequestDTO) -> None:
        """요청된 작업(Job)이 ECOS 수집 정책에 부합하는지 검증합니다.

        1. job_id가 Config의 extraction_policy에 존재하는지 확인.
        2. 해당 Policy의 Provider가 'ECOS'인지 확인.
        3. 날짜 범위(start_date, end_date)가 요청에 포함되었는지 확인 (ECOS 필수).

        Args:
            request (RequestDTO): 요청 객체.

        Raises:
            ExtractorError: 정책이 없거나, Provider가 다르거나, 필수 파라미터가 누락된 경우.
        """
        if not request.job_id:
            raise ExtractorError("Invalid Request: 'job_id' is mandatory.")

        # Rationale: Pydantic 모델의 딕셔너리 속성(extraction_policy)에 접근.
        policy = self.config.extraction_policy.get(request.job_id)

        if not policy:
            self.logger.error(f"Policy missing for job_id: {request.job_id}")
            raise ExtractorError(f"Configuration Error: Policy not found for job_id '{request.job_id}'.")

        # Rationale: 다른 Provider(예: KIS)의 작업을 ECOS 수집기에 요청하는 실수를 방지.
        if policy.provider != "ECOS":
            raise ExtractorError(f"Provider Mismatch: Job '{request.job_id}' is for '{policy.provider}', not 'ECOS'.")

        # Rationale: ECOS는 URL Path에 날짜를 필수적으로 포함해야 하므로, 요청 시점 검증이 필요함.
        if "start_date" not in request.params or "end_date" not in request.params:
            raise ExtractorError("Invalid Request: 'start_date' and 'end_date' are mandatory for ECOS.")

    @log_decorator(logger_name="ECOS_Extractor")
    @rate_limit(limit=20, period=1.0, bucket_key="ECOS_API")
    @retry(max_retries=3, base_delay=1.0)
    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """설정된 정책과 요청 파라미터를 결합하여 ECOS API URL을 조립하고 호출합니다.

        Decorators:
            @retry: 네트워크 일시 오류 시 최대 3회 재시도.
            @rate_limit: 초당 20회 호출 제한 (안전한 기본값).
            @log_decorator: 함수 진입/종료 및 에러 로깅.

        ECOS API 구조: /Service/Key/Type/Lang/Start/End/StatCode/Cycle/StartDate/EndDate/ItemCode

        Args:
            request (RequestDTO): 검증된 요청 객체.

        Returns:
            Any: API 원본 응답 데이터 (Dict).
        """
        # 1. 정책 및 인증키 로드
        policy = self.config.extraction_policy[request.job_id]
        api_key = self.config.ecos.api_key.get_secret_value()
        
        # 2. 파라미터 추출 (Config와 Request 병합 개념)
        # Rationale: YAML Config에는 정적 정보(통계코드)가, Request에는 동적 정보(날짜)가 있음.
        stat_code = policy.params.get("stat_code")
        cycle = policy.params.get("cycle")
        item_code = policy.params.get("item_code1")
        start_date = request.params.get("start_date")
        end_date = request.params.get("end_date")

        # 3. URL 조립 (Strict Path Construction)
        # Rationale: ECOS는 Query Param을 쓰지 않고 Path Variable 순서를 엄격히 따름.
        # 기본 요청 건수는 1~100000건으로 고정 (대량 조회 가정).
        base_path = policy.path.strip("/") # 예: StatisticSearch
        url = (
            f"{self.config.ecos.base_url}/{base_path}/"
            f"{api_key}/json/kr/1/100000/"
            f"{stat_code}/{cycle}/{start_date}/{end_date}/{item_code}"
        )

        self.logger.debug(f"Executing ECOS Request | Job: {request.job_id} | Path: {url}")

        # 4. 비동기 호출 수행
        # Rationale: URL에 모든 파라미터가 포함되었으므로 params 인자는 전달하지 않음.
        return await self.http_client.get(url)

    def _create_response(self, raw_data: Any, job_id: str) -> ExtractedDTO:
        """ECOS API 응답의 결과 코드(RESULT.CODE)를 확인하고 DTO로 포장합니다.

        Args:
            raw_data (Any): API 원본 응답.
            job_id (str): 요청된 작업 ID.
        Returns:
            ExtractedDTO: 결과 객체.

        Raises:
            ExtractorError: API 코드가 성공('INFO-000')이 아닌 경우.
        """
        # 1. 서비스명 추출 (Root Key)
        # Rationale: ECOS 응답은 { "StatisticSearch": { ... } } 형태이므로 Root Key를 찾아야 함.
        policy_path = self.config.extraction_policy[job_id].path.strip("/")
        
        # 2. 에러 응답 처리 (Root에 RESULT가 바로 오는 경우 - 인증 에러 등)
        if "RESULT" in raw_data:
            code = raw_data["RESULT"].get("CODE")
            msg = raw_data["RESULT"].get("MESSAGE")
            if code != "INFO-000":
                 self.logger.error(f"ECOS API System Failure: {msg} (Code: {code})")
                 raise ExtractorError(f"ECOS API Failed: {msg} (Code: {code})")

        # 3. 정상 응답 내 비즈니스 코드 확인
        if policy_path in raw_data:
            result_body = raw_data[policy_path]
            # row가 없고 RESULT만 있는 경우 (데이터 없음 등)
            if "RESULT" in result_body:
                code = result_body["RESULT"].get("CODE")
                msg = result_body["RESULT"].get("MESSAGE")
                if code != "INFO-000":
                    self.logger.error(f"ECOS API Business Failure: {msg} (Code: {code})")
                    raise ExtractorError(f"ECOS API Failed: {msg} (Code: {code})")
        else:
             # Rationale: 예상한 서비스명 키가 없는 경우 응답 구조 변경 또는 알 수 없는 에러.
             raise ExtractorError(f"Invalid ECOS Response: Root key '{policy_path}' not found.")

        return ExtractedDTO(
            data=raw_data,
            meta={
                "source": "ECOS",
                "job_id": job_id,
                "extracted_at": datetime.now().isoformat(),
                "status": "success"
            }
        )