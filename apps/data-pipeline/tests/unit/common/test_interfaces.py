import pytest
import asyncio
import inspect
import sys
from abc import ABC
from typing import Dict, Any, Optional
from unittest.mock import MagicMock

# ========================================================================================
# [Pre-setup] 의존성 모듈 Mocking (Fail-Safe)
# ========================================================================================
# 1. DTO Mocking
mock_dtos = MagicMock()
mock_dtos.RequestDTO = type("RequestDTO", (), {})
mock_dtos.ExtractedDTO = type("ExtractedDTO", (), {})
sys.modules["src.common.dtos"] = mock_dtos

# 2. Pandas Mocking (테스트 환경에 pandas가 없어도 통과하도록 처리)
mock_pd = MagicMock()
mock_pd.DataFrame = type("DataFrame", (), {})
sys.modules["pandas"] = mock_pd

# [Target Modules]
import pandas as pd
from src.common.interfaces import IHttpClient, IAuthStrategy, IExtractor, ILoader, ITransformer
from src.common.dtos import RequestDTO, ExtractedDTO

# ========================================================================================
# [Mocks & Stubs] 테스트를 위한 정상 구현체 정의
# ========================================================================================

class ValidHttpClient(IHttpClient):
    async def get(self, url: str, headers: Optional[Dict] = None, params: Optional[Dict] = None) -> Any:
        return "GET_OK"
    async def post(self, url: str, headers: Optional[Dict] = None, data: Optional[Dict] = None) -> Any:
        return "POST_OK"

class ValidAuthStrategy(IAuthStrategy):
    async def get_token(self, http_client: IHttpClient) -> str:
        return "Bearer test_token"

class ValidExtractor(IExtractor):
    async def extract(self, request: RequestDTO) -> ExtractedDTO:
        return ExtractedDTO()

class ValidTransformer(ITransformer):
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        return data

class ValidLoader(ILoader):
    def load(self, dto: ExtractedDTO) -> bool:
        return True

# ========================================================================================
# 1. IHttpClient 인터페이스 테스트
# ========================================================================================

def test_http_01_prevent_direct_instantiation():
    """[HTTP-01] [표준] IHttpClient 직접 인스턴스화 차단"""
    # Given: IHttpClient 추상 클래스
    # When & Then: 인스턴스화 시도 시 TypeError 발생
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IHttpClient()

def test_http_02_partial_implementation():
    """[HTTP-02] [BVA] get만 구현하고 post를 누락한 구현체 인스턴스화 차단"""
    # Given: 불완전한 구현체 정의
    class PartialClient(IHttpClient):
        async def get(self, url, headers=None, params=None): return "ok"
    
    # When & Then: TypeError 및 누락된 메서드(post) 명시 확인
    with pytest.raises(TypeError, match="abstract method .?post.?"):
        PartialClient()

@pytest.mark.asyncio
async def test_http_03_base_method_execution():
    """[HTTP-03] [커버리지] super()를 호출하여 추상 메서드 내부(pass) 실행 -> 커버리지 100%"""
    # Given: super()를 호출하는 특수 구현체
    class SuperHttpClient(IHttpClient):
        async def get(self, url, headers=None, params=None):
            return await super().get(url, headers, params)
        async def post(self, url, headers=None, data=None):
            return await super().post(url, headers, data)
            
    client = SuperHttpClient()
    # When & Then: 예외 없이 None 반환 (pass 구문 도달)
    assert await client.get("url") is None
    assert await client.post("url") is None

def test_http_04_coroutine_enforcement():
    """[HTTP-04] [계약] 메서드가 반드시 비동기로 선언되어야 함"""
    # Given: 대상 메서드
    target_methods = [IHttpClient.get, IHttpClient.post]
    # When & Then: 코루틴 검사 True
    for method in target_methods:
        assert inspect.iscoroutinefunction(method) is True

# ========================================================================================
# 2. IAuthStrategy 인터페이스 테스트
# ========================================================================================

def test_auth_01_prevent_direct_instantiation():
    """[AUTH-01] [표준] IAuthStrategy 직접 인스턴스화 차단"""
    # When & Then
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IAuthStrategy()

def test_auth_02_partial_implementation():
    """[AUTH-02] [BVA] get_token을 누락한 구현체 인스턴스화 차단"""
    # Given
    class BadAuth(IAuthStrategy): pass
    # When & Then
    with pytest.raises(TypeError, match="abstract method .?get_token.?"):
        BadAuth()

@pytest.mark.asyncio
async def test_auth_03_valid_implementation():
    """[AUTH-03] [표준] 정상 구현체의 인터페이스 메서드 호출 및 커버리지(super) 검증"""
    # Given: 일반 호출 검증
    strategy = ValidAuthStrategy()
    assert await strategy.get_token(ValidHttpClient()) == "Bearer test_token"
    
    # Given: 커버리지용 super() 호출
    class SuperAuthStrategy(IAuthStrategy):
        async def get_token(self, http_client):
            return await super().get_token(http_client)
            
    # When & Then: 부모 pass 실행 확인
    assert await SuperAuthStrategy().get_token(ValidHttpClient()) is None

def test_auth_04_coroutine_enforcement():
    """[AUTH-04] [계약] get_token 메서드가 비동기인지 검증"""
    # When & Then
    assert inspect.iscoroutinefunction(IAuthStrategy.get_token) is True

# ========================================================================================
# 3. IExtractor 인터페이스 테스트
# ========================================================================================

def test_ext_01_prevent_direct_instantiation():
    """[EXT-01] [표준] IExtractor 직접 인스턴스화 차단"""
    # When & Then
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IExtractor()

def test_ext_02_partial_implementation():
    """[EXT-02] [BVA] extract 누락 시 인스턴스화 차단"""
    # Given
    class BadExtractor(IExtractor): pass
    # When & Then
    with pytest.raises(TypeError, match="abstract method .?extract.?"):
        BadExtractor()

def test_ext_03_annotations_check():
    """[EXT-03] [데이터] 타입 힌트가 DTO를 올바르게 참조하는지 검사"""
    # Given
    annotations = IExtractor.extract.__annotations__
    # When & Then
    assert annotations['request'] == RequestDTO
    assert annotations['return'] == ExtractedDTO

def test_ext_04_coroutine_enforcement():
    """[EXT-04] [계약] extract 메서드가 비동기인지 검증 (및 super 커버리지)"""
    # 비동기 계약 검증
    assert inspect.iscoroutinefunction(IExtractor.extract) is True
    
@pytest.mark.asyncio
async def test_ext_05_base_method_execution():
    """[EXT-추가] [커버리지] super()를 이용해 IExtractor 부모 메서드 실행 검증"""
    # Given
    class SuperExtractor(IExtractor):
        async def extract(self, request):
            return await super().extract(request)
    # When & Then
    assert await SuperExtractor().extract(RequestDTO()) is None

# ========================================================================================
# 4. ITransformer 인터페이스 테스트
# ========================================================================================

def test_trf_01_prevent_direct_instantiation():
    """[TRF-01] [표준] ITransformer 직접 인스턴스화 차단"""
    # Given: ITransformer 추상 클래스
    # When & Then: 인스턴스화 시 TypeError
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        ITransformer()

def test_trf_02_partial_implementation():
    """[TRF-02] [BVA] transform 누락 시 인스턴스화 차단"""
    # Given: transform을 구현하지 않은 클래스
    class BadTransformer(ITransformer): pass
    # When & Then
    with pytest.raises(TypeError, match="abstract method .?transform.?"):
        BadTransformer()

def test_trf_03_sync_contract():
    """[TRF-03] [계약] CPU 연산이므로 transform은 동기(Sync) 함수여야 함"""
    # Given & When: iscoroutinefunction 검사
    is_async = inspect.iscoroutinefunction(ITransformer.transform)
    # Then: 비동기가 아님을 증명(False)
    assert is_async is False

def test_trf_04_annotations_check():
    """[TRF-04] [데이터] 타입 힌트가 pd.DataFrame을 올바르게 참조하는지 검사"""
    # Given: 애노테이션 추출
    annotations = ITransformer.transform.__annotations__
    # When & Then: 입출력이 모두 pd.DataFrame인지 확인
    assert annotations['data'] == pd.DataFrame
    assert annotations['return'] == pd.DataFrame

def test_trf_05_exception_propagation():
    """[TRF-05] [견고성] 예외가 인터페이스 레벨에서 삼켜지지 않고 전파되는지 확인 + 커버리지(super)"""
    # Given 1: 예외 발생 구현체
    class BrokenTransformer(ITransformer):
        def transform(self, data):
            raise ValueError("Transform Error")
            
    transformer = BrokenTransformer()
    dummy_df = pd.DataFrame()
    
    # When & Then 1: 예외 전파 확인
    with pytest.raises(ValueError, match="Transform Error"):
        transformer.transform(dummy_df)
        
    # Given 2: 커버리지용 super() 호출 (부모의 pass 로직 도달)
    class SuperTransformer(ITransformer):
        def transform(self, data):
            return super().transform(data)
            
    # When & Then 2: 에러 없이 None 반환 (pass 실행 증명)
    assert SuperTransformer().transform(dummy_df) is None

# ========================================================================================
# 5. ILoader 인터페이스 테스트
# ========================================================================================

def test_ldr_01_prevent_direct_instantiation():
    """[LDR-01] [표준] ILoader 직접 인스턴스화 차단"""
    # Given: ILoader 추상 클래스
    # When & Then: 직접 인스턴스화 시도 시 TypeError 발생
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        ILoader()

def test_ldr_02_partial_implementation():
    """[LDR-02] [BVA] load 메서드 누락 시 인스턴스화 차단"""
    # Given: 필수 추상 메서드(load)를 구현하지 않은 하위 클래스
    class BadLoader(ILoader): pass
    
    # When & Then: TypeError 발생 및 누락된 메서드 이름(load) 검증
    with pytest.raises(TypeError, match="abstract method .?load.?"):
        BadLoader()

def test_ldr_03_sync_contract():
    """[LDR-03] [계약] 제공된 시그니처에 따라 load는 동기(Sync) 함수여야 함"""
    # Given & When: load 메서드의 코루틴(비동기) 여부 검사
    is_async = inspect.iscoroutinefunction(ILoader.load)
    
    # Then: 비동기 함수가 아님을 증명 (False 반환)
    assert is_async is False

def test_ldr_04_annotations_check():
    """[LDR-04] [데이터] 타입 힌트가 ExtractedDTO와 bool을 올바르게 참조하는지 검사"""
    # Given: load 메서드의 애노테이션 딕셔너리 추출
    annotations = ILoader.load.__annotations__
    
    # When & Then: 파라미터 타입과 반환 타입이 강제된 규격과 일치하는지 확인
    assert annotations['dto'] == ExtractedDTO
    assert annotations['return'] == bool

def test_ldr_05_exception_propagation():
    """[LDR-05] [견고성] 예외가 삼켜지지 않고 전파되는지 확인 및 super() 분기 커버리지 100% 달성"""
    # Given 1: 테스트용 도메인 에러 및 이를 발생시키는 구현체
    class LoaderError(Exception): pass 
    
    class BrokenLoader(ILoader):
        def load(self, dto: ExtractedDTO) -> bool:
            raise LoaderError("Load Error")
            
    loader = BrokenLoader()
    dummy_dto = ExtractedDTO()
    
    # When & Then 1: 인터페이스에서 예외를 억제하지 않고 그대로 상위로 전파하는지 확인
    with pytest.raises(LoaderError, match="Load Error"):
        loader.load(dummy_dto)
        
    # Given 2: 커버리지 확보를 위해 부모의 추상 메서드(pass)를 호출하는 구현체
    class SuperLoader(ILoader):
        def load(self, dto: ExtractedDTO) -> bool:
            return super().load(dto)
            
    # When & Then 2: 에러 없이 실행되며 부모의 빈 반환값(None)을 정상적으로 가져오는지 확인
    assert SuperLoader().load(dummy_dto) is None