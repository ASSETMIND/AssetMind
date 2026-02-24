"""
[도메인 데이터 전송 객체 (Domain DTOs)]

ETL 파이프라인의 각 단계(Extraction, Transformation, Loading) 간 
명확한 데이터 계약(Contract)을 정의하는 모듈입니다.

데이터 흐름 (Data Flow):
1. RequestDTO (요청 정보) 
   -> [Extractor] 
2. ExtractDTO (수집된 원본 데이터) 
   -> [Transformer] 
3. TransformedDTO (정제된 데이터) 
   -> [Loader] 

설계 원칙:
1. Immutability: 데이터 오염 방지를 위해 기본적으로 변경 불가능하도록 설계.
2. Separation of Concerns: 각 단계별로 필요한 데이터만 포함.
3. Simplicity: 필수적인 성공 여부와 데이터만 유지 (불필요한 메타데이터 제외).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

# ==============================================================================
# 1. 공통 기반 타입 (Shared Types)
# ==============================================================================

class SourceType(Enum):
    """데이터 수집 원천(Source) 식별자."""
    KIS = "KIS"            # 한국투자증권
    FRED = "FRED"          # 미 연준 경제 데이터
    ECOS = "ECOS"          # 한국은행
    UPBIT = "UPBIT"        # 암호화폐 거래소
    UNKNOWN = "UNKNOWN"    # 알 수 없음

# ==============================================================================
# 2. ETL DTOS
# ==============================================================================

@dataclass
class RequestDTO:
    """수집기(Extractor)에 전달되는 요청 정보."""
    job_id: str                                           # 실행할 작업 ID
    params: Dict[str, Any] = field(default_factory=dict)  # 실행 파라미터 (기간, 종목코드 등)


@dataclass
class ExtractedDTO:
    """[E] 수집 단계 결과: 원본 데이터(Raw Data) 포함."""
    data: Any = None                                    # 수집된 원본 데이터 (JSON, List, Dict 등)
    meta: Dict[str, Any] = field(default_factory=dict)  # 메타데이터 (성공 여부, 타임스탬프 등)

@dataclass
class TransformedDTO:
    """[T] 변환 단계 결과: 정제된 데이터(Cleaned Data) 포함."""
    data: Any = None                                    # 정규화 및 전처리가 완료된 데이터
    meta: Dict[str, Any] = field(default_factory=dict)  # 메타데이터 (변환 규칙, 타임스탬프 등)