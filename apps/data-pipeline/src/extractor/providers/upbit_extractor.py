"""
업비트(UPBIT) 오픈 API를 활용하여 암호화폐(Cryptocurrency) 시세 및 시장 데이터를 수집하는 구체화된 수집기(Extractor) 모듈입니다.
모든 API 호출 정보(URL, 파라미터 등)를 하드코딩하지 않고 외부 설정(ConfigManager)에서 동적으로 로드하며,
`AbstractExtractor`가 강제하는 생명주기를 준수하여 인증(JWT), 파라미터 병합, 비동기 통신, 에러 핸들링을 캡슐화합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. RequestDTO: 파이프라인 컨트롤러로부터 특정 수집 대상 작업(job_id) 실행 요청 유입.
2. Validation: ConfigManager에서 UPBIT 전용 작업(JobPolicy)인지 확인하고 식별자 사전 검증.
3. Preparation & Auth: UPBITAuthStrategy를 통해 JWT 토큰을 확보(필요 시)하고, 정적 정책과 동적 파라미터를 병합하여 HTTP Header 구성.
4. Execution: 비동기 HTTP 클라이언트(IHttpClient)를 통해 조립된 URL과 헤더로 API 호출 (Rate Limit 10회/초 제한 준수).
5. Verification & Wrap: HTTP 응답 페이로드 내 비즈니스 에러(`error` 객체)를 검증 후 다운스트림용 표준 ExtractedDTO로 래핑.

주요 기능:
- Configuration-Driven Execution: 코드 배포 없이 YAML 설정 파일 수정만으로 새로운 마켓/코인 수집 작업 동적 추가 가능.
- Dynamic Header Injection: AuthStrategy와 연동하여 JWT 토큰을 매 요청마다 동적 주입 (Public 엔드포인트의 경우 생략 가능).
- Application-Level Error Handling: 응답 내에 포함되거나 별도로 반환되는 업비트 자체 비즈니스 에러(`error` 딕셔너리)를 포착하여 파이프라인 중단(Fail-Fast).

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- Runtime Config Dependency (Late Binding):
  - 장점: 급변하는 암호화폐 시장 특성상 새로운 마켓(코인 페어) 데이터 수집 요구사항에 소스 코드 수정 및 재배포 없이 즉각 대응이 가능함.
  - 단점: 설정 파일의 오타나 필수 값 누락이 컴파일 타임이 아닌 런타임(또는 초기화 타임) 에러로 발현될 위험이 존재함.
  - 근거: 다양한 종류의 자산을 수집해야 하는 파이프라인 특성상 확장성(Scalability) 확보가 코드 레벨의 강한 결합(Hardcoding)보다 우선시됨.
"""

from datetime import datetime
from typing import Any, Dict

from src.common.config import ConfigManager
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ExtractorError
from src.common.interfaces import IHttpClient, IAuthStrategy

from src.common.decorators.log_decorator import log_decorator
from src.common.decorators.rate_limit_decorator import rate_limit
from src.common.decorators.retry_decorator import retry

from src.extractor.providers.abstract_extractor import AbstractExtractor

class UPBITExtractor(AbstractExtractor):
    """설정(Config)에 정의된 정책을 기반으로 동작하는 업비트(UPBIT) 전용 데이터 수집기.

    `AbstractExtractor`를 상속받아 UPBIT 규격에 맞는 Validation, Fetch, Response 조립 훅(Hook)을 구현합니다.

    Attributes:
        auth_strategy (IAuthStrategy): UPBIT JWT 토큰 발급 및 서명을 담당하는 전략 인스턴스.
        base_url (str): UPBIT API의 엔드포인트 도메인.
    """

    def __init__(self, http_client: IHttpClient, auth_strategy: IAuthStrategy):
        """UPBITExtractor 인스턴스를 초기화하고 의존성을 주입받습니다.

        Args:
            http_client (IHttpClient): 비동기 네트워크 통신을 담당할 HTTP 클라이언트 어댑터.
            auth_strategy (IAuthStrategy): UPBIT 전용 인증 토큰 발급/서명 관리 객체.

        Raises:
            ExtractorError: ConfigManager에 필수 설정값(base_url)이 누락된 경우.
        """
        super().__init__(http_client)
        self.auth_strategy = auth_strategy
        self.base_url = self.config.upbit.base_url
        
        # [설계 의도] 필수 환경변수 누락 시 시스템 구동 시점(Fail-Fast)에 에러를 발생시켜
        # 런타임 도중 의미 없는 네트워크 호출과 예외가 발생하는 것을 조기 방지함.
        if not self.base_url:
            raise ExtractorError("Critical Config Error: 'base_url'가 누락되었습니다.")
    
    def _validate_request(self, request: RequestDTO) -> None:
        """요청된 작업(Job)이 UPBIT 수집 정책에 부합하는지 런타임에 사전 검증합니다.

        Args:
            request (RequestDTO): 파이프라인 컨트롤러로부터 전달받은 수집 요청 객체.

        Raises:
            ExtractorError: job_id가 누락되었거나, 설정에 없거나, Provider가 불일치하는 경우.
        """
        if not request.job_id:
            raise ExtractorError("유효하지 않은 요청: 'job_id'는 필수 항목입니다.")

        # [설계 의도] 설정 파일에서 해당 job_id를 찾지 못할 경우, 하위 로직 실행 전
        # 조기 예외를 발생시켜 시스템의 상태 이상을 즉각적으로 알림.
        try:
            policy = self.config.get_extractor(request.job_id)
        except Exception as e:
            raise ExtractorError(f"설정 오류: {e}")

        # [설계 의도] 파이프라인 YAML 설정의 휴먼 에러로 인해 타 API(예: KIS) 작업이 
        # UPBIT 수집기로 잘못 라우팅되는 것을 원천 방어함.
        if policy.provider != "UPBIT":
            raise ExtractorError(f"API 제공자 불일치: Job '{request.job_id}'은(는) '{policy.provider}'용이며, 'UPBIT'용이 아닙니다.")

    @rate_limit(limit=10, period=1.0, bucket_key="UPBIT_Quotation")
    @retry(max_retries=3)
    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """설정된 정책, 인증 토큰(JWT), 요청 파라미터를 병합하여 UPBIT API를 비동기 호출합니다.

        Decorators:
            @retry: 일시적인 네트워크 장애나 서버 오류 시 최대 3회 재시도.
            @rate_limit: UPBIT Quotation API의 초당 10회 호출 제한 규정을 클라이언트 사이드에서 강제 준수.

        Args:
            request (RequestDTO): 검증이 완료된 요청 객체.

        Returns:
            Any: UPBIT API로부터 수신한 JSON 형식의 원본 응답 데이터 (주로 Dict 또는 List 구조체).
        """
        # 1. 인증 토큰 확보 (AuthStrategy 위임)
        # [설계 의도] 토큰 생성 및 JWT 서명 로직을 추출기(Extractor)에서 분리하여 단일 책임 원칙(SRP) 준수.
        token = await self.auth_strategy.get_token(self.http_client)

        # 2. 정책 로드 (Validation 단계를 통과했으므로 존재 보장)
        policy = self.config.get_extractor(request.job_id)
        
        # 3. URL 구성
        # Config의 계층 구조(config.upbit.base_url)와 객체 속성(policy.path)을 결합.
        url = f"{self.base_url}{policy.path}"
        
        # 4. 헤더 구성
        # [설계 의도] Bearer Token 방식을 사용하며, 시세 조회 등 인증이 필요 없는 
        # Public 엔드포인트의 경우 token이 None일 수 있으므로 이를 동적으로 처리.
        headers = {
            "accept": "application/json",
        }
        if token:
            headers["authorization"] = token

        # 5. 파라미터 병합
        # [설계 의도] 정적 설정(policy.params)을 기본값으로 두고, 스케줄러 등이 주입한
        # 동적 파라미터(request.params)로 덮어쓰기하여 런타임 유연성을 극대화함.
        merged_params = {**policy.params, **request.params}

        # 6. 비동기 호출 수행
        return await self.http_client.get(url, headers=headers, params=merged_params)

    def _create_response(self, raw_data: Any, job_id: str) -> ExtractedDTO:
        """UPBIT API 응답 구조를 파싱하여 비즈니스 에러를 식별하고 시스템 표준 DTO로 포장합니다.

        Args:
            raw_data (Any): HTTP 클라이언트가 JSON으로 파싱 완료한 원본 데이터.
            job_id (str): 현재 응답이 속한 작업의 메타데이터 식별용 고유 ID.

        Returns:
            ExtractedDTO: 원본 데이터와 필수 메타데이터가 병합된 표준 결과 객체.

        Raises:
            ExtractorError: 반환된 페이로드 내에 'error' 구조체가 포함되어 있는 경우.
        """
        # [설계 의도] UPBIT API는 잘못된 파라미터나 권한 에러 발생 시 최상위에 
        # {'error': {'name': ..., 'message': ...}} 구조의 페이로드를 반환함.
        # 이를 식별하여 비정상 데이터가 다운스트림(데이터 레이크)으로 흘러가는 것을 방어(Fail-Fast).
        if isinstance(raw_data, dict) and "error" in raw_data:
            error_payload = raw_data["error"]
            error_name = error_payload.get("name", "알 수 없는 오류")
            error_msg = error_payload.get("message", "메시지 없음")
            
            raise ExtractorError(f"업비트 API 실패: {error_msg} (이름: {error_name})")
        
        # [설계 의도] 성공적인 응답에 한해 후속 파이프라인(Loader)이 즉시 소비할 수 있도록 
        # 데이터 컨트랙트(ExtractedDTO)로 래핑. (UPBIT는 별도 상태 코드를 주지 않아 "OK"로 명시)
        return ExtractedDTO(
            data=raw_data,
            meta={
                "source": "UPBIT",
                "job_id": job_id,
                "extracted_at": datetime.now().isoformat(),
                "status_code": "OK"
            }
        )