"""
UPBIT(업비트) 데이터 수집기 구현체 (UPBIT Extractor)

이 모듈은 업비트 오픈 API를 사용하여 데이터를 수집하는 역할을 담당합니다.
모든 API 호출 정보(URL, Market Code 등)를 코드 내 상수가 아닌 외부 설정(AppConfig)에서
동적으로 로드하여 유연성을 확보했습니다.

데이터 흐름 (Data Flow):
RequestDTO(job_id) -> Load Policy from Config -> Get Token -> Merge Params -> Async API Call -> Check Status -> ResponseDTO

주요 기능:
- 설정 파일(YAML) 기반의 API 요청 정보 동적 로딩
- 작업 ID(job_id) 유효성 검사 및 필수 정책(Policy) 확인
- API 응답 에러 객체(error) 검사를 통한 수집 성공 여부 판단
- 수집 실패 시 도메인 표준 예외(ExtractorError) 발생

Trade-off:
- Runtime Config Dependency:
    - 장점: 새로운 코인 마켓 추가 시 코드를 배포하지 않고 설정 파일 수정만으로 대응 가능.
    - 단점: 설정 파일의 오타나 누락이 런타임 에러로 이어질 수 있음.
    - 근거: 급변하는 암호화폐 시장 특성상 새로운 마켓 데이터 수집 요구사항에 빠르게 대응해야 함.
"""

from typing import Any, Dict, Optional
from datetime import datetime

from .abstract_extractor import AbstractExtractor
from ..domain.interfaces import IHttpClient, IAuthStrategy
from ..domain.dtos import RequestDTO, ResponseDTO
from ..domain.exceptions import ExtractorError
from ...common.config import AppConfig

class UPBITExtractor(AbstractExtractor):
    """설정(Config)에 정의된 정책을 기반으로 동작하는 업비트 데이터 수집기.

    Attributes:
        auth_strategy (IAuthStrategy): 토큰 발급(JWT) 및 갱신을 담당하는 전략 객체.
        config (AppConfig): 애플리케이션의 전체 설정 정보를 담고 있는 객체.
    """

    def __init__(
        self, 
        http_client: IHttpClient, 
        auth_strategy: IAuthStrategy, 
        config: AppConfig
    ):
        """UPBITExtractor를 초기화합니다.

        Args:
            http_client (IHttpClient): HTTP 요청 클라이언트.
            auth_strategy (IAuthStrategy): UPBIT 인증 토큰 발급 전략.
            config (AppConfig): 앱 설정 객체.
        """
        # 부모 클래스(AbstractExtractor) 초기화 (여기서 config 기본 검증 수행됨)
        super().__init__(http_client, config)
        self.auth_strategy = auth_strategy
        
        # Rationale: AppConfig가 Pydantic 모델이므로 upbit 필드의 존재는 보장되지만, 
        # 명시적으로 base_url이 비어있는지 체크하여 Fail-Fast를 유도함.
        if not config.upbit.base_url:
            raise ExtractorError("Critical Config Error: 'upbit.base_url' is empty in AppConfig.")

    async def extract(self, request: RequestDTO) -> ResponseDTO:
        """데이터 수집을 수행하는 공개 메서드 (Template Method).

        검증 -> 데이터 인출 -> 응답 생성의 표준 흐름을 제어합니다.

        Args:
            request (RequestDTO): 수집 요청 정보 (job_id, params 포함).

        Returns:
            ResponseDTO: 수집된 원본 데이터와 메타데이터.

        Raises:
            ExtractorError: 수집 과정 중 발생한 모든 비즈니스 예외.
        """
        try:
            # 1. 요청 유효성 검증 (Validation)
            self._validate_request(request)

            # 2. 데이터 인출 (Fetching)
            raw_data = await self._fetch_raw_data(request)

            # 3. 응답 객체 생성 (Response Creation)
            response = self._create_response(raw_data, request.job_id)
            
            self.logger.info(f"Extraction Successful | Job: {request.job_id}")
            
            return response

        except ExtractorError as e:
            # 이미 처리된 ExtractorError는 그대로 상위로 전파
            self.logger.error(f"Extraction Failed: {e}")
            raise e
        except Exception as e:
            # 예상치 못한 시스템 에러는 ExtractorError로 래핑하여 일관성 유지
            self.logger.error(f"Unexpected System Error during extraction: {e}", exc_info=True)
            raise ExtractorError(f"System Error: {str(e)}")
    
    def _validate_request(self, request: RequestDTO) -> None:
        """요청된 작업(Job)이 UPBIT 수집 정책에 부합하는지 검증합니다.

        1. job_id가 Config의 extraction_policy에 존재하는지 확인.
        2. 해당 Policy의 Provider가 'UPBIT'인지 확인.
        3. UPBIT API 호출에 필수적인 파라미터(params) 설정 여부 확인.

        Args:
            request (RequestDTO): 요청 객체.

        Raises:
            ExtractorError: 정책이 없거나, Provider가 다르거나, 필수 필드가 누락된 경우.
        """
        if not request.job_id:
            raise ExtractorError("Invalid Request: 'job_id' is mandatory.")

        # Rationale: Pydantic 모델의 딕셔너리 속성(extraction_policy)에 접근.
        policy = self.config.extraction_policy.get(request.job_id)
        
        if not policy:
            self.logger.error(f"Policy missing for job_id: {request.job_id}")
            raise ExtractorError(f"Configuration Error: Policy not found for job_id '{request.job_id}'.")

        # Rationale: 다른 Provider(예: KIS)의 작업을 UPBIT 수집기에 요청하는 실수를 방지.
        if policy.provider != "UPBIT":
            raise ExtractorError(f"Provider Mismatch: Job '{request.job_id}' is for '{policy.provider}', not 'UPBIT'.")

        # Rationale: 대부분의 업비트 API는 'market' 파라미터가 필수임. (Policy나 Request Params 중 한 곳에는 있어야 함)
        # KIS의 tr_id 체크와 유사하게, UPBIT 로직에 필수적인 사전 검증을 수행.
        combined_params = {**policy.params, **request.params}
        if "market" not in combined_params and "markets" not in combined_params:
             self.logger.warning(f"Parameter Warning: 'market' might be missing in policy '{request.job_id}'.")

    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """설정된 정책과 인증 정보를 결합하여 UPBIT API를 호출합니다.

        Args:
            request (RequestDTO): 검증된 요청 객체.

        Returns:
            Any: API 원본 응답 데이터 (Dict or List).
        """
        # 1. 인증 토큰 확보 (AuthStrategy 위임)
        token = await self.auth_strategy.get_token(self.http_client)

        # 2. 정책 로드 (Validation 단계를 통과했으므로 존재 보장)
        policy = self.config.extraction_policy[request.job_id]
        
        # 3. URL 구성
        # Config의 계층 구조(config.upbit.base_url)와 객체 속성(policy.path)을 활용.
        url = f"{self.config.upbit.base_url}{policy.path}"
        
        # 4. 헤더 구성
        # Bearer Token 방식을 사용하며, 인증이 필요 없는 경우 token이 None일 수 있음.
        headers = {
            "accept": "application/json",
        }
        if token:
            headers["authorization"] = token

        # 5. 파라미터 병합
        # Static Params(Config)와 Dynamic Params(Request)를 병합. Request가 우선순위를 가짐.
        merged_params = {**policy.params, **request.params}

        self.logger.debug(f"Executing UPBIT Request | Job: {request.job_id} | Path: {policy.path}")

        # 6. 비동기 호출 수행
        return await self.http_client.get(url, headers=headers, params=merged_params)

    def _create_response(self, raw_data: Any, job_id: str) -> ResponseDTO:
        """UPBIT API 응답의 에러 객체(error)를 확인하고 DTO로 포장합니다.

        Args:
            raw_data (Any): API 원본 응답.
            job_id (str): 요청된 작업 ID.
        Returns:
            ResponseDTO: 결과 객체.

        Raises:
            ExtractorError: 응답 내에 'error' 키가 존재하는 경우.
        """
        # Rationale: UPBIT API는 에러 발생 시 {'error': {'name':..., 'message':...}} 형태를 반환함.
        if isinstance(raw_data, dict) and "error" in raw_data:
            error_payload = raw_data["error"]
            error_name = error_payload.get("name", "UnknownError")
            error_msg = error_payload.get("message", "No message provided")
            
            self.logger.error(f"UPBIT API Business Failure: {error_msg} (Name: {error_name})")
            raise ExtractorError(f"UPBIT API Failed: {error_msg} (Name: {error_name})")

        return ResponseDTO(
            data=raw_data,
            meta={
                "source": "UPBIT",
                "job_id": job_id,
                "extracted_at": datetime.now().isoformat(),
                "status_code": "OK" # UPBIT는 별도의 상태 코드를 본문에 주지 않으므로 OK로 통일
            }
        )