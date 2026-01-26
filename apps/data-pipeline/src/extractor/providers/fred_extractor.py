"""
FRED 데이터 수집기 모듈 (FRED Extractor)

이 모듈은 St. Louis Fed의 FRED API를 통해 경제 지표 데이터를 수집합니다.
기본 XML 응답을 JSON으로 강제 변환하고, 쿼리 파라미터 기반의 인증을 처리합니다.

데이터 흐름 (Data Flow):
RequestDTO(job_id) -> Validate(Config.policy) -> Merge Params(API Key + Format) -> Async API Call -> Error Check -> ResponseDTO

주요 기능:
- FRED API 호출 시 `file_type=json` 파라미터 강제 주입 (XML 파싱 비용 제거)
- Policy(설정)와 Request(요청) 파라미터의 동적 병합 및 우선순위 처리
- API 응답 내 논리적 에러(HTTP 200 OK 내의 Error Message) 감지

Trade-off:
- Method Override (extract):
    - 상황: AbstractExtractor._create_response는 job_id를 인자로 받지 않음.
    - 결정: KISExtractor와 동일하게 extract 메서드를 오버라이딩하여 ResponseDTO 생성 시 job_id를 주입.
    - 근거: 부모 클래스의 서명(Signature)을 변경하지 않고 메타데이터(Job ID) 추적성을 확보하기 위함.
"""

from typing import Any, Dict, Optional
from datetime import datetime

from .abstract_extractor import AbstractExtractor
from ..domain.interfaces import IHttpClient
from ..domain.dtos import RequestDTO, ResponseDTO
from ..domain.exceptions import ExtractorError
from ...common.config import AppConfig


class FREDExtractor(AbstractExtractor):
    """설정(AppConfig)에 정의된 정책을 기반으로 FRED API를 호출하는 수집기.

    Attributes:
        http_client (IHttpClient): HTTP 요청 처리를 위한 어댑터.
        config (AppConfig): 앱 전역 설정 객체 (FRED API Key 포함).
    """

    def __init__(self, http_client: IHttpClient, config: AppConfig):
        """FREDExtractor를 초기화하고 필수 의존성을 검증합니다.

        Args:
            http_client (IHttpClient): HTTP 클라이언트.
            config (AppConfig): 앱 설정 객체.

        Raises:
            ExtractorError: FRED 관련 필수 설정(Base URL, API Key)이 누락된 경우.
        """
        # 1. 부모 클래스 초기화 (Config None 체크 포함)
        super().__init__(http_client, config)

        # 2. FRED 전용 필수 설정 검증 (Fail-Fast)
        # Rationale: AppConfig 객체가 존재하더라도 내부 필드가 비어있으면 런타임 에러가 발생하므로 생성 시점에 확인.
        if not config.fred.base_url:
            raise ExtractorError("Critical Config Error: 'fred.base_url' is empty.")
        if not config.fred.api_key:
            raise ExtractorError("Critical Config Error: 'fred.api_key' is missing.")

    async def extract(self, request: RequestDTO) -> ResponseDTO:
        """데이터 수집 템플릿 메서드 (Overridden).

        AbstractExtractor의 기본 흐름을 따르되, _create_response 단계에서
        job_id를 주입하기 위해 KISExtractor와 동일하게 오버라이딩하였습니다.

        Args:
            request (RequestDTO): 요청 객체.

        Returns:
            ResponseDTO: 결과 객체.

        Raises:
            ExtractorError: 수집 실패 시.
        """
        try:
            # Step 1: Validation
            self._validate_request(request)

            # Step 2: Execution (Preparation & I/O)
            raw_data = await self._fetch_raw_data(request)

            # Step 3: Packaging
            # Rationale: 부모 클래스의 _create_response는 raw_data만 받도록 정의되어 있어,
            # job_id를 포함시키기 위해 이곳에서 호출 구조를 변경함.
            response = self._create_response(raw_data, request.job_id)
            
            self.logger.info(f"Extraction Successful | Job: {request.job_id} | Source: FRED")
            return response

        except ExtractorError as e:
            # 도메인 에러는 로깅 후 상위로 전파
            self.logger.error(f"Extraction Failed: {e}")
            raise e
        except Exception as e:
            # 예상치 못한 에러는 래핑하여 전파
            self.logger.error(f"Unexpected System Error: {e}", exc_info=True)
            raise ExtractorError(f"System Error: {str(e)}")

    def _validate_request(self, request: RequestDTO) -> None:
        """요청된 Job이 FRED 정책에 부합하고 필수 파라미터를 가졌는지 검증합니다.

        Args:
            request (RequestDTO): 요청 객체.

        Raises:
            ExtractorError: 정책 미존재, Provider 불일치, 필수 파라미터(series_id) 누락 시.
        """
        if not request.job_id:
            raise ExtractorError("Invalid Request: 'job_id' is mandatory.")

        policy = self.config.extraction_policy.get(request.job_id)

        # 1. Policy 존재 여부 확인
        if not policy:
            self.logger.error(f"Policy missing for job_id: {request.job_id}")
            raise ExtractorError(f"Configuration Error: Policy not found for job_id '{request.job_id}'.")

        # 2. Provider 일치 여부 확인
        if policy.provider != "FRED":
            raise ExtractorError(f"Provider Mismatch: Job '{request.job_id}' is for '{policy.provider}', not 'FRED'.")

        # 3. 필수 파라미터(series_id) 확인
        # Rationale: FRED API의 핵심 식별자인 'series_id'가 Config나 Request 어디에도 없으면 호출이 불가능함.
        # KISExtractor가 'tr_id'를 검사하는 것과 동일한 로직.
        has_series_id_in_policy = "series_id" in policy.params
        has_series_id_in_request = "series_id" in request.params

        if not (has_series_id_in_policy or has_series_id_in_request):
            raise ExtractorError(f"Missing Parameter: 'series_id' is required for job '{request.job_id}'.")

    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """FRED API를 호출하여 원본 데이터를 가져옵니다.

        Args:
            request (RequestDTO): 요청 객체.

        Returns:
            Any: API 원본 응답 (Dict).
        """
        policy = self.config.extraction_policy[request.job_id]

        # 1. URL 구성
        url = f"{self.config.fred.base_url}{policy.path}"

        # 2. 파라미터 병합 (Policy < Request < System Forced)
        merged_params = policy.params.copy()
        merged_params.update(request.params)
        
        # Rationale: FRED는 기본적으로 XML을 반환하므로 시스템 차원에서 JSON을 강제함.
        merged_params["file_type"] = "json"
        
        # 3. 인증 정보 주입
        # Rationale: FRED는 Header가 아닌 Query Parameter로 api_key를 받음.
        # SecretStr 타입인 api_key를 안전하게 평문으로 변환하여 주입.
        merged_params["api_key"] = self.config.fred.api_key.get_secret_value()

        self.logger.debug(f"Executing FRED Request | Job: {request.job_id} | Path: {policy.path}")

        # 4. HTTP 요청 수행
        return await self.http_client.get(url, params=merged_params)

    def _create_response(self, raw_data: Any, job_id: str) -> ResponseDTO:
        """API 응답을 검증하고 ResponseDTO로 포장합니다.

        Args:
            raw_data (Any): API 원본 응답.
            job_id (str): 작업 ID.

        Returns:
            ResponseDTO: 결과 객체.

        Raises:
            ExtractorError: API 응답 내 에러 메시지가 포함된 경우.
        """
        # Rationale: FRED API는 HTTP 200 응답에도 JSON Body에 에러 메시지를 포함할 수 있음.
        # 예: {"error_code": 400, "error_message": "Bad Request"}
        if "error_message" in raw_data:
            msg = raw_data.get("error_message")
            code = raw_data.get("error_code", "Unknown")
            self.logger.error(f"FRED API Business Failure: {msg} (Code: {code})")
            raise ExtractorError(f"FRED API Failed: {msg} (Code: {code})")

        return ResponseDTO(
            data=raw_data,
            meta={
                "source": "FRED",
                "job_id": job_id,
                "extracted_at": datetime.now().isoformat(),
                # FRED API는 명시적인 성공 코드를 JSON에 주지 않으므로 HTTP 성공을 가정하여 200 기재
                "status_code": "200"
            }
        )