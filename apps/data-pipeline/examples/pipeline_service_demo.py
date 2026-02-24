"""
[Pipeline Service 통합 데모]

이 스크립트는 확정된 DTO 기반의 PipelineService가 정상 동작하는지 검증합니다.
설정 파일(extractor_demo.yml)을 읽어 배치 작업을 수행하고, 결과를 리포팅합니다.
"""

import sys
import asyncio
from pathlib import Path

# [System Path Setup]
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from src.common.log import LogManager
from src.common.config import ConfigManager
from src.pipeline_service import PipelineService

def print_report(summary: dict):
    """실행 결과를 가독성 있게 출력합니다."""
    print("\n" + "=" * 60)
    print(f" [배치 파이프라인 결과 리포트]")
    print(f" - 전체 작업 수 : {summary['total']}")
    print(f" - 성공 작업 수 : {summary['success']}")
    print(f" - 실패 작업 수 : {summary['fail']}")
    print("-" * 60)
    
    for item in summary['details']:
        # 상태에 따른 아이콘 표시
        if item['status'] == "SUCCESS":
            icon = "✅"
        elif "FAIL" in item['status']:
            icon = "❌"
        else:
            icon = "❓"
            
        error_msg = f" | Error: {item['error']}" if item['error'] else ""
        print(f" {icon} [{item['job_id']:<25}] Status: {item['status']}{error_msg}")
        
    print("=" * 60 + "\n")

async def main():
    # 1. 로거 초기화
    config = ConfigManager.get_config("extractor_demo")
    logger = LogManager.get_logger("PipelineDemo")
    logger.info(">>> [Start] Pipeline Service Demo 시작")

    # 2. 파이프라인 실행 (Context Manager 사용)
    # 'extractor_demo' 태스크 설정을 로드합니다.
    async with PipelineService("extractor_demo") as pipeline:
        
        # 3. 배치 작업 실행
        result_summary = await pipeline.run_batch()
        
        # 4. 결과 출력
        print_report(result_summary)

    logger.info(">>> [End] Pipeline Service Demo 종료")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ 사용자에 의해 중단되었습니다.")