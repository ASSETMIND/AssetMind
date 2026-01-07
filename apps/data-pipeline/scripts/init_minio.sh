#!/bin/sh

# 에러 발생 시 스크립트 중단
set -e

echo "⏳ MinIO 서버($ENDPOINT_URL)가 시작될 때까지 대기 중..."

# MinIO Client(mc)의 alias 설정
# mc alias set [별칭] [URL] [ID] [PW]
mc alias set myminio $ENDPOINT_URL $AWS_ACCESS_KEY_ID $AWS_SECRET_ACCESS_KEY

echo "✅ MinIO 서버 연결 성공"

# 버킷 존재 여부 확인 후 생성
if mc ls myminio/$BUCKET_NAME > /dev/null 2>&1; then
    echo "⚠️ 버킷($BUCKET_NAME)이 이미 존재합니다."
else
    echo "📦 버킷($BUCKET_NAME)을 생성합니다..."
    mc mb myminio/$BUCKET_NAME
    echo "✅ 버킷 생성 완료!"
fi