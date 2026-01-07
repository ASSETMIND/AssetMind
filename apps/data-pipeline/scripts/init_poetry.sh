#!/bin/bash
set -e # 에러 발생 시 즉시 종료

echo "📦 Poetry 환경 초기화를 시작합니다..."

# 1. Poetry 설치 여부 확인
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry가 설치되어 있지 않습니다."
    exit 1
fi

# [중요] Mac 로컬 환경에서는 반드시 가상환경을 사용하도록 강제 설정
# 이 설정은 프로젝트 내의 poetry.toml 파일에 저장되며, 전역 설정을 덮음
echo "🔧 로컬 가상환경 설정을 강제합니다 (virtualenvs.create = true)..."
poetry config virtualenvs.create true --local

# 2. pyproject.toml 존재 여부 확인 및 생성
if [ ! -f "pyproject.toml" ]; then
    echo "📄 pyproject.toml이 없습니다. 새로 생성합니다..."
    
    # 비대화형(non-interactive) 모드로 초기화
    poetry init --name "data-pipeline" \
                --description "S3/MinIO Data Pipeline" \
                --author "Kim Jun-su" \
                --python "^3.12" \
                --no-interaction
else
    echo "✅ pyproject.toml이 이미 존재합니다."
fi

# 3. 필수 라이브러리 추가
# 가상환경이 켜져 있으므로 시스템 Python 충돌 없이 설치
echo "📚 의존성 라이브러리(boto3) 확인 및 추가..."
poetry add boto3

echo "🧪 테스트 라이브러리(pytest) 확인 및 추가..."
poetry add --group dev pytest

echo "🔒 Lock 파일 생성 및 갱신..."
poetry lock

echo "🎉 Poetry 환경 설정이 완료되었습니다."