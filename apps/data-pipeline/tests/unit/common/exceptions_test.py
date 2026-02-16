import pytest
from typing import Dict, Any

# [Target Modules]
from src.common.exceptions import (
    ETLError,
    ConfigurationError,
    ExtractorError,
    TransformerError,
    LoaderError,
    NetworkConnectionError,
    HttpError,
    RateLimitError,
    AuthError
)

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture
def base_error_message():
    return "Test Error Message"

@pytest.fixture
def large_payload():
    """500자를 초과하는 대용량 더미 데이터 생성"""
    return "A" * 600

# ========================================================================================
# 1. 기반 로직 테스트 (Base Logic & Serialization)
# ========================================================================================

def test_base_01_serialization(base_error_message):
    """[BASE-01] [Serialization] to_dict 호출 시 필수 키(error_type, message 등) 존재 검증"""
    # Given
    error = ETLError(message=base_error_message, should_retry=True)
    
    # When
    result = error.to_dict()
    
    # Then
    assert result["error_type"] == "ETLError"
    assert result["message"] == base_error_message
    assert result["should_retry"] is True
    assert "details" in result
    assert "cause" in result

def test_base_02_chaining(base_error_message):
    """[BASE-02] [Chaining] 원인 예외(Original Exception)가 있을 경우 cause 필드에 문자열로 기록"""
    # Given
    original = ValueError("Root Cause Error")
    error = ETLError(message=base_error_message, original_exception=original)
    
    # When
    result = error.to_dict()
    
    # Then
    assert result["cause"] == "Root Cause Error"
    assert error.original_exception is original

def test_base_03_formatting(base_error_message):
    """[BASE-03] [Formatting] __str__ 호출 시 'Caused by' 문구가 포함된 디버깅용 문자열 반환"""
    # Given
    original = KeyError("Missing Key")
    error = ETLError(message=base_error_message, original_exception=original)
    
    # When
    debug_str = str(error)
    
    # Then
    # 형식: "[ETLError] Test Error Message (Caused by: KeyError)"
    assert "[ETLError]" in debug_str
    assert base_error_message in debug_str
    assert "(Caused by: KeyError)" in debug_str

def test_base_04_formatting_no_cause(base_error_message):
    """[BASE-04] [Formatting/Branch] original_exception이 없을 때 'Caused by' 문구 생략 검증"""
    # Given
    error = ETLError(message=base_error_message, original_exception=None)
    
    # When
    debug_str = str(error)
    
    # Then
    assert "[ETLError]" in debug_str
    assert base_error_message in debug_str
    assert "Caused by" not in debug_str

# ========================================================================================
# 2. 데이터 축약 테스트 (Data Truncation & BVA)
# ========================================================================================

def test_trunc_01_body_under_limit():
    """[TRUNC-01] [BVA] HTTP Body 길이가 499자(Under)일 때 원본 유지"""
    # Given
    body = "A" * 499
    
    # When
    error = HttpError("Error", status_code=500, response_body=body)
    result = error.to_dict()
    
    # Then
    preview = result["details"]["response_body_preview"]
    assert len(preview) == 499
    assert preview == body
    assert "truncated" not in preview

def test_trunc_02_body_exact_limit():
    """[TRUNC-02] [BVA] HTTP Body 길이가 500자(Exact)일 때 원본 유지 (잘리지 않음)"""
    # Given
    body = "A" * 500
    
    # When
    error = HttpError("Error", status_code=500, response_body=body)
    result = error.to_dict()
    
    # Then
    preview = result["details"]["response_body_preview"]
    assert len(preview) == 500
    assert preview == body
    assert "truncated" not in preview

def test_trunc_03_body_over_limit():
    """[TRUNC-03] [BVA] HTTP Body 길이가 501자(Over)일 때 500자로 자르고 접미사 추가"""
    # Given
    body = "A" * 501
    
    # When
    error = HttpError("Error", status_code=500, response_body=body)
    result = error.to_dict()
    
    # Then
    preview = result["details"]["response_body_preview"]
    # 500자 + "...(truncated)"(13자) = 513자 예상
    assert len(preview) > 500
    assert preview.startswith("A" * 500)
    assert preview.endswith("...(truncated)")

def test_trunc_04_body_none():
    """[TRUNC-04] [Defensive] HTTP Body가 None일 경우 'Empty' 문자열로 안전하게 처리"""
    # Given
    body = None
    
    # When
    error = HttpError("Error", status_code=404, response_body=body)
    result = error.to_dict()
    
    # Then
    assert result["details"]["response_body_preview"] == "Empty"

# ========================================================================================
# 3. 계층 및 속성 테스트 (Hierarchy & Properties)
# ========================================================================================

def test_prop_01_config_error_details():
    """[PROP-01] [Property] ConfigurationError 생성 시 key_name이 details에 주입됨"""
    # Given
    key = "DB_HOST"
    
    # When
    error = ConfigurationError("Config Missing", key_name=key)
    result = error.to_dict()
    
    # Then
    assert result["details"]["key_name"] == key
    assert error.should_retry is False

def test_prop_02_network_error_details():
    """[PROP-02] [Property] NetworkConnectionError 생성 시 url이 details에 주입됨"""
    # Given
    url = "http://api.test.com"
    
    # When
    error = NetworkConnectionError("DNS Fail", url=url)
    result = error.to_dict()
    
    # Then
    assert result["details"]["url"] == url
    assert error.should_retry is True

def test_prop_03_ratelimit_retry_policy():
    """[PROP-03] [Policy] RateLimitError는 재시도 정책(True)과 retry_after 값을 가짐"""
    # Given
    retry_seconds = 120
    
    # When
    error = RateLimitError(retry_after=retry_seconds)
    result = error.to_dict()
    
    # Then
    assert error.should_retry is True
    assert result["details"]["retry_after"] == retry_seconds
    assert result["details"]["status_code"] == 429

def test_hier_01_auth_inheritance():
    """[HIER-01] [Inheritance] AuthError가 HttpError 및 ExtractorError의 하위 클래스임을 검증"""
    # Given
    error = AuthError("Login Failed")
    
    # When & Then
    assert isinstance(error, HttpError)
    assert isinstance(error, ExtractorError)
    assert isinstance(error, ETLError)
    
    # AuthError는 재시도하지 않음 (401/403은 영구적 오류로 취급)
    assert error.should_retry is False