import pytest
import io
import json
from unittest.mock import MagicMock, patch
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
    """
    [핵심 수정] 
    데코레이터 평가 시점 문제를 해결하기 위해, log_decorator 모듈 내부가 참조하는 
    LogManager 자체를 Mocking하여 ConfigManager 연쇄 호출 에러를 원천 차단합니다.
    """
    with patch("src.common.decorators.log_decorator.LogManager") as mock_dec_log, \
         patch("src.loader.providers.abstract_loader.LogManager") as mock_abs_log:
        yield

@pytest.fixture
def mock_config():
    """정상적인 S3 버킷 정보가 포함된 ConfigManager 모방 객체"""
    config_mock = MagicMock()
    def mock_get(key, default=None):
        if key == "aws.s3.bucket_name":
            return "toss-datalake-raw-zone-prd"
        if key == "aws.region":
            return "ap-northeast-2"
        return default
    config_mock.get.side_effect = mock_get
    return config_mock

@pytest.fixture
def boto3_client_mock():
    """AWS 비용 발생 및 네트워크 I/O를 차단하기 위한 Boto3 Mock"""
    with patch("src.loader.providers.s3_loader.boto3.client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def s3_loader(mock_config, boto3_client_mock):
    """기본 설정이 주입되고 Boto3가 Mocking된 S3Loader 인스턴스"""
    return S3Loader(mock_config)


# ========================================================================================
# 1. 초기화 및 설정 테스트 (Initialization)
# ========================================================================================

def test_init_01_success(mock_config, boto3_client_mock):
    """[INIT-01] 정상 설정 주입 시 에러 없이 S3Loader 및 Boto3 클라이언트 초기화"""
    loader = S3Loader(mock_config)
    assert loader._bucket_name == "toss-datalake-raw-zone-prd"
    assert loader._boto3_client is not None

def test_init_02_missing_bucket(mock_config):
    """[INIT-02] [예외] 버킷 이름 누락 시 ConfigurationError 조기 발생 (Fail-Fast)"""
    mock_config.get.side_effect = lambda k, d=None: None if k == "aws.s3.bucket_name" else d
    with pytest.raises(ConfigurationError, match="S3 버킷 이름이 설정 파일에 누락되었습니다"):
        S3Loader(mock_config)

def test_init_03_boto_error_wrapping(mock_config):
    """[INIT-03] [래핑] Boto3 초기화 중 예외 발생 시 ConfigurationError로 래핑 (Line 136-137 커버)"""
    # [수정] 명확하게 BotoCoreError 인스턴스를 발생시켜 정확히 except 블록에 걸리도록 유도
    with patch("src.loader.providers.s3_loader.boto3.client", side_effect=BotoCoreError()):
        with pytest.raises(ConfigurationError, match="AWS 설정 오류"):
            S3Loader(mock_config)


# ========================================================================================
# 2. 파이프라인 통합 오케스트레이션 및 무결성 검증 테스트 (Orchestration & Validation)
# ========================================================================================

def test_apply_load_success(s3_loader, boto3_client_mock):
    """[APPLY-01] [통합] _apply_load 호출 시 키 생성, 압축, 업로드 연동 정상 (Line 151-174 커버)"""
    # Given
    dto = MockExtractedDTO(data={"value": 1}, meta={"provider": "kis", "job_id": "kospi"})
    
    # When
    result = s3_loader._apply_load(dto)
    
    # Then
    assert result is True
    boto3_client_mock.upload_fileobj.assert_called_once()
    
    # 동적 생성된 S3 키(Hive 파티셔닝) 검증
    kwargs = boto3_client_mock.upload_fileobj.call_args.kwargs
    assert "raw/provider=kis/job=kospi/" in kwargs["Key"]

def test_val_01_valid_dto(s3_loader):
    """[VAL-01] data와 meta가 모두 존재하는 정상 DTO"""
    valid_dto = MockExtractedDTO(data={"value": 1}, meta={"provider": "kis", "job_id": "kospi"})
    assert s3_loader._validate_dto(valid_dto) is True

def test_val_02_no_data(s3_loader):
    """[VAL-02] [BVA] data 속성이 None인 경우 검증 실패"""
    invalid_dto = MockExtractedDTO(data=None, meta={"provider": "kis", "job_id": "kospi"})
    assert s3_loader._validate_dto(invalid_dto) is False

def test_val_03_invalid_meta_type(s3_loader):
    """[VAL-03] meta 속성이 dict가 아닌 경우 검증 실패"""
    invalid_dto = MockExtractedDTO(data={"value": 1}, meta=["kis", "kospi"])
    assert s3_loader._validate_dto(invalid_dto) is False

def test_val_04_missing_meta_keys(s3_loader):
    """[VAL-04] [스키마] meta에 필수 파티셔닝 키가 누락된 경우 검증 실패"""
    invalid_dto = MockExtractedDTO(data={"value": 1}, meta={"provider": "kis"})
    assert s3_loader._validate_dto(invalid_dto) is False


# ========================================================================================
# 3. 직렬화 및 압축 테스트 (Serialization & Compression)
# ========================================================================================

@pytest.mark.parametrize("input_data", [
    {"key": "value"},                
    "plain text data",               
    b"binary payload"                
])
def test_comp_01_serialize_types(s3_loader, input_data):
    """[COMP-01] [동등분할] 데이터 타입별 직렬화 및 Zstd 압축 정상 처리"""
    compressed_bytes = s3_loader._compress_to_zstd_stream(input_data)
    assert isinstance(compressed_bytes, bytes)
    assert len(compressed_bytes) > 0

def test_comp_02_unserializable_wrapping(s3_loader):
    """[COMP-02] [래핑] JSON 직렬화 불가 객체 주입 시 ZstdCompressionError 발생"""
    class Unserializable: pass
    with pytest.raises(ZstdCompressionError, match="직렬화하는 데 실패"):
        s3_loader._compress_to_zstd_stream(Unserializable())

def test_comp_03_memory_error_wrapping(s3_loader):
    """[COMP-03] [래핑] 압축 중 MemoryError 발생 시 에러 래핑"""
    with patch("src.loader.providers.s3_loader.zstd.ZstdCompressor.compress", side_effect=MemoryError("OOM")):
        with pytest.raises(ZstdCompressionError, match="메모리 부족"):
            s3_loader._compress_to_zstd_stream(b"test data")

def test_comp_04_unknown_error_wrapping(s3_loader):
    """[COMP-04] [래핑] 압축 중 알 수 없는 시스템 예외 발생 시 에러 래핑"""
    with patch("src.loader.providers.s3_loader.zstd.ZstdCompressor.compress", side_effect=Exception("Unknown Crash")):
        with pytest.raises(ZstdCompressionError, match="예기치 않은 오류 발생"):
            s3_loader._compress_to_zstd_stream(b"test data")


# ========================================================================================
# 4. S3 적재 테스트 (Upload)
# ========================================================================================

@pytest.mark.parametrize("stream_size", [
    100,                        
    11 * 1024 * 1024            
])
def test_upl_01_success_both_sizes(s3_loader, boto3_client_mock, stream_size):
    """[UPL-01] [BVA] 임계값(10MB) 미만 및 이상의 데이터에 대해 upload_fileobj 정상 호출"""
    dummy_stream = b"0" * stream_size
    result = s3_loader._execute_multipart_upload(dummy_stream, "raw/test.zst")
    
    assert result is True
    boto3_client_mock.upload_fileobj.assert_called_once()

def test_upl_02_client_error_wrapping(s3_loader, boto3_client_mock):
    """[UPL-02] [래핑] S3 업로드 중 ClientError 발생 시 S3UploadError 래핑"""
    error_response = {'Error': {'Code': 'AccessDenied'}}
    boto3_client_mock.upload_fileobj.side_effect = ClientError(error_response, 'UploadPart')
    
    with pytest.raises(S3UploadError, match="Boto3 ClientError 발생"):
        s3_loader._execute_multipart_upload(b"test", "raw/test.zst")

def test_upl_03_unknown_error_wrapping(s3_loader, boto3_client_mock):
    """[UPL-03] [래핑] 멀티파트 업로드 중 네이티브 에러 발생 시 래핑 (Line 261-262 커버)"""
    boto3_client_mock.upload_fileobj.side_effect = Exception("Connection Reset by Peer")
    
    with pytest.raises(S3UploadError, match="예기치 않은 네이티브 오류 발생"):
        s3_loader._execute_multipart_upload(b"test", "raw/test.zst")