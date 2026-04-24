"""
한국은행 경제통계시스템(ECOS)의 Open API를 활용하여 거시경제 및 금융 데이터를 수집하는 구체화된 수집기(Extractor) 모듈입니다.
`AbstractExtractor`가 강제하는 템플릿 생명주기(Validation -> Execution -> Packaging)를 엄격히 준수하며,
ECOS API 특유의 'Path Variable' 기반 요청 구조를 처리하기 위해 파라미터 병합 로직을 URL 동적 생성 로직으로 대체하여 구현했습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Validation: RequestDTO(job_id) 유입 시 ConfigManager를 통해 ECOS 전용 작업인지 식별 및 필수 날짜 파라미터 자동 보정.
2. Preparation: 정적 API Key와 런타임 파라미터(통계코드, 주기, 날짜 등)를 결합하여 엄격한 순서의 ECOS Path URL 조립.
3. Execution: IHttpClient를 통해 조립된 URL로 비동기 GET 요청 수행 (Query String 배제).
4. Packaging: ECOS 고유의 중첩 JSON 응답 구조를 파싱하여 'INFO-000' 성공 코드를 검증한 뒤 표준 ExtractedDTO로 래핑하여 반환.

주요 기능:
- Policy-driven Validation: 요청된 작업이 'ECOS' Provider에 속하는지 런타임에 즉시 검증하여 잘못된 파이프라인 실행 차단(Fail-Fast).
- Path Variable URL Builder: Query Parameter(?key=value) 방식을 지원하지 않는 ECOS API 규격에 맞춘 순차적 URL 조립.
- Default Date Injection: 수집 날짜(start_date, end_date)가 누락된 경우 최근 30일 기준으로 자동 할당하여 파이프라인 무결성 유지.
- ECOS Specific Error Handling: HTTP 200 OK 응답 내부에 숨겨진 비즈니스 에러 코드(RESULT.CODE != INFO-000)를 식별 및 예외 처리.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- Explicit URL Construction (Path Variable) vs Query String:
  - 장점: ECOS API가 강제하는 엄격한 URL 세그먼트 규칙(/Key/Type/Lang/...)을 완벽하게 준수하여 통신 오류를 원천 차단함.
  - 단점: URL 세그먼트 순서(StatCode -> Cycle -> Date...)가 코드 레벨에 하드코딩되어 있어, API 명세가 변경될 경우 유지보수가 필요함.
  - 근거: 외부 기관(한국은행)의 고정된 API 명세 준수가 범용적인 코드 유연성(Flexibility)보다 절대적으로 우선되어야 하는 인프라/어댑터 계층이므로, 명시적이고 결정론적인 문자열 포매팅 방식을 채택함.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from src.common.config import ConfigManager
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ETLError, ExtractorError
from src.common.interfaces import IHttpClient

from src.common.decorators.log_decorator import log_decorator
from src.common.decorators.rate_limit_decorator import rate_limit
from src.common.decorators.retry_decorator import retry

from src.extractor.providers.abstract_extractor import AbstractExtractor

class ECOSExtractor(AbstractExtractor):
    """설정(Config)에 정의된 정책을 기반으로 동작하는 한국은행(ECOS) API 전용 데이터 수집기.

    `AbstractExtractor`를 상속받아 ECOS의 규격에 맞는 Validation, Fetch, Response 조립 훅(Hook)을 구현합니다.

    Attributes:
        base_url (str): ECOS API의 엔드포인트 도메인.
        api_key (str): ECOS API 인증을 위한 평문 형태의 Secret Key.
    """

    def __init__(self, http_client: IHttpClient):
        """ECOSExtractor 인스턴스를 초기화하고 인증 정보의 무결성을 검증합니다.

        Args:
            http_client (IHttpClient): 비동기 네트워크 통신을 담당할 HTTP 클라이언트 어댑터.

        Raises:
            ExtractorError: ConfigManager에 필수 설정값(base_url, api_key)이 누락된 경우.
        """
        super().__init__(http_client)

        self.base_url = self.config.ecos.base_url
        
        # [설계 의도] SecretStr 객체에서 평문을 추출하여 메모리에 적재. 매 API 호출마다 
        # 추출하는 오버헤드를 줄이기 위해 초기화 시점에 한 번만 수행.
        self.api_key = self.config.ecos.api_key.get_secret_value()

        # [설계 의도] 주입받은 개별 설정값의 유효성 조기 검증(Fail-Fast).
        # 빈 문자열이나 None 상태로 파이프라인이 구동되어 런타임 중 타임아웃/404가 발생하는 것을 방지.
        if not self.base_url:
            raise ExtractorError("Critical Config Error: 'base_url' is empty.")
        if not self.api_key:
            raise ExtractorError("Critical Config Error: 'api_key' is missing.")

    def _validate_request(self, request: RequestDTO) -> None:
        """요청된 작업(Job)이 ECOS 수집 정책에 부합하는지 검증하고 필요시 기본값을 주입합니다.

        Args:
            request (RequestDTO): 파이프라인 컨트롤러로부터 전달받은 수집 요청 객체.

        Raises:
            ExtractorError: job_id가 없거나, 설정에 정의되지 않았거나, 대상 Provider가 'ECOS'가 아닌 경우.
        """
        if not request.job_id:
            raise ExtractorError("유효하지 않은 요청: 'job_id'는 필수 항목입니다.")

        try:
            policy = self.config.get_extractor(request.job_id)
        except Exception as e:
            raise ExtractorError(f"설정 오류: {e}")
        
        # [설계 의도] 파이프라인 설정 오류로 인해 다른 제공자(예: KIS)의 작업이 
        # ECOS 수집기로 잘못 라우팅되는 휴먼 에러를 런타임에 완벽히 차단함.
        if policy.provider != "ECOS":
            raise ExtractorError(f"API 제공자 불일치: Job '{request.job_id}'은(는) '{policy.provider}'용이며, 'ECOS'용이 아닙니다.")

        # [설계 의도] ECOS API는 수집 기간 명시가 필수적임. 
        # 호출자가 날짜를 누락하더라도 파이프라인이 중단되지 않도록 최근 30일이라는 합리적 기본값(Default)을 주입(Fail-Safe).
        if "start_date" not in request.params and "start_date" not in policy.params:
            default_start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
            request.params["start_date"] = default_start
            
        if "end_date" not in request.params and "end_date" not in policy.params:
            default_end = datetime.now().strftime("%Y%m%d")
            request.params["end_date"] = default_end

    @rate_limit(limit=20, period=1.0, bucket_key="ECOS")
    @retry(max_retries=3, base_delay=1.0)
    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """설정된 정책과 런타임 요청 파라미터를 결합하여 ECOS 규격에 맞는 Path 기반 URL을 조립하고 호출합니다.

        Decorators:
            @retry: 일시적인 네트워크 장애나 ECOS 서버 불안정 시 최대 3회(지수 백오프) 재시도 수행.
            @rate_limit: ECOS 서버의 Rate Limit 차단을 방지하기 위해 초당 20회 호출로 클라이언트 사이드 스로틀링 강제.

        Args:
            request (RequestDTO): 검증 및 기본값이 주입 완료된 요청 객체.

        Returns:
            Any: ECOS API로부터 수신한 JSON 형식의 원본 응답 데이터 (Dict 구조체).
        """
        # 1. 정책 및 파라미터 로드
        policy = self.config.get_extractor(request.job_id)
        
        # 2. 파라미터 추출 (Config의 정적 정책과 Request의 동적 파라미터 병합)
        stat_code = policy.params.get("stat_code")
        cycle = policy.params.get("cycle")
        item_code = policy.params.get("item_code1")
        start_date = request.params.get("start_date")
        end_date = request.params.get("end_date")

        # 3. URL 조립 (Strict Path Construction)
        # [설계 의도] ECOS는 표준적인 Query String(?key=value)을 지원하지 않고 URL Path 세그먼트의 
        # 절대적인 순서(/Key/Type/Lang/Start/End/StatCode/Cycle/StartDate/EndDate/ItemCode)를 요구함.
        # 대량 데이터 파이프라인을 가정하여 시작 인덱스 1, 종료 인덱스 100000으로 하드코딩 고정.
        base_path = policy.path.strip("/") # 예: StatisticSearch
        url = (
            f"{self.base_url}/{base_path}/"
            f"{self.api_key}/json/kr/1/100000/"
            f"{stat_code}/{cycle}/{start_date}/{end_date}/{item_code}"
        )

        # 4. 비동기 호출 수행
        # [설계 의도] URL 문자열 내에 모든 요구사항(인증키, 조회 조건 등)이 내포되었으므로 
        # params나 headers 인자를 별도로 전달하지 않고 깔끔하게 GET 호출만 수행함.
        return await self.http_client.get(url)

    def _create_response(self, raw_data_list: List[Any], job_id: str) -> ExtractedDTO:
        """ECOS API 응답 구조를 파싱하여 비즈니스 에러 코드를 식별하고 시스템 표준 DTO로 포장합니다.

        Args:
            raw_data_list (List[Any]): HTTP 클라이언트가 반환한 JSON 파싱 완료 원본 데이터 리스트.
            job_id (str): 현재 응답이 속한 작업의 고유 ID.

        Returns:
            ExtractedDTO: 원본 데이터와 필수 메타데이터가 병합된 표준 결과 객체.

        Raises:
            ExtractorError: HTTP 200 OK로 응답이 왔으나, 내부 RESULT.CODE가 정상(INFO-000)이거나 
                            데이터 없음(INFO-200)이 아닌 치명적 에러인 경우.
        """
        # [설계 의도] 방어적 프로그래밍. 병렬 호출 결과가 비어있을 경우 무의미한 로직 실행 방지.
        if not raw_data_list:
            raise ExtractorError(f"[{job_id}] 수집된 데이터가 없습니다 (빈 응답 리스트 반환).")

        policy = self.config.get_extractor(job_id)
        # ECOS는 URL Path의 첫 번째 요소(예: /StatisticSearch/... -> StatisticSearch)를 최상위 응답 키로 사용함
        policy_path = policy.path.strip('/').split('/')[0]

        merged_data: Dict[str, Any] = {}
        base_response = None

        for idx, raw_data in enumerate(raw_data_list):
            # 1. 에러 및 예외 응답 처리 (Root에 RESULT가 바로 오는 경우)
            if "RESULT" in raw_data:
                code = raw_data["RESULT"].get("CODE")
                msg = raw_data["RESULT"].get("MESSAGE")
                
                # 금융 데이터의 지연 고시(T+1) 특성으로 인해 발생한 '데이터 없음(INFO-200)'을
                # 치명적 파이프라인 예외가 아닌, 0건의 데이터 추출 성공(정상 비즈니스 상태)으로 수용합니다.
                if code == "INFO-200":
                    continue
                    
                if code != "INFO-000":
                     raise ExtractorError(f"ECOS API 부분 실패 (Chunk {idx+1}/{len(raw_data_list)}): {msg} (Code: {code})")

            # 2. 정상 응답 내 비즈니스 코드 및 데이터 확인
            if policy_path in raw_data:
                result_body = raw_data[policy_path]
                
                # 데이터가 0건이거나 파라미터가 잘못된 경우 'row' 없이 'RESULT' 객체만 반환될 수 있음
                if "RESULT" in result_body:
                    code = result_body["RESULT"].get("CODE")
                    msg = result_body["RESULT"].get("MESSAGE")
                    
                    if code == "INFO-200":
                        continue
                        
                    if code != "INFO-000":
                        raise ExtractorError(f"ECOS API 부분 실패 (Chunk {idx+1}/{len(raw_data_list)}): {msg} (Code: {code})")

                # 3. 베이스 응답 캡처 및 row 데이터 병합
                if base_response is None:
                    base_response = raw_data.copy()
                    merged_data = base_response
                    
                    # [설계 의도] 첫 청크의 row가 아예 없거나 비어있는 경우 빈 리스트로 초기화하여 이후 병합을 준비함.
                    if "row" not in merged_data[policy_path] or not merged_data[policy_path]["row"]:
                        merged_data[policy_path]["row"] = []
                    continue

                # 4. 두 번째 응답부터는 row 배열만 찾아 이어붙임(Extend)
                current_rows = result_body.get("row", [])
                
                # 빈 리스트([])인 경우 무시하여 메모리와 스토리지 낭비 방지 (비용/효익 최적화)
                if not current_rows:
                    continue
                    
                merged_data[policy_path]["row"].extend(current_rows)

            else:
                raise ExtractorError(f"ECOS API 알 수 없는 응답 구조: '{policy_path}' 키를 찾을 수 없습니다.")

        # 5. 빈 응답 조립 및 총 건수 메타데이터 보정
        # 조회된 모든 청크가 INFO-200을 반환하여 base_response가 초기화되지 않은 경우,
        # 다운스트림 계층(Loader)이 에러 없이 0건 적재를 수행할 수 있도록 표준 규격의 빈 딕셔너리를 생성합니다.
        if base_response is None:
            merged_data = {
                policy_path: {
                    "list_total_count": 0,
                    "row": []
                }
            }
        elif policy_path in merged_data:
            merged_data[policy_path]["list_total_count"] = len(merged_data[policy_path].get("row", []))

        return ExtractedDTO(
            data=merged_data,
            meta={
                "source": "ECOS",
                "job_id": job_id,
                "extracted_at": datetime.now().isoformat(),
                "status_code": "INFO-000", 
                "chunks_merged": len(raw_data_list)
            }
        )