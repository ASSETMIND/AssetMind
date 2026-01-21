import os
from s3_client import get_s3_client

def run():
    bucket_name = os.getenv("BUCKET_NAME")
    s3 = get_s3_client()

    print(f"🚀 연결 시도: {bucket_name}")
    
    try:
        # 버킷 리스트 조회
        response = s3.list_buckets()
        print("✅ 연결 성공! 버킷 목록:")
        for bucket in response['Buckets']:
            print(f"- {bucket['Name']}")
            
    except Exception as e:
        print(f"❌ 연결 실패: {e}")

if __name__ == "__main__":
    run()