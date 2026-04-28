from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

import pandas as pd

from src.common.dtos import RequestDTO, ExtractedDTO

class IHttpClient(ABC):
    """HTTP 통신을 담당하는 어댑터 인터페이스.
    
    구체적인 라이브러리(requests, aiohttp, httpx)에 대한 의존성을 제거하기 위해 정의합니다.
    Adapter Pattern의 Target 인터페이스 역할을 합니다.
    """

    @abstractmethod
    async def get(self, url: str, headers: Optional[Dict] = None, params: Optional[Dict] = None) -> Any:
        """비동기 GET 요청을 수행합니다.
        
        Args:
            url (str): 요청할 URL.
            headers (Optional[Dict]): HTTP 요청 헤더.
            params (Optional[Dict]): URL 쿼리 파라미터.
            
        Returns:
            Any: 원본 응답 객체 (Response).
        """
        pass

    @abstractmethod
    async def post(self, url: str, headers: Optional[Dict] = None, data: Optional[Dict] = None) -> Any:
        """비동기 POST 요청을 수행합니다.
        
        Args:
            url (str): 요청할 URL.
            headers (Optional[Dict]): HTTP 요청 헤더.
            data (Optional[Dict]): 요청 바디 데이터 (JSON 등).
            
        Returns:
            Any: 원본 응답 객체 (Response).
        """
        pass

class IAuthStrategy(ABC):
    """API 인증 토큰 관리를 담당하는 전략 인터페이스.
    
    Strategy Pattern을 사용하여 데이터 소스마다 다른 인증 방식(OAuth, APIKey)을 캡슐화합니다.
    """

    @abstractmethod
    async def get_token(self, http_client: IHttpClient) -> str:
        """유효한 인증 토큰 또는 키 값을 반환합니다.
        
        구현체 내부에서 토큰 캐싱 및 갱신 로직을 수행해야 합니다.

        Args:
            http_client (IHttpClient): 토큰 갱신 요청 시 사용할 HTTP 클라이언트.

        Returns:
            str: API 호출 시 헤더에 포함될 인증 토큰 값.
        """
        pass

class IExtractor(ABC):
    """모든 데이터 수집기가 반드시 구현해야 하는 최상위 인터페이스.
    
    Template Method Pattern의 기반이 되며, 외부 시스템(Service Layer)은
    오직 이 인터페이스에만 의존합니다.
    """

    @abstractmethod
    async def extract(self, request: RequestDTO) -> ExtractedDTO:
        """데이터 추출 작업을 수행합니다.
        
        검증, 인증, 요청, 파싱의 전 과정을 수행하고 표준화된 결과를 반환합니다.

        Args:
            request (RequestDTO): 데이터 추출 요청 객체.

        Returns:
            ExtractedDTO: 추출된 데이터 결과 객체.
            
        Raises:
            ExtractorError: 추출 과정에서 발생한 모든 예외.
        """
        pass

class ITransformer(ABC):
    """모든 데이터 변환기가 반드시 구현해야 하는 최상위 인터페이스.
    
    Strategy Pattern의 기반이 되며, 외부 시스템(TransformerService)은
    오직 이 인터페이스에만 의존하여 데이터 변환 작업을 수행합니다.
    """

    @abstractmethod
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """데이터 변환 작업을 수행합니다.
        
        결측치 처리, 스케일링, 병합 등의 전처리 과정을 수행하고 변환된 데이터프레임을 반환합니다.

        Args:
            data (pd.DataFrame): 변환 로직을 수행할 대상 입력 데이터프레임.

        Returns:
            pd.DataFrame: 변환 로직이 모두 적용된 결과 데이터프레임.
            
        Raises:
            TransformerError: 데이터 변환 과정에서 발생한 모든 예외.
        """
        pass

class ILoader(ABC):
    """모든 데이터 적재기가 반드시 구현해야 하는 최상위 인터페이스.
    
    Service Layer(예: LoaderService)는 외부 인프라에 종속되지 않도록
    오직 이 인터페이스에만 의존하여 다형성을 확보합니다.
    """

    @abstractmethod
    def load(self, dto: ExtractedDTO) -> bool:
        """데이터 적재 작업을 수행합니다.
        
        Args:
            dto (ExtractedDTO): 이전 단계(Transform)에서 전달된 정제된 데이터 전송 객체.

        Returns:
            bool: 적재 성공 여부.
            
        Raises:
            LoaderError: 적재 과정에서 발생한 모든 예외.
        """
        pass