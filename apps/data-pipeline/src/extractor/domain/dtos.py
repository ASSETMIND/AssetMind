from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

class SourceType(Enum):
    """데이터 수집 원천(Source)을 정의하는 열거형."""
    KIS = "KIS"        # 한국투자증권
    KRX = "KRX"        # 한국거래소
    OVERSEAS = "OVERSEAS"  # 해외 데이터 소스 (Yahoo Finance 등)

@dataclass
class RequestDTO:
    """데이터 추출 요청 정보를 담는 데이터 전송 객체 (Data Transfer Object).
    
    Extractor 계층으로 데이터를 요청할 때 필요한 모든 파라미터를 캡슐화합니다.
    
    Attributes:
        ticker (str): 종목 코드 (예: '005930').
        source (SourceType): 데이터를 수집할 원천 소스 타입.
        start_date (Optional[str]): 조회 시작 날짜 (YYYYMMDD).
        end_date (Optional[str]): 조회 종료 날짜 (YYYYMMDD).
        period (str): 데이터 주기 (D:일, W:주, M:월). 기본값은 'D'.
        extra_params (Dict[str, Any]): 소스별 특화된 추가 파라미터를 담기 위한 딕셔너리.
    """
    ticker: str
    source: SourceType
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    period: str = "D"
    extra_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResponseDTO:
    """데이터 추출 결과를 표준화하여 반환하는 객체.
    
    모든 Extractor는 내부 로직과 상관없이 반드시 이 형태로 결과를 반환해야 합니다.
    
    Attributes:
        ticker (str): 요청된 종목 코드.
        source (SourceType): 데이터가 수집된 원천 소스.
        data (List[Dict[str, Any]]): 실제 파싱된 데이터 리스트 (OHLCV 등).
        raw_data (Optional[Any]): 디버깅용 원본 응답 데이터 (선택 사항).
        success (bool): 수집 성공 여부.
        message (str): 실패 시 에러 메시지 또는 성공 메시지.
    """
    ticker: str
    source: SourceType
    data: List[Dict[str, Any]]
    raw_data: Optional[Any] = None
    success: bool = True
    message: str = ""