import os
import boto3
import pytest
from botocore.exceptions import ClientError

# src 모듈 경로를 찾기 위해 sys.path 설정이 필요할 수 있으나, 
# docker에서 실행 시 PYTHONPATH를 설정하거나 상대 경로 import를 사용합니다.
# 여기서는 가장 간단하게 환경 변수 기반으로 클라이언트를 직접 생성하거나
# src/s3_client.py를 import 하여 사용합니다.

from src.s3_client import get_s3_client

@pytest.fixture
def s3_bucket():
    """테스트용 버킷 이름을 반환하고, 테스트 전 버킷 존재를 보장하는 Fixture"""
    bucket_name = os.getenv("BUCKET_NAME", "test-bucket")
    client = get_s3_client()
    
    # 버킷이 확실히 있는지 확인 (MinIO 초기화 스크립트가 만들었겠지만 안전장치)
    try:
        client.head_bucket(Bucket=bucket_name)
    except ClientError:
        client.create_bucket(Bucket=bucket_name)
        
    return bucket_name

def test_s3_connection():
    """1. S3/MinIO 연결 및 버킷 목록 조회 테스트"""
    client = get_s3_client()
    response = client.list_buckets()
    
    assert 'Buckets' in response
    print("\n✅ 연결 성공. 버킷 목록 조회 완료.")

def test_upload_and_download(s3_bucket):
    """2. 파일 업로드 -> 다운로드 -> 내용 일치 검증 테스트"""
    client = get_s3_client()
    
    file_key = "test_data/hello.txt"
    content = "Hello MinIO! This is a test."
    
    # 2-1. 업로드 (String -> Bytes)
    print(f"\n📤 업로드 테스트: {file_key}")
    client.put_object(Bucket=s3_bucket, Key=file_key, Body=content.encode('utf-8'))
    
    # 2-2. 다운로드 및 검증
    print(f"📥 다운로드 테스트: {file_key}")
    response = client.get_object(Bucket=s3_bucket, Key=file_key)
    read_content = response['Body'].read().decode('utf-8')
    
    # 검증 (Assertion)
    assert read_content == content
    print(f"✅ 데이터 무결성 확인 완료: {read_content}")

def test_file_cleanup(s3_bucket):
    """3. 테스트 후 파일 삭제 확인 (선택 사항)"""
    client = get_s3_client()
    file_key = "test_data/hello.txt"
    
    client.delete_object(Bucket=s3_bucket, Key=file_key)
    
    # 삭제되었는지 확인 (삭제 후 조회 시 에러가 나야 정상 404)
    with pytest.raises(ClientError) as e:
        client.head_object(Bucket=s3_bucket, Key=file_key)
    
    assert str(e.value.response['Error']['Code']) == "404"
    print("✅ 테스트 파일 삭제 확인 완료.")