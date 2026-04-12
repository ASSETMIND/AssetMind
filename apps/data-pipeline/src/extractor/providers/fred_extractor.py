"""
FRED(Federal Reserve Economic Data) API를 연동하여 거시경제 지표 데이터를 수집하는 구체화된 수집기 모듈입니다.
`AbstractExtractor`의 템플릿 생명주기(Validation -> Execution -> Packaging)를 엄격히 준수하며, 
상태가 없는(Stateless) 쿼리 파라미터 기반의 인증 처리와 데이터 파이프라인 표준화를 위한 JSON 응답 강제 변환 로직을 캡슐화했습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Validation: RequestDTO(job_id) 유입 시 ConfigManager를 통해 FRED 정책을 식별하고 필수 파라미터(series_id) 존재 여부 조기 검증.
2. Preparation: 정책(Policy) 파라미터와 런타임 요청(Request) 파라미터를 병합한 뒤, 인증키(api_key) 및 응답 포맷(file_type=json)을 시스템에서 강제 주입.
3. Execution: IHttpClient를 통해 조립된 쿼리 스트링 기반의 비동기 GET 요청 수행 (Rate Limit 준수).
4. Packaging: HTTP 200 OK 응답 내부에 숨겨진 논리적 비즈니스 에러(error_message)를 감지하고, 정상 응답 시 표준 ExtractedDTO로 래핑하여 반환.

주요 기능:
- Configuration & Request Parameter Merging: 정적 설정(YAML)과 동적 요청 파라미터를 런타임에 유연하게 병합.
- Format Enforcing (JSON): 기본값이 XML인 FRED API 호출 시 `file_type=json` 파라미터를 강제 주입하여 XML 파싱 비용 제거.
- Stateless Authentication: 별도의 세션이나 헤더 주입 없이 API 명세에 맞춘 쿼리 파라미터(`api_key`) 기반 즉시 인증.
- Application-level Error Detection: HTTP 상태 코드가 정상이더라도 페이로드 내의 에러 메시지를 식별하는 방어적 파싱.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. Query Parameter Authentication vs Header Injection:
   - 장점: FRED API 명세에 가장 부합하며 HTTP 요청 구성 객체를 단순화할 수 있음.
   - 단점: URL을 평문으로 로깅할 경우 API Key가 노출될 보안 위협이 존재함.
   - 근거: 이를 방어하기 위해 하위 HTTP 어댑터(`log_decorator.py`) 계층에 PII 마스킹 로직이 이미 구현되어 있으므로, API 명세를 그대로 수용하는 것이 구조적으로 깔끔함.
2. Implicit JSON Forcing (`file_type="json"`):
   - 장점: 무거운 XML 파싱 연산(CPU Bound)과 서드파티 라이브러리(lxml 등) 의존성을 제거하고 데이터 레이크(Data Lake) 적재 표준을 일원화함.
   - 단점: 호출자가 명시적으로 XML 포맷을 요구하더라도 파이프라인에서 강제로 JSON으로 오버라이드 됨.
   - 근거: 엔터프라이즈 데이터 웨어하우스 환경에서는 수집 포맷을 JSON/Parquet 등으로 획일화하여 다운스트림(Loader)의 복잡성을 낮추는 것이 시스템 유지보수성에 압도적으로 유리하므로 이 제약을 수용함.
"""

from datetime import datetime
from typing import Any, Dict, List

from src.common.config import ConfigManager
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ExtractorError
from src.common.interfaces import IHttpClient

from src.common.decorators.log_decorator import log_decorator
from src.common.decorators.rate_limit_decorator import rate_limit
from src.common.decorators.retry_decorator import retry

from src.extractor.providers.abstract_extractor import AbstractExtractor

class FREDExtractor(AbstractExtractor):
    """설정(ConfigManager)에 정의된 정책을 기반으로 FRED API를 호출하는 전용 수집기 구현체.

    `AbstractExtractor`를 상속받아 FRED의 규격에 맞는 Validation, Fetch, Response 조립 훅(Hook)을 구현합니다.

    Attributes:
        base_url (str): FRED API의 엔드포인트 도메인.
        api_key (str): FRED API 인증을 위한 평문 형태의 Secret Key.
    """

    def __init__(self, http_client: IHttpClient):
        """FREDExtractor 인스턴스를 초기화하고 인증 정보의 무결성을 검증합니다.

        Args:
            http_client (IHttpClient): 비동기 네트워크 통신을 담당할 HTTP 클라이언트 어댑터.

        Raises:
            ExtractorError: ConfigManager에 필수 설정값(base_url, api_key)이 누락된 경우.
        """
        # 1. 부모 클래스 초기화 (IHttpClient None 체크 및 Config 로드 수행)
        super().__init__(http_client)

        self.base_url = self.config.fred.base_url
        
        # [설계 의도] SecretStr 객체에서 평문을 추출하여 메모리에 적재. 
        # 매 API 호출 시 반복되는 객체 접근 오버헤드를 제거하기 위함.
        self.api_key = self.config.fred.api_key.get_secret_value()

        # 2. FRED 전용 필수 설정 검증 (Fail-Fast)
        # [설계 의도] 설정 누락으로 인해 무의미한 네트워크 I/O 타임아웃이나 401 에러가 
        # 발생하기 전에 시스템 구동 시점 또는 인스턴스화 시점에 조기 차단함.
        if not self.base_url:
            raise ExtractorError("Critical Config Error: 'base_url'가 누락되었습니다.")
        if not self.api_key:
            raise ExtractorError("Critical Config Error: 'api_key'가 누락되었습니다.")

    def _validate_request(self, request: RequestDTO) -> None:
        """요청된 작업(Job)이 FRED 수집 정책에 부합하고 필수 파라미터를 포함하는지 사전에 검증합니다.

        Args:
            request (RequestDTO): 파이프라인 컨트롤러로부터 전달받은 수집 요청 객체.

        Raises:
            ExtractorError: job_id가 누락되었거나, 설정에 없거나, Provider가 불일치하거나 필수 파라미터가 누락된 경우.
        """
        if not request.job_id:
            raise ExtractorError("유효하지 않은 요청: 'job_id'는 필수 항목입니다.")

        # 1. Policy 존재 여부 확인
        try:
            policy = self.config.get_extractor(request.job_id)
        except Exception as e:
            raise ExtractorError(f"설정 오류: {e}")

        # 2. Provider 일치 여부 확인
        # [설계 의도] 파이프라인 설정의 휴먼 에러로 인해 타 API(예: ECOS) 작업이 
        # FRED 수집기로 라우팅되는 것을 원천 방어함.
        if policy.provider != "FRED":
            raise ExtractorError(f"API 제공자 불일치: Job '{request.job_id}'은(는) '{policy.provider}'용이며, 'FRED'용이 아닙니다.")

        # 3. 필수 파라미터(series_id) 확인
        # [설계 의도] FRED API의 핵심 식별자인 'series_id'가 정적 Config나 동적 Request 
        # 그 어디에도 선언되지 않았다면 API 호출 자체가 불가능하므로 Fail-Fast 처리함.
        has_series_id_in_policy = "series_id" in policy.params
        has_series_id_in_request = "series_id" in request.params

        if not (has_series_id_in_policy or has_series_id_in_request):
            raise ExtractorError(f"파라미터 누락: 작업 '{request.job_id}'에 'series_id'가 필요합니다.")

    @rate_limit(limit=2, period=1.0, bucket_key="FRED")
    @retry(max_retries=3)
    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """정적 정책 설정과 런타임 요청 파라미터를 병합하여 FRED API를 비동기 호출합니다.

        Decorators:
            @retry: 일시적인 네트워크 장애나 FRED 서버 오류 시 지수 백오프 기반 최대 3회 재시도.
            @rate_limit: FRED API 공식 제한에 맞추어 초당 2회로 클라이언트 사이드 스로틀링(Throttling) 강제.

        Args:
            request (RequestDTO): 검증이 완료된 요청 객체.

        Returns:
            Any: FRED API로부터 수신한 JSON 형식의 원본 응답 데이터 (Dict 구조체).
        """
        policy = self.config.get_extractor(request.job_id)

        # 1. URL 구성
        url = f"{self.base_url}{policy.path}"

        # 2. 파라미터 병합 (우선순위: Policy < Request < System Forced)
        # [설계 의도] 정적 설정 파일(policy)을 기본값으로 두고 런타임 요청(request)으로 덮어쓴 뒤, 
        # 데이터 파이프라인 무결성을 위해 포맷(JSON)과 인증키는 시스템 수준에서 강제로 주입함.
        merged_params = policy.params.copy()
        merged_params.update(request.params)
        merged_params["file_type"] = "json"
        merged_params["api_key"] = self.api_key

        # 4. HTTP 요청 수행
        return await self.http_client.get(url, params=merged_params)

    def _create_response(self, raw_data_list: List[Any], job_id: str) -> ExtractedDTO:
        """FRED API 응답 구조를 파싱하여 애플리케이션 레벨의 에러를 식별하고 시스템 표준 DTO로 포장합니다.

        Args:
            raw_data_list (List[Any]): HTTP 클라이언트가 JSON으로 파싱 완료한 원본 데이터 리스트.
            job_id (str): 현재 응답이 속한 작업의 메타데이터 식별용 고유 ID.

        Returns:
            ExtractedDTO: 원본 데이터와 필수 메타데이터가 병합된 표준 결과 객체.

        Raises:
            ExtractorError: HTTP Status 200 OK로 반환되었음에도 내부 JSON에 에러 메시지가 포함된 경우.
        """
        # [설계 의도] 방어적 프로그래밍.
        if not raw_data_list:
            raise ExtractorError(f"[{job_id}] 수집된 데이터가 없습니다 (빈 응답 리스트 반환).")

        merged_data: Dict[str, Any] = {}
        base_response = None

        for idx, raw_data in enumerate(raw_data_list):
            # 1. 에러 검증 (Fail-Fast)
            # [설계 의도] FRED API는 잘못된 쿼리 발생 시 Body 내부에 error_message를 반환함.
            if "error_message" in raw_data:
                msg = raw_data.get("error_message")
                code = raw_data.get("error_code", "Unknown")
                raise ExtractorError(f"FRED API 부분 실패 (Chunk {idx+1}/{len(raw_data_list)}): {msg} (Code: {code})")

            # 2. 첫 응답을 베이스 뼈대로 캡처
            if base_response is None:
                base_response = raw_data.copy()
                merged_data = base_response
                
                # [설계 의도] observations 배열이 없으면 빈 배열로 뼈대를 구축.
                if "observations" not in merged_data or not merged_data["observations"]:
                    merged_data["observations"] = []
                continue

            # 3. 두 번째 응답부터는 observations 배열만 찾아 이어붙임(Extend)
            current_observations = raw_data.get("observations", [])
            
            # [개선] 빈 리스트([])인 경우 무시하여 메모리와 스토리지 낭비 방지 (비용/효익 최적화)
            if not current_observations:
                continue
                
            merged_data["observations"].extend(current_observations)

        # 4. 총 건수 메타데이터 보정
        if base_response:
            merged_data["count"] = len(merged_data.get("observations", []))

        return ExtractedDTO(
            data=merged_data,
            meta={
                "source": "FRED",
                "job_id": job_id,
                "extracted_at": datetime.now().isoformat(),
                "status_code": "200",
                "chunks_merged": len(raw_data_list)
            }
        )