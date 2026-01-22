"""
KIS(한국투자증권) 데이터 수집기 구현체 (KIS Extractor)

이 모듈은 한국투자증권 오픈 API를 사용하여 데이터를 수집하는 역할을 담당합니다.
모든 API 호출 정보(URL, TR_ID 등)를 코드 내 상수가 아닌 외부 설정(AppConfig)에서
동적으로 로드하여 유연성을 확보했습니다.

데이터 흐름 (Data Flow):
RequestDTO(job_id) -> Load Policy from Config -> Get Token -> Merge Params -> Async API Call -> Check Status -> ResponseDTO

주요 기능:
- 설정 파일(YAML) 기반의 API 요청 정보 동적 로딩
- 작업 ID(job_id) 유효성 검사 및 필수 정책(Policy) 확인
- API 응답 코드(rt_cd) 검사를 통한 수집 성공 여부 판단
- 수집 실패 시 도메인 표준 예외(ExtractorError) 발생

Trade-off:
- Runtime Config Dependency:
    - 장점: 새로운 API 대상 추가 시 코드를 배포하지 않고 설정 파일 수정만으로 대응 가능.
    - 단점: 설정 파일의 오타나 누락이 런타임 에러로 이어질 수 있음.
    - 근거: 다양한 종류의 금융 데이터를 수집해야 하는 요구사항 특성상 확장성이 최우선임.
"""

from typing import Any, Dict, Optional
from datetime import datetime

from .abstract_extractor import AbstractExtractor
from ..domain.interfaces import IHttpClient, IAuthStrategy
from ..domain.dtos import RequestDTO, ResponseDTO
from ..domain.exceptions import ExtractorError
from ...common.config import AppConfig

class KISExtractor(AbstractExtractor):
    """설정(Config)에 정의된 정책을 기반으로 동작하는 한국투자증권 데이터 수집기.

    Attributes:
        auth_strategy (IAuthStrategy): 토큰 발급 및 갱신을 담당하는 전략 객체.
        config (AppConfig): 애플리케이션의 전체 설정 정보를 담고 있는 객체.
    """

    def __init__(
        self, 
        http_client: IHttpClient, 
        auth_strategy: IAuthStrategy, 
        config: AppConfig
    ):
        """KISExtractor 인스턴스를 생성하고 필수 설정을 검증합니다.

        Args:
            http_client (IHttpClient): HTTP 요청을 수행할 클라이언트.
            auth_strategy (IAuthStrategy): 인증 토큰 관리 전략.
            config (AppConfig): 앱 설정 객체.

        Raises:
            ExtractorError: 필수 설정 항목이 누락된 경우 발생.
        """
        super().__init__(http_client, config)
        self.auth_strategy = auth_strategy

        
        # 설정 객체에 KIS API 기본 URL이 포함되어 있는지 확인합니다.
        if not hasattr(config, "kis_base_url") or not config.kis_base_url:
            raise ExtractorError("Critical Config Error: 'kis_base_url' is missing in AppConfig.")
            
        # 설정 객체에 데이터 수집 정책(Dictionary)이 포함되어 있는지 확인합니다.
        if not hasattr(config, "extraction_policy") or not isinstance(config.extraction_policy, dict):
            raise ExtractorError("Critical Config Error: 'extraction_policy' dictionary is missing.")

    def _validate_request(self, request: RequestDTO) -> None:
        """요청 정보와 설정 파일의 정합성을 검사합니다.

        요청된 작업(job_id)이 설정 파일에 정의되어 있는지,
        그리고 해당 정책에 필수적인 API 정보(path, tr_id)가 있는지 확인합니다.

        Args:
            request (RequestDTO): 데이터 수집 요청 객체.

        Raises:
            ExtractorError: job_id가 없거나 설정 파일에 해당 정책이 없는 경우.
        """
        # 요청 객체에 작업 ID가 명시되어 있는지 확인합니다.
        if not request.job_id:
            raise ExtractorError("Invalid Request: 'job_id' is mandatory for KIS Extraction.")

        # 설정 파일에서 해당 작업 ID에 대한 정책을 가져옵니다.
        policy = self.config.extraction_policy.get(request.job_id)
        
        # 정책이 존재하지 않으면 수집을 진행할 수 없으므로 에러를 발생시킵니다.
        if not policy:
            self.logger.error(f"Policy missing for job_id: {request.job_id}")
            raise ExtractorError(f"Configuration Error: Policy not found for job_id '{request.job_id}'. Check extractor.yml.")

        # 정책 딕셔너리에 API 호출을 위한 필수 키(경로, TR_ID)가 포함되어 있는지 검사합니다.
        required_keys = ["path", "tr_id"]
        missing_keys = [key for key in required_keys if key not in policy]
        
        if missing_keys:
            raise ExtractorError(
                f"Configuration Error: Policy '{request.job_id}' is incomplete. Missing keys: {missing_keys}"
            )

    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """설정된 정책과 요청 파라미터를 결합하여 실제 API 호출을 수행합니다.

        인증 토큰 획득, 헤더 구성, 파라미터 병합 과정을 거쳐 HTTP 요청을 전송합니다.

        Args:
            request (RequestDTO): 검증이 완료된 요청 객체.

        Returns:
            Any: API 서버로부터 받은 원본 응답 데이터 (Dictionary).
        """
        # 인증 전략 객체를 통해 유효한 액세스 토큰을 가져옵니다.
        token = await self.auth_strategy.get_token(self.http_client)

        # 설정 파일에서 현재 작업에 해당하는 정책을 로드합니다.
        policy = self.config.extraction_policy[request.job_id]
        
        # 기본 URL과 정책에 정의된 경로를 결합하여 전체 요청 URL을 생성합니다.
        url = f"{self.config.kis_base_url}{policy['path']}"
        tr_id = policy['tr_id']

        # API 호출에 필요한 HTTP 헤더를 구성합니다.
        # 토큰, 앱 키, 시크릿, TR_ID가 포함되며, 정책에 추가 헤더가 있다면 병합합니다.
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": token,
            "appkey": self.config.kis_app_key,
            "appsecret": self.config.kis_app_secret,
            "tr_id": tr_id,
            **policy.get("extra_headers", {})
        }

        # 파라미터 병합: 설정 파일의 고정 파라미터(static)와 요청 파라미터(dynamic)를 합칩니다.
        # 요청 파라미터가 고정 파라미터보다 우선순위를 가집니다.
        static_params = policy.get("params", {})
        dynamic_params = request.params
        merged_params = {**static_params, **dynamic_params}

        self.logger.debug(f"Executing KIS Request | Job: {request.job_id} | TR_ID: {tr_id}")

        # 구성된 정보로 HTTP GET 요청을 비동기로 수행하고 결과를 반환합니다.
        raw_response = await self.http_client.get(url, headers=headers, params=merged_params)

        return raw_response

    def _create_response(self, raw_data: Any) -> ResponseDTO:
        """API 원본 데이터를 ResponseDTO 객체로 포장합니다.

        API 응답 코드를 확인하여 비즈니스 로직상 실패인 경우 에러를 발생시키고,
        성공인 경우 데이터를 가공 없이 그대로 반환 객체에 담습니다.

        Args:
            raw_data (Any): _fetch_raw_data에서 반환된 API 원본 데이터.

        Returns:
            ResponseDTO: 원본 데이터와 메타데이터가 담긴 전송 객체.

        Raises:
            ExtractorError: API 응답 코드가 성공(0)이 아닌 경우.
        """
        # API 응답 내의 결과 코드(rt_cd)를 추출합니다.
        rt_cd = raw_data.get("rt_cd", "")
        
        # 결과 코드가 '0'(성공)이 아니라면 수집 실패로 간주합니다.
        if rt_cd != "0":
            msg = raw_data.get("msg1", "Unknown Error")
            self.logger.error(f"KIS API Business Failure: {msg} (Code: {rt_cd})")
            # 단순히 데이터를 반환하지 않고 에러를 발생시켜 파이프라인을 중단하거나 재시도를 유도합니다.
            raise ExtractorError(f"KIS API Failed: {msg} (Code: {rt_cd})")

        # 수집 성공 시, 원본 데이터를 DTO에 담아 반환합니다.
        return ResponseDTO(
            data=raw_data,
            meta={
                "source": "KIS",
                "extracted_at": datetime.now().isoformat(),
                "status_code": rt_cd
            }
        )