import pytest
import asyncio
import inspect
import sys
from abc import ABC
from typing import Dict, Any, Optional
from unittest.mock import MagicMock

# ========================================================================================
# [Pre-setup] 의존성 모듈 Mocking
# ========================================================================================
mock_dtos = MagicMock()
mock_dtos.RequestDTO = type("RequestDTO", (), {})
mock_dtos.ExtractedDTO = type("ExtractedDTO", (), {})
sys.modules["src.common.dtos"] = mock_dtos

# [Target Modules]
from src.common.interfaces import IHttpClient, IAuthStrategy, IExtractor
from src.common.dtos import RequestDTO, ExtractedDTO

# ========================================================================================
# [Mocks & Stubs] 테스트를 위한 정상 구현체 정의
# ========================================================================================

class ValidHttpClient(IHttpClient):
    """IHttpClient의 정상 구현체"""
    async def get(self, url: str, headers: Optional[Dict] = None, params: Optional[Dict] = None) -> Any:
        return "GET_OK"

    async def post(self, url: str, headers: Optional[Dict] = None, data: Optional[Dict] = None) -> Any:
        return "POST_OK"

class ValidAuthStrategy(IAuthStrategy):
    """IAuthStrategy의 정상 구현체"""
    async def get_token(self, http_client: IHttpClient) -> str:
        return "Bearer test_token"

class ValidExtractor(IExtractor):
    """IExtractor의 정상 구현체"""
    async def extract(self, request: RequestDTO) -> ExtractedDTO:
        return ExtractedDTO()

# ========================================================================================
# 1. 아키텍처 강제성 테스트 (Architecture Enforcement)
# ========================================================================================

def test_arch_01_prevent_direct_instantiation():
    """[ARCH-01] [Architecture] 추상 클래스(IHttpClient)는 직접 인스턴스화할 수 없으며 TypeError 발생"""
    # Given: 추상 클래스 IHttpClient 자체
    
    # When & Then: 인스턴스화 시도 시 TypeError 발생 확인
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IHttpClient()

def test_arch_02_partial_implementation_http():
    """[ARCH-02] [BVA] get만 구현하고 post를 누락한 구현체는 인스턴스화 차단"""
    # Given: 추상 메서드 중 일부(post)만 구현하지 않은 불완전한 클래스 정의
    class PartialClient(IHttpClient):
        async def get(self, url, headers=None, params=None):
            return "ok"
    
    # When & Then: 인스턴스화 시도 시 TypeError 발생 확인
    # Python 3.12+ 대응: 메서드명 주변의 따옴표('') 유무를 모두 허용하는 정규식 사용 (.?post.?)
    with pytest.raises(TypeError, match="abstract method .?post.?"):
        PartialClient()

def test_arch_03_bad_extractor_implementation():
    """[ARCH-03] [BVA] extract 메서드를 누락한 IExtractor 구현체는 인스턴스화 차단"""
    # Given: 필수 메서드(extract)를 구현하지 않은 잘못된 클래스 정의
    class BadExtractor(IExtractor):
        def some_other_method(self):
            pass
    
    # When & Then: 인스턴스화 시도 시 TypeError 발생 확인
    with pytest.raises(TypeError, match="abstract method .?extract.?"):
        BadExtractor()

# ========================================================================================
# 2. 인터페이스 준수 및 동작 테스트 (Interface Compliance)
# ========================================================================================

@pytest.mark.asyncio
async def test_impl_01_valid_http_client():
    """[IMPL-01] [Standard] IHttpClient 정상 구현체는 정의된 비동기 메서드 호출 가능"""
    # Given: 모든 추상 메서드를 구현한 정상 클래스
    client = ValidHttpClient()
    
    # When & Then: 메서드 호출 시 정상적으로 값을 반환해야 함
    assert await client.get("http://test.com") == "GET_OK"
    assert await client.post("http://test.com") == "POST_OK"

@pytest.mark.asyncio
async def test_impl_02_valid_auth_strategy():
    """[IMPL-02] [Standard] IAuthStrategy 정상 구현체는 토큰 반환 가능"""
    # Given: 정상 구현체 준비
    strategy = ValidAuthStrategy()
    mock_client = ValidHttpClient()
    
    # When: 토큰 요청
    token = await strategy.get_token(mock_client)
    
    # Then: 예상된 토큰 값 반환
    assert token == "Bearer test_token"

@pytest.mark.asyncio
async def test_impl_03_valid_extractor():
    """[IMPL-03] [Standard] IExtractor 정상 구현체는 DTO 반환 가능"""
    # Given: 정상 구현체 및 요청 객체 준비
    extractor = ValidExtractor()
    request = RequestDTO()
    
    # When: 추출 요청
    result = await extractor.extract(request)
    
    # Then: ExtractedDTO 타입의 객체 반환 확인
    assert isinstance(result, ExtractedDTO)

# ========================================================================================
# 3. 비동기 계약 및 메타데이터 테스트 (Async Contract & Metadata)
# ========================================================================================

def test_async_01_coroutine_enforcement():
    """[ASYNC-01] [Contract] 인터페이스의 모든 주요 메서드는 비동기(Coroutine)로 선언되어야 함"""
    # Given: 검증 대상이 되는 주요 인터페이스 메서드 목록
    target_methods = [
        IHttpClient.get,
        IHttpClient.post,
        IAuthStrategy.get_token,
        IExtractor.extract
    ]
    
    # When & Then: 각 메서드가 코루틴 함수인지 검사
    for method in target_methods:
        assert inspect.iscoroutinefunction(method), f"{method.__name__} must be a coroutine"

def test_type_01_annotations_check():
    """[TYPE-01] [Data] 인터페이스 메서드의 타입 힌트가 DTO 클래스를 올바르게 참조하는지 검증"""
    # Given: 메서드의 타입 힌트(Annotations) 추출
    extract_annotations = IExtractor.extract.__annotations__
    auth_annotations = IAuthStrategy.get_token.__annotations__
    
    # Then: 매개변수와 반환 타입이 올바른 DTO/Interface를 가리키는지 확인
    assert extract_annotations['request'] == RequestDTO
    assert extract_annotations['return'] == ExtractedDTO
    assert auth_annotations['http_client'] == IHttpClient

@pytest.mark.asyncio
async def test_err_01_exception_propagation():
    """[ERR-01] [Robustness] 구현체 내부 예외가 인터페이스 레벨에서 차단되지 않고 전파됨"""
    # Given: 실행 중 고의로 예외를 발생시키는 구현체 정의
    class BrokenExtractor(IExtractor):
        async def extract(self, request):
            raise ValueError("Extraction Failed")
            
    extractor = BrokenExtractor()
    
    # When & Then: 인터페이스 메서드 호출 시 예외가 그대로 전달되는지 확인
    with pytest.raises(ValueError, match="Extraction Failed"):
        await extractor.extract(RequestDTO())

# ========================================================================================
# 4. 추상 메서드 실행 테스트 (Coverage Completeness)
# ========================================================================================

@pytest.mark.asyncio
async def test_arch_04_base_method_execution():
    """[ARCH-04] [Coverage] 추상 메서드의 기본 구현(pass)을 super()로 호출하여 모든 라인 커버리지 달성.
    
    Note: 일반적인 구현체는 오버라이딩을 하므로 부모의 pass 구문이 실행되지 않습니다.
    커버리지 100%를 달성하기 위해 super()를 호출하는 특수 구현체를 사용하여 부모 메서드를 실행합니다.
    """
    
    # 1. IHttpClient Base Execution
    # Given: super()를 호출하는 HttpClient
    class SuperHttpClient(IHttpClient):
        async def get(self, url, headers=None, params=None):
            return await super().get(url, headers, params)
        
        async def post(self, url, headers=None, data=None):
            return await super().post(url, headers, data)

    client = SuperHttpClient()
    # When & Then: 기본 구현 실행 (Return None 확인)
    assert await client.get("url") is None
    assert await client.post("url") is None

    # 2. IAuthStrategy Base Execution
    # Given: super()를 호출하는 AuthStrategy
    class SuperAuthStrategy(IAuthStrategy):
        async def get_token(self, http_client):
            return await super().get_token(http_client)

    auth = SuperAuthStrategy()
    # When & Then
    assert await auth.get_token(client) is None

    # 3. IExtractor Base Execution
    # Given: super()를 호출하는 Extractor
    class SuperExtractor(IExtractor):
        async def extract(self, request):
            return await super().extract(request)

    extractor = SuperExtractor()
    # When & Then
    assert await extractor.extract(RequestDTO()) is None