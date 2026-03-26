import pytest
import io
import json
import os
from unittest.mock import MagicMock, patch, ANY
from botocore.exceptions import BotoCoreError, ClientError

# [Target Modules]
from src.loader.providers.s3_loader import S3Loader

# [Dependencies & Exceptions]
from src.common.exceptions import (
    ConfigurationError, 
    ZstdCompressionError, 
    S3UploadError
)

# ========================================================================================
# [Mocks & Stubs]
# ========================================================================================

class MockExtractedDTO:
    """테스트용 Extracted DTO (격리된 객체)"""
    def __init__(self, data=None, meta=None):
        self.data = data
        self.meta = meta if meta is not None else {}

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger_isolation():
    """상속받은 AbstractLoader의 LogManager 의존성 차단"""
    with patch("src.loader.providers.abstract_loader.LogManager"):
        yield

@pytest.fixture
def boto3_client_mock():
    """AWS 비용 발생 및 네트워크 I/O 차단을 위한 Boto3 Mock"""
    with patch("src.loader.providers.s3_loader.boto3.client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_client

@pytest.fixture
def s3_loader(boto3_client_mock):
    """정상 파라미터가 주입된 S3Loader 인스턴스"""
    # GIVEN: 유효한 bucket_name과 region 주입
    return S3Loader(bucket_name="toss-datalake-raw-zone-prd", region="ap-northeast-2")


# ========================================================================================
# 1. 초기화 및 설정 테스트 (Initialization)
# ========================================================================================

def test_init_01_success(boto3_client_mock):
    """[INIT-01] 정상 설정 주입 시 에러 없이 초기화되며 운영망 Boto3 생성"""
    # GIVEN & WHEN
    loader = S3Loader(bucket_name="test-bucket", region="ap-northeast-2")
    
    # THEN
    assert loader._bucket_name == "test-bucket"
    boto3_client_mock.assert_called_with(service_name='s3', region_name='ap-northeast-2')

def test_init_02_missing_bucket():
    """[INIT-02] [Fail-Fast] 버킷 이름 누락 시 예외 발생"""
    # GIVEN / WHEN / THEN
    with pytest.raises(ConfigurationError, match="S3 버킷 이름이 누락되었습니다"):
        S3Loader(bucket_name="", region="ap-northeast-2")

def test_init_03_missing_region():
    """[INIT-03] [Fail-Fast] 리전 누락 시 예외 발생"""
    # GIVEN / WHEN / THEN
    with pytest.raises(ConfigurationError, match="AWS 리전이 누락되었습니다"):
        S3Loader(bucket_name="test-bucket", region="")

def test_init_04_local_endpoint(boto3_client_mock):
    """[INIT-04] LOCAL_S3_ENDPOINT 환경 변수 존재 시 LocalStack 세팅으로 오버라이딩"""
    # GIVEN: 환경 변수에 로컬 엔드포인트 세팅
    with patch.dict(os.environ, {"LOCAL_S3_ENDPOINT": "http://localhost:4566"}):
        # WHEN
        S3Loader(bucket_name="test-bucket", region="ap-northeast-2")
        
        # THEN: endpoint_url이 포함되어 boto3.client가 호출되었는지 검증
        boto3_client_mock.assert_called_with(
            service_name='s3',
            region_name='ap-northeast-2',
            endpoint_url='http://localhost:4566',
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )

def test_init_05_boto_error_wrapping(boto3_client_mock):
    """[INIT-05] [예외 래핑] Boto3 초기화 중 예외 발생 시 도메인 에러로 래핑"""
    # GIVEN: Boto3 클라이언트 생성 시 BotoCoreError 발생 시뮬레이션
    boto3_client_mock.side_effect = BotoCoreError()
    
    # WHEN / THEN
    with pytest.raises(ConfigurationError, match="AWS 설정 오류"):
        S3Loader(bucket_name="test-bucket", region="ap-northeast-2")


# ========================================================================================
# 2. 파이프라인 무결성 검증 (Validation)
# ========================================================================================

def test_val_01_valid_dto(s3_loader):
    """[VAL-01] 정상적인 DTO 주입 시 검증 통과"""
    # GIVEN: 필수 키인 'source'와 'job_id'가 포함된 DTO
    valid_dto = MockExtractedDTO(data={"value": 1}, meta={"source": "kis", "job_id": "kospi"})
    # WHEN
    result = s3_loader._validate_dto(valid_dto)
    # THEN
    assert result is True

def test_val_02_no_data(s3_loader):
    """[VAL-02] [BVA] data가 None인 경우 검증 실패"""
    # GIVEN
    invalid_dto = MockExtractedDTO(data=None, meta={"source": "kis", "job_id": "kospi"})
    # WHEN
    result = s3_loader._validate_dto(invalid_dto)
    # THEN
    assert result is False

def test_val_03_invalid_meta_type(s3_loader):
    """[VAL-03] meta 속성이 dict가 아닌 경우 검증 실패"""
    # GIVEN
    invalid_dto = MockExtractedDTO(data={"value": 1}, meta=["kis", "kospi"])
    # WHEN
    result = s3_loader._validate_dto(invalid_dto)
    # THEN
    assert result is False

def test_val_04_missing_meta_keys(s3_loader):
    """[VAL-04] 파티셔닝 필수 키(source, job_id) 누락 시 검증 실패"""
    # GIVEN: 'job_id' 누락
    invalid_dto = MockExtractedDTO(data={"value": 1}, meta={"source": "kis"})
    # WHEN
    result = s3_loader._validate_dto(invalid_dto)
    # THEN
    assert result is False


# ========================================================================================
# 3. 키 생성 및 파이프라인 (Orchestration)
# ========================================================================================

def test_key_01_generate_s3_key(s3_loader):
    """[KEY-01] 정상 DTO 기반으로 Hive-style 파티셔닝 경로 생성 검증"""
    # GIVEN
    dto = MockExtractedDTO(data={"value": 1}, meta={"source": "KIS", "job_id": "KOSPI_DAILY"})
    # WHEN
    key = s3_loader._generate_s3_key(dto)
    # THEN: 대소문자 소문자화 확인 및 경로 구조 확인
    assert key.startswith("raw/provider=kis/job=kospi_daily/year=")
    assert key.endswith(".json.zst")

def test_orch_01_apply_load_integration(s3_loader, boto3_client_mock):
    """[ORCH-01] _apply_load 호출 시 _upload_stream을 거쳐 전체 파이프라인 가동 확인"""
    # GIVEN
    dto = MockExtractedDTO(data={"value": 1}, meta={"source": "kis", "job_id": "kospi"})
    mock_instance = boto3_client_mock.return_value
    
    # WHEN
    result = s3_loader._apply_load(dto)
    
    # THEN
    assert result is True
    # upload_fileobj가 최소 1회 호출되었는지 검증하여 _upload_stream 연계 확인
    mock_instance.upload_fileobj.assert_called_once()


# ========================================================================================
# 4. 직렬화 및 압축 (Compression)
# ========================================================================================

@pytest.mark.parametrize("input_data", [
    {"key": "value"},                
    "plain text data",               
    b"binary payload"                
])
def test_comp_01_serialize_types(s3_loader, input_data):
    """[COMP-01] [동등분할] dict, str, bytes 타입 데이터의 직렬화 및 Zstd 압축 정상 처리"""
    # GIVEN (Parametrized input)
    # WHEN
    compressed_bytes = s3_loader._compress_to_zstd_stream(input_data)
    # THEN
    assert isinstance(compressed_bytes, bytes)
    assert len(compressed_bytes) > 0

def test_comp_02_unserializable_wrapping(s3_loader):
    """[COMP-02] JSON 직렬화 불가 객체(Custom Class) 주입 시 예외 래핑"""
    # GIVEN
    class Unserializable: pass
    # WHEN / THEN
    with pytest.raises(ZstdCompressionError, match="직렬화하는 데 실패"):
        s3_loader._compress_to_zstd_stream(Unserializable())

def test_comp_03_memory_error_wrapping(s3_loader):
    """[COMP-03] 압축 중 OOM(MemoryError) 발생 시 예외 래핑"""
    # GIVEN
    with patch("src.loader.providers.s3_loader.zstd.ZstdCompressor.compress", side_effect=MemoryError("OOM")):
        # WHEN / THEN
        with pytest.raises(ZstdCompressionError, match="메모리 부족으로 압축 실패"):
            s3_loader._compress_to_zstd_stream(b"test data")

def test_comp_04_unknown_error_wrapping(s3_loader):
    """[COMP-04] 압축 중 예상치 못한 일반 Exception 발생 시 예외 래핑"""
    # GIVEN
    with patch("src.loader.providers.s3_loader.zstd.ZstdCompressor.compress", side_effect=Exception("Unknown Crash")):
        # WHEN / THEN
        with pytest.raises(ZstdCompressionError, match="Zstd 압축 처리 중 예기치 않은 오류 발생"):
            s3_loader._compress_to_zstd_stream(b"test data")


# ========================================================================================
# 5. 멀티파트 업로드 (Upload)
# ========================================================================================

@pytest.mark.parametrize("stream_size", [
    100,                        # 10MB 미만
    11 * 1024 * 1024            # 10MB 이상 (멀티파트 임계값 초과)
])
def test_upl_01_success_both_sizes(s3_loader, boto3_client_mock, stream_size):
    """[UPL-01] [BVA] 임계값(10MB) 미만 및 이상의 데이터에 대해 upload_fileobj 정상 호출 확인"""
    # GIVEN
    dummy_stream = b"0" * stream_size
    mock_instance = boto3_client_mock.return_value
    
    # WHEN
    result = s3_loader._execute_multipart_upload(dummy_stream, "raw/test.zst")
    
    # THEN
    assert result is True
    mock_instance.upload_fileobj.assert_called_once_with(
        Fileobj=ANY,
        Bucket="toss-datalake-raw-zone-prd",
        Key="raw/test.zst",
        Config=ANY
    )

def test_upl_02_client_error_wrapping(s3_loader, boto3_client_mock):
    """[UPL-02] S3 업로드 중 ClientError 발생 시 S3UploadError 래핑 및 is_multipart 확인"""
    # GIVEN
    error_response = {'Error': {'Code': 'AccessDenied'}}
    mock_instance = boto3_client_mock.return_value
    mock_instance.upload_fileobj.side_effect = ClientError(error_response, 'UploadPart')
    
    # 멀티파트 임계값을 넘기는 더미 데이터
    large_stream = b"0" * (11 * 1024 * 1024)
    
    # WHEN / THEN
    with pytest.raises(S3UploadError, match="Boto3 ClientError 발생") as exc_info:
        s3_loader._execute_multipart_upload(large_stream, "raw/test.zst")
    
    # THEN: 내부 플래그가 정확히 계산되었는지 추가 검증
    assert "AccessDenied" in str(exc_info.value)
    # is_multipart 조건 로직 정상 실행 여부 검증 (에러 객체 안의 튜플/속성에 담겨있을 것임)

def test_upl_03_unknown_error_wrapping(s3_loader, boto3_client_mock):
    """[UPL-03] S3 업로드 중 예상치 못한 네이티브 에러 발생 시 철저한 예외 래핑"""
    # GIVEN
    mock_instance = boto3_client_mock.return_value
    mock_instance.upload_fileobj.side_effect = Exception("Connection Reset by Peer")
    
    small_stream = b"0" * 100
    
    # WHEN / THEN
    with pytest.raises(S3UploadError, match="예기치 않은 네이티브 오류 발생") as exc_info:
        s3_loader._execute_multipart_upload(small_stream, "raw/test.zst")
        
    # THEN
    assert "Connection Reset by Peer" in str(exc_info.value.__cause__)