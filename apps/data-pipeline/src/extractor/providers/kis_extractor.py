"""
한국투자증권(KIS) 오픈 API를 활용하여 주식, 채권 등 금융 데이터를 수집하는 구체화된 수집기(Extractor) 모듈입니다.
모든 API 호출 정보(URL, TR_ID 등)를 하드코딩하지 않고 외부 설정(ConfigManager)에서 동적으로 로드하며,
`AbstractExtractor`가 강제하는 생명주기를 준수하여 인증(OAuth2), 파라미터 병합, 비동기 통신, 에러 핸들링을 캡슐화합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. RequestDTO: 파이프라인 컨트롤러로부터 특정 수집 대상 작업(job_id) 실행 요청 유입.
2. Validation: ConfigManager에서 KIS 전용 작업(JobPolicy)인지 확인하고 API 필수 식별자(tr_id) 사전 검증.
3. Preparation & Auth: KISAuthStrategy를 통해 Access Token을 확보하고, 정적 정책과 동적 파라미터를 병합하여 HTTP Header 구성.
4. Execution: 비동기 HTTP 클라이언트(IHttpClient)를 통해 조립된 URL과 헤더로 API 호출 (Rate Limit 5회/초 제한 준수).
5. Verification & Wrap: HTTP 응답 페이로드 내 비즈니스 성공 코드(rt_cd == "0")를 검증 후 다운스트림용 표준 ExtractedDTO로 래핑.

주요 기능:
- Configuration-Driven Execution: 코드 배포 없이 YAML 설정 파일 수정만으로 새로운 KIS API 엔드포인트 수집 작업 동적 추가 가능.
- Dynamic Header Injection: AuthStrategy와 연동하여 토큰 생명주기를 투명하게 관리하고, API Key 및 Token을 매 요청마다 동적 주입.
- Strict Validation: KIS API 필수 규격인 Transaction ID(`tr_id`) 누락을 네트워크 I/O 실행 전에 감지하여 불필요한 통신 방지.
- Application-Level Error Handling: HTTP 200 OK 응답 내에 포함된 KIS 자체 비즈니스 에러(`rt_cd` != "0")를 포착하여 파이프라인 중단(Fail-Fast).

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- Runtime Config Dependency (Late Binding):
  - 장점: 새로운 금융 지표 대상이 추가되거나 파라미터가 변경될 때, 소스 코드 수정 및 재배포 없이 설정 파일(YAML) 변경만으로 즉각 대응이 가능함.
  - 단점: 설정 파일의 오타나 필수 값 누락이 컴파일 타임이 아닌 런타임(또는 초기화 타임) 에러로 발현될 위험이 존재함.
  - 근거: 수십~수백 개의 서로 다른 금융 지표(TR_ID)를 수집해야 하는 KIS API 특성상, 코드 수준의 강한 결합(Hardcoding)보다 유연성(Flexibility) 확보가 시스템 확장성 측면에서 압도적으로 중요하므로 이 설계를 채택함.
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

class KISExtractor(AbstractExtractor):
    """설정(Config)에 정의된 정책을 기반으로 동작하는 한국투자증권(KIS) 전용 데이터 수집기.

    `AbstractExtractor`를 상속받아 KIS 규격에 맞는 Validation, Fetch, Response 조립 훅(Hook)을 구현합니다.

    Attributes:
        auth_strategy (IAuthStrategy): KIS OAuth2 토큰 발급 및 갱신(Lazy Refresh)을 담당하는 전략 인스턴스.
        base_url (str): KIS API의 엔드포인트 도메인.
        app_key (str): KIS API 인증을 위한 App Key (평문).
        app_secret (str): KIS API 인증을 위한 App Secret (평문).
    """

    def __init__(self, http_client: IHttpClient, auth_strategy: IAuthStrategy):
        """KISExtractor 인스턴스를 초기화하고 의존성을 주입받습니다.

        Args:
            http_client (IHttpClient): 비동기 네트워크 통신을 담당할 HTTP 클라이언트 어댑터.
            auth_strategy (IAuthStrategy): KIS 전용 인증 토큰 발급 관리 객체.

        Raises:
            ExtractorError: ConfigManager에 필수 설정값(base_url)이 누락된 경우.
        """
        super().__init__(http_client)
        self.auth_strategy = auth_strategy

        self.base_url = self.config.kis.base_url
        
        # [설계 의도] SecretStr 객체에서 평문을 추출하여 메모리에 적재. 
        # 매 API 호출마다 복호화 프로퍼티에 접근하는 오버헤드를 제거하기 위해 초기화 시점에 수행.
        self.app_key = self.config.kis.app_key.get_secret_value()
        self.app_secret = self.config.kis.app_secret.get_secret_value()
        
        # [설계 의도] 필수 환경변수 누락 시 시스템 구동 시점(Fail-Fast)에 에러를 발생시켜
        # 런타임 도중 의미 없는 네트워크 호출과 예외가 발생하는 것을 방지.
        if not self.base_url:
            raise ExtractorError("Critical Config Error: 'base_url'가 누락되었습니다.")
    
    def _validate_request(self, request: RequestDTO) -> None:
        """요청된 작업(Job)이 KIS 수집 정책에 부합하는지 런타임에 사전 검증합니다.

        Args:
            request (RequestDTO): 파이프라인 컨트롤러로부터 전달받은 수집 요청 객체.

        Raises:
            ExtractorError: job_id가 누락되었거나, 설정에 없거나, Provider가 불일치하거나 필수 식별자(tr_id)가 없는 경우.
        """
        if not request.job_id:
            raise ExtractorError("유효하지 않은 요청: 'job_id'는 필수 항목입니다.")

        try:
            policy = self.config.get_extractor(request.job_id)
        except Exception as e:
            # [설계 의도] 낡은 방식의 수동 로깅(self.logger.error)을 배제.
            # 여기서 비즈니스 예외(ExtractorError)를 던지면, 최상위 @log_decorator가 
            # 이를 포착하여 자동으로 규격화된 에러 로깅(Structured Log)을 수행함.
            raise ExtractorError(f"설정 오류: {e}")

        # [설계 의도] 파이프라인 YAML 설정의 휴먼 에러로 인해 타 API(예: FRED) 작업이 
        # KIS 수집기로 잘못 라우팅되는 것을 원천 방어함.
        if policy.provider != "KIS":
            raise ExtractorError(f"API 제공자 불일치: Job '{request.job_id}'은(는) '{policy.provider}'용이며, 'KIS'용이 아닙니다.")

        # [설계 의도] KIS API 명세상 Transaction ID(`tr_id`)는 헤더에 필수적으로 들어가야 하므로,
        # 이 값이 설정(policy)에 존재하지 않으면 API 호출 자체가 실패함. 이를 사전에 차단.
        if not policy.tr_id:
             raise ExtractorError(f"설정 오류: '{request.job_id}' 정책에 'tr_id'가 누락되었습니다.")
    
    @rate_limit(limit=5, period=1.0, bucket_key="KIS_OpenAPI")
    @retry(max_retries=3)
    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """설정된 정책, 인증 토큰, 요청 파라미터를 병합하여 KIS API를 비동기 호출합니다.

        Decorators:
            @retry: 일시적인 네트워크 장애나 KIS 서버 오류 시 지수 백오프 기반 최대 3회 재시도.
            @rate_limit: KIS 계좌/앱키 단위 API 호출 제한 규정(초당 5회)을 클라이언트 사이드에서 강제 준수.

        Args:
            request (RequestDTO): 검증이 완료된 요청 객체.

        Returns:
            Any: KIS API로부터 수신한 JSON 형식의 원본 응답 데이터 (Dict 구조체).
        """
        # 1. 인증 토큰 확보 (AuthStrategy 위임)
        # [설계 의도] 토큰의 유효성 검사 및 갱신 로직을 추출기(Extractor)에서 분리하여 
        # 단일 책임 원칙(SRP) 준수 및 코드 중복 방지.
        token = await self.auth_strategy.get_token(self.http_client)

        # 2. 정책 로드 (Validation 단계를 통과했으므로 존재 보장)
        policy = self.config.get_extractor(request.job_id)
        
        # 3. URL 구성
        # Config의 계층 구조(config.kis.base_url)와 객체 속성(policy.path)을 결합.
        url = f"{self.base_url}{policy.path}"
        
        # 4. 헤더 구성
        # [설계 의도] KIS 명세에 따라 App Key, Secret, Token, TR_ID를 모두 HTTP Header에 주입.
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": token,
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": policy.tr_id
        }

        # 5. 파라미터 병합
        # [설계 의도] 정적 설정(policy.params)을 기본값으로 깔고, 스케줄러 등이 주입한
        # 동적 설정(request.params)으로 덮어쓰기하여 런타임 유연성을 극대화함.
        merged_params = {**policy.params, **request.params}

        # 6. 비동기 호출 수행
        return await self.http_client.get(url, headers=headers, params=merged_params)

    def _create_response(self, raw_data: Any, job_id: str) -> ExtractedDTO:
        """KIS API 응답 구조를 파싱하여 비즈니스 성공 여부를 판단하고 시스템 표준 DTO로 포장합니다.

        Args:
            raw_data (Any): HTTP 클라이언트가 JSON으로 파싱 완료한 원본 데이터.
            job_id (str): 현재 응답이 속한 작업의 메타데이터 식별용 고유 ID.

        Returns:
            ExtractedDTO: 원본 데이터와 필수 메타데이터가 병합된 표준 결과 객체.

        Raises:
            ExtractorError: HTTP Status 200 OK로 반환되었음에도 내부 `rt_cd`가 '0'(성공)이 아닌 경우.
        """
        # [설계 의도] KIS API는 잘못된 파라미터나 권한 오류 시에도 HTTP 200 코드를 주고,
        # JSON Payload 내부의 `rt_cd` 필드를 통해 비즈니스 실패를 알림. 
        # 이를 무시하고 적재하면 데이터 레이크가 오염되므로 래핑 전 엄격하게 필터링함.
        rt_cd = raw_data.get("rt_cd", "")
        
        if rt_cd != "0":
            msg = raw_data.get("msg", "알 수 없는 오류")
            raise ExtractorError(f"KIS API 실패: {msg} (Code: {rt_cd})")

        # [설계 의도] 성공적인 응답에 한해 후속 파이프라인(Loader)이 즉시 
        # 소비할 수 있도록 데이터 컨트랙트(ExtractedDTO)로 패키징.
        return ExtractedDTO(
            data=raw_data,
            meta={
                "source": "KIS",
                "job_id": job_id,
                "extracted_at": datetime.now().isoformat(),
                "status_code": rt_cd
            }
        )