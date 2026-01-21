"""
데이터 전송 객체 모듈 (Data Transfer Objects)

계층 간(Service <-> Extractor) 데이터 교환을 위한 표준 객체를 정의합니다.
설정 주도(Configuration-Driven) 아키텍처를 지원하기 위해, 고정된 필드 대신
작업 식별자(job_id)와 유연한 파라미터 딕셔너리를 사용합니다.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from enum import Enum

class SourceType(Enum):
    """데이터 수집 원천(Source)을 정의하는 열거형.
    Factory에서 Extractor 구현체를 선택할 때 사용됩니다.
    """
    KIS = "KIS"            # 한국투자증권
    KRX = "KRX"            # 한국거래소
    OVERSEAS = "OVERSEAS"  # 해외 데이터 소스

@dataclass
class RequestDTO:
    """데이터 수집 요청 정보를 담는 DTO.

    특정 API나 데이터 소스에 종속되지 않는 범용 구조를 가집니다.

    Attributes:
        job_id (str): 설정 파일(YAML)에 정의된 수집 정책을 식별하는 키.
                      (예: 'kis_daily_price', 'krx_market_cap')
        params (Dict[str, Any]): 수집에 필요한 동적 파라미터 집합.
                                 (예: {'symbol': '005930', 'date': '20240101'})
    """
    job_id: str
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResponseDTO:
    """데이터 수집(Extraction) 단계의 결과를 담는 DTO.

    E 단계는 데이터를 해석하거나 변형하지 않고 원본 그대로 전달하는 것을 원칙으로 하므로,
    Raw Data를 담을 수 있는 유연한 구조를 가집니다.

    Attributes:
        data (Any): 수집된 원본 데이터. (JSON Dict, Text, Bytes 등)
        meta (Dict[str, Any]): 데이터의 출처, 수집 시각, 응답 코드 등 메타데이터.
    """
    data: Any
    meta: Dict[str, Any] = field(default_factory=dict)