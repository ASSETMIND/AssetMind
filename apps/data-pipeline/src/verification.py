from src.common.config import get_config
from src.extractor.domain.interfaces import IAuthStrategy, IHttpClient
from src.extractor.providers.kis_extractor import KISExtractor
from src.extractor.providers.fred_extractor import FREDExtractor
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

def verify_config():
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

def verify_extractor(target_provider: str = "KIS"):
    """특정 Provider에 대한 설정 및 Extractor 초기화를 검증합니다.

    Args:
        target_provider (str): 'KIS' 또는 'FRED'
    """
    target_provider = target_provider.upper()
    print("="*80)
    print(f">>> [Verification Start] Target Provider: {target_provider}")
    print("="*80)

    # -----------------------------------------------------
    # Step 1. Configuration Loading
    # -----------------------------------------------------
    print(f"\n>>> [Step 1] Loading Configuration...")
    try:
        config = get_config(task_name="extractor")
        print(f"✅ AppConfig Loaded Successfully!")
        print(f"   - Task Name: {config.task_name}")
        print(f"   - Total Policies: {len(config.extraction_policy)}")
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Failed to load config. \n{e}")
        return

    # -----------------------------------------------------
    # Step 2. Extractor Initialization (Dependency Injection)
    # -----------------------------------------------------
    print(f"\n>>> [Step 2] Initializing {target_provider} Extractor...")

    mock_http = MockHttpClient()
    mock_auth = MockAuthStrategy()
    extractor = None

    try:
        if target_provider == "KIS":
            # KIS는 AuthStrategy가 필수
            extractor = KISExtractor(
                http_client=mock_http, 
                auth_strategy=mock_auth, 
                config=config
            )
            # KIS Global Config Check
            is_key_present = bool(config.kis.app_key.get_secret_value())
            print(f"✅ KISExtractor Instantiated.")
            print(f"   - Base URL: {config.kis.base_url}")
            print(f"   - App Key:  {'[PROTECTED]' if is_key_present else '[MISSING]'}")

        elif target_provider == "FRED":
            # FRED는 AuthStrategy 불필요 (Config 내 API Key 사용)
            extractor = FREDExtractor(
                http_client=mock_http,
                config=config
            )
            # FRED Global Config Check
            is_key_present = bool(config.fred.api_key.get_secret_value())
            print(f"✅ FREDExtractor Instantiated.")
            print(f"   - Base URL: {config.fred.base_url}")
            print(f"   - API Key:  {'[PROTECTED]' if is_key_present else '[MISSING]'}")
        
        else:
            print(f"❌ ERROR: Unknown provider type '{target_provider}'")
            return

    except Exception as e:
        print(f"❌ ERROR: Failed to initialize {target_provider} Extractor.")
        print(f"Details: {e}")
        return

    # -----------------------------------------------------
    # Step 3. Policy Mapping Verification
    # -----------------------------------------------------
    print(f"\n>>> [Step 3] Verifying {target_provider} Policies in YAML")
    
    # Provider 일치하는 정책 필터링
    target_policies = {
        k: v for k, v in config.extraction_policy.items() 
        if v.provider == target_provider
    }

    if not target_policies:
        print(f"⚠️ WARNING: No policies found for provider '{target_provider}'. Check 'extractor.yml'.")
    else:
        print(f"🔍 Found {len(target_policies)} Job(s). Printing details...\n")
        
        for job_id, policy in target_policies.items():
            print(f"🔹 [Job ID] {job_id}")
            print(f"   • Description : {policy.description}")
            
            # URL 조합 시뮬레이션
            base_url = config.kis.base_url if target_provider == "KIS" else config.fred.base_url
            full_path = f"{base_url}{policy.path}"
            print(f"   • Endpoint    : {full_path}")

            # Provider별 핵심 속성 출력 분기
            if target_provider == "KIS":
                print(f"   • TR_ID       : {policy.tr_id}")
                print(f"   • Domain      : {policy.domain}")
            
            elif target_provider == "FRED":
                # FRED는 params 안에 핵심 정보(series_id)가 있음
                s_id = policy.params.get('series_id', 'MISSING')
                freq = policy.params.get('frequency', 'N/A')
                print(f"   • Series ID   : {s_id}")
                print(f"   • Frequency   : {freq}")

            print(f"   • Params      : {policy.params}")
            print("   ----------------------------------------------------------------------------")

    print(f"\n✅ [{target_provider}] Verification Completed.")
    print("\n" + " " * 80 + "\n")


if __name__ == "__main__":
    #verify_config()
    #verify_extractor(target_provider="KIS")
    verify_extractor(target_provider="FRED")