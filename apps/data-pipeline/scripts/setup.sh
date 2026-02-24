#!/bin/bash
set -e

# 스크립트 위치가 어디서 실행되든 정확한 경로를 찾기 위해 변수 설정
SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

echo "🚀 전체 시스템 셋업 및 테스트를 시작합니다."

# 1. Poetry 환경 초기화 (init_poetry.sh 호출)
echo "------------------------------------------------"
"$SCRIPT_DIR/init_poetry.sh"
echo "------------------------------------------------"

# 2. Docker Compose 빌드 및 실행 (백그라운드 실행)
echo "🐳 Docker Compose 실행 중..."
cd "$PROJECT_ROOT"
docker compose up -d --build

# 3. MinIO 초기화 및 서버 기동 대기
echo "⏳ 서버가 준비될 때까지 잠시 대기합니다 (10초)..."
sleep 10

# 4. 컨테이너 내부에서 테스트 코드 실행
echo "🧪 Docker 컨테이너 내부에서 테스트를 수행합니다..."
# python-pipeline 컨테이너 내에서 pytest 실행
# -v: 상세 출력, -s: print문 출력 허용
docker compose exec -T data-pipeline python -m pytest -v -s tests/s3_test.py

echo "------------------------------------------------"
if [ $? -eq 0 ]; then
    echo "✅ 모든 테스트가 성공적으로 완료되었습니다!"
    echo "📡 MinIO Console: http://localhost:9001 (ID/PW 확인: .env)"
else
    echo "❌ 테스트 실패. 로그를 확인해주세요."
    exit 1
fi