import pytest
from dataclasses import is_dataclass, asdict
from typing import Dict, Any

# 대상 모듈 임포트
from src.common.dtos import SourceType, RequestDTO, ExtractedDTO, TransformedDTO

# --------------------------------------------------------------------------
# Test Strategy: DTO Integrity & Schema Validation
# --------------------------------------------------------------------------

class TestDomainDTOs:
    """
    [TCS-DTO-001] 도메인 데이터 전송 객체(DTO) 정합성 테스트
    각 단계별 데이터 계약(Contract)이 명세대로 동작하는지 검증합니다.
    """

    # ==========================================
    # Category: Schema & Structure (Static)
    # ==========================================

    def test_tc001_dto_is_dataclass(self):
        """[TC-001] 모든 DTO가 dataclass로 정의되어 있는지 확인"""
        assert is_dataclass(RequestDTO)
        assert is_dataclass(ExtractedDTO)
        assert is_dataclass(TransformedDTO)

    def test_tc002_source_type_enum(self):
        """[TC-002] SourceType Enum 정의 및 값 일치 확인"""
        assert SourceType.KIS.value == "KIS"
        assert SourceType.FRED.value == "FRED"
        assert SourceType.UNKNOWN.value == "UNKNOWN"

    # ==========================================
    # Category: RequestDTO (Initialization)
    # ==========================================

    def test_tc003_request_dto_init(self):
        """[TC-003] RequestDTO: 필수 인자(job_id) 및 기본값(params) 검증"""
        # Given
        job_id = "TASK_20231027"
        params = {"symbol": "005930", "timeframe": "D"}

        # When
        dto = RequestDTO(job_id=job_id, params=params)

        # Then
        assert dto.job_id == job_id
        assert dto.params["symbol"] == "005930"
        assert isinstance(dto.params, dict)

    def test_tc004_request_dto_default_params(self):
        """[TC-004] RequestDTO: params 미지정 시 빈 딕셔너리 생성 확인"""
        # When
        dto = RequestDTO(job_id="MINIMAL_TASK")
        
        # Then
        assert dto.params == {}
        # 팩토리 메서드 동작 확인 (독립성)
        dto.params["new"] = True
        assert RequestDTO(job_id="OTHER").params == {}

    # ==========================================
    # Category: ExtractedDTO (Extraction Phase)
    # ==========================================

    def test_tc005_extracted_dto_payload(self):
        """[TC-005] ExtractedDTO: 원본 데이터(Raw Data) 저장 및 메타데이터 검증"""
        # Given
        raw_data = {"price": 70000, "volume": 1000000}
        meta = {"source": SourceType.KIS.value, "latency": 0.5}

        # When
        dto = ExtractedDTO(data=raw_data, meta=meta)

        # Then
        assert dto.data == raw_data
        assert dto.meta["source"] == "KIS"
        assert dto.data["price"] == 70000

    def test_tc006_extracted_dto_nullable_data(self):
        """[TC-006] ExtractedDTO: 데이터가 None일 경우에도 안전하게 생성됨을 확인"""
        # When
        dto = ExtractedDTO()
        
        # Then
        assert dto.data is None
        assert dto.meta == {}

    # ==========================================
    # Category: TransformedDTO (Transformation Phase)
    # ==========================================

    def test_tc007_transformed_dto_clean_data(self):
        """[TC-007] TransformedDTO: 정제된 데이터 및 변환 규칙 기록 확인"""
        # Given
        clean_data = [10.5, 11.2, 10.8]
        transform_meta = {"rule": "standardization", "scale": 1.0}

        # When
        dto = TransformedDTO(data=clean_data, meta=transform_meta)

        # Then
        assert dto.data == clean_data
        assert dto.meta["rule"] == "standardization"

    # ==========================================
    # Category: Robustness & Data Integrity
    # ==========================================

    def test_tc008_dto_serialization_ready(self):
        """[TC-008] DTO가 asdict를 통해 직렬화 가능한 구조인지 검증"""
        # Given
        dto = ExtractedDTO(data="test_data", meta={"id": 1})

        # When
        dict_form = asdict(dto)

        # Then
        assert dict_form == {"data": "test_data", "meta": {"id": 1}}
        assert isinstance(dict_form, dict)

    @pytest.mark.parametrize("dto_class", [RequestDTO, ExtractedDTO, TransformedDTO])
    def test_tc009_field_independence(self, dto_class):
        """[TC-009] [BVA] field(default_factory=dict)를 통한 인스턴스 간 딕셔너리 독립성 보장 확인"""
        # Given
        instance_a = dto_class(job_id="A") if dto_class == RequestDTO else dto_class()
        instance_b = dto_class(job_id="B") if dto_class == RequestDTO else dto_class()

        # When [Fix] 속성 존재 여부를 확인한 후 안전하게 할당
        if hasattr(instance_a, 'meta'):
            instance_a.meta["key"] = "value"
        if hasattr(instance_a, 'params'):
            instance_a.params["key"] = "value"

        # Then
        if hasattr(instance_b, 'meta'):
            assert "key" not in instance_b.meta
        if hasattr(instance_b, 'params'):
            assert "key" not in instance_b.params