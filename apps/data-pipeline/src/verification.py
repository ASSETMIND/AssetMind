from src.common.config import get_config

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

if __name__ == "__main__":
    config_verification()