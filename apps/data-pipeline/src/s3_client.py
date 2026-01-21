import os
import boto3
from botocore.exceptions import NoCredentialsError

def get_s3_client():
    """
    환경 변수에 따라 자동으로 MinIO 또는 AWS S3 클라이언트를 반환합니다.
    """
    # .env에서 환경 변수 로드
    endpoint_url = os.getenv("ENDPOINT_URL")
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_DEFAULT_REGION")

    # 근거: Boto3 문서 - endpoint_url이 제공되면 해당 URL(MinIO) 사용, 
    # None이면 기본 AWS 엔드포인트 사용.
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html
    
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url if endpoint_url else None, # 핵심 로직
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )
    
    return s3_client

# 테스트용 함수
if __name__ == "__main__":
    s3 = get_s3_client()
    print(f"Current Endpoint: {s3.meta.endpoint_url}")