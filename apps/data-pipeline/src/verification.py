from src.common.config import get_config
from src.extractor.domain.interfaces import IAuthStrategy, IHttpClient
from src.extractor.providers.kis_extractor import KISExtractor
from typing import Any, Dict

class MockHttpClient(IHttpClient):
    """실제 네트워크 요청을 보내지 않는 테스트용 HTTP 클라이언트"""
    async def get(self, url: str, headers: Dict[str, str], params: Dict[str, Any]) -> Any:
        return {"rt_cd": "0", "msg1": "Mock Success"}

    async def post(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Any:
        return {"rt_cd": "0", "msg1": "Mock Success"}

class MockAuthStrategy(IAuthStrategy):
    """인증 과정을 생략하고 더미 토큰을 반환하는 테스트용 전략"""
    async def get_token(self, http_client: IHttpClient) -> str:
        return "Bearer MOCK_TOKEN"

def config_verification():
    """설정 모듈의 정상 동작 여부를 확인하는 내부 함수."""
    print("="*60)
    print(">>> [Step 1] Configuration Loading Started...")
    print("="*60)

    # 테스트할 Task Name 지정 (configs/extractor.yml 파일이 있어야 함)
    target_task = "extractor"

    try:
        # 1. 설정 로드 시도
        config = get_config(task_name=target_task)
        print(f"✅ AppConfig loaded successfully for task: '{config.task_name}'")
        print("-" * 60 + "\n")

    except Exception as e:
        print(f"❌ CRITICAL ERROR: Failed to load config. \n{e}")
        return

    # 2. YAML 정책 확인
    print(f">>> [Step 2] Verifying YAML Policies ({target_task}.yml)")
    policies = config.extraction_policy
    
    if not policies:
        print(f"⚠️ WARNING: No policies found. Check 'configs/{target_task}.yml'.")
    else:
        print(f"🔍 Found {len(policies)} job(s):\n")
        for job_id, policy in policies.items():
            print(f"🔹 Job ID: [{job_id}]")
            print(f"   • Provider    : {policy.provider}")
            print(f"   • Path        : {policy.path}")
            print("   ------------------------------------------------")
    print("\n")

    print("✅ Verification Completed.")

def kis_extractor_verification():
    print("="*80)
    print(">>> [Step 1] Configuration Loading Verification")
    print("="*80)

    target_task = "extractor"
    
    try:
        config = get_config(task_name=target_task)
        print(f"✅ AppConfig Loaded Successfully!")
        print(f"   - Task Name: {config.task_name}")
        print(f"   - Policy Count: {len(config.extraction_policy)}")
        print("-" * 80 + "\n")
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Failed to load config. \n{e}")
        return

    print("="*80)
    print(">>> [Step 2] KIS Extractor Initialization & Policy Mapping Verification")
    print("="*80)

    # 1. Mock 의존성 주입 및 Extractor 생성
    mock_http = MockHttpClient()
    mock_auth = MockAuthStrategy()

    try:
        # KISExtractor가 AppConfig를 올바르게 참조하는지 테스트
        extractor = KISExtractor(
            http_client=mock_http, 
            auth_strategy=mock_auth, 
            config=config
        )
        print("✅ KISExtractor Instantiated Successfully!")
        
        # 2. Global KIS Setting 확인
        print(f"   - Base URL: {config.kis.base_url}")
        print(f"   - App Key:  {'[PROTECTED]' if config.kis.app_key.get_secret_value() else '[MISSING]'}")
        print("\n")

    except Exception as e:
        print(f"❌ ERROR: Failed to initialize KISExtractor. Check your 'config.py' and 'kis_extractor.py' compatibility.")
        print(f"Details: {e}")
        return

    # 3. KIS 관련 정책 전수 조사 및 출력
    print(">>> [Step 3] Verifying Collected KIS Policies (Details)")
    
    kis_policies = {
        k: v for k, v in config.extraction_policy.items() 
        if v.provider == "KIS"
    }

    if not kis_policies:
        print("⚠️ WARNING: No KIS policies found in 'extractor.yml'.")
    else:
        print(f"🔍 Found {len(kis_policies)} KIS Job(s). Printing details...\n")
        
        for job_id, policy in kis_policies.items():
            print(f"🔹 [Job ID] {job_id}")
            print(f"   • Description : {policy.description}")
            print(f"   • Endpoint    : {config.kis.base_url}{policy.path}")
            print(f"   • TR_ID       : {policy.tr_id}")
            print(f"   • Params      : {policy.params}")
            
            # 도메인 구분 확인 (국내/해외)
            domain_label = policy.domain if policy.domain else "N/A"
            print(f"   • Domain      : {domain_label}")
            print("   ----------------------------------------------------------------------------")

    print("\n✅ Verification Completed.")


if __name__ == "__main__":
    #config_verification()
    kis_extractor_verification()