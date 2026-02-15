"""
Adapter Integration Test Script (KIS Target)

이 스크립트는 Infrastructure Layer(HTTP Adapter, Auth Strategy)가 
실제 타겟 시스템(KIS API)과 정상적으로 통신할 수 있는지 검증합니다.

Domain Layer(Extractor)를 거치지 않고 직접 헤더와 URL을 조립하여 요청함으로써,
비즈니스 로직의 간섭 없이 순수 네트워크 및 인증 상태를 진단합니다.

검증 흐름 (Verification Flow):
1. Config Load: .env 및 adapter_demo.yml 로드.
2. Auth: KISAuthStrategy를 통해 Access Token 발급 (or 캐시 사용).
3. Request Construction: Token, AppKey, Secret, TR_ID를 헤더에 수동 주입.
4. Execution: AsyncHttpAdapter를 통해 실제 API 호출.
5. Verification: HTTP 200 OK 및 응답 본문의 rt_cd(결과 코드) 확인.

Usage:
    python examples/adapter_demo.py
"""

import sys
import asyncio
from pathlib import Path
from typing import Dict, Any

# [System Path Setup]
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from src.extractor.adapters.http_client import AsyncHttpAdapter
from src.extractor.adapters.auth import KISAuthStrategy
from src.extractor.domain.exceptions import AuthError, NetworkError
from src.common.config import get_config
from src.common.log import LogManager

async def run_kis_integration_test():
    """KIS API 통합 연결 테스트 메인 함수."""
    
    logger = LogManager.get_logger("AdapterDemo")
    logger.info(">>> [Step 1] Initializing Configuration & Strategies")

    # 1. 설정 로드
    try:
        config = get_config("adapter_demo")
        policy = config.extraction_policy["test_kis_integration"]
        logger.info(f"Loaded Policy: {policy.description} (Target: {policy.path})")
    except KeyError:
        logger.error("Critical: 'test_kis_integration' policy not found in adapter_demo.yml")
        return

    # 2. 인증 전략 및 HTTP 클라이언트 준비
    auth_strategy = KISAuthStrategy(config)
    
    async with AsyncHttpAdapter(timeout=10) as client:
        # ----------------------------------------------------------------------
        # [Step 2] Authentication Verification
        # ----------------------------------------------------------------------
        logger.info(">>> [Step 2] Verifying Authentication (Token Issuance)")
        try:
            token = await auth_strategy.get_token(client)
            masked_token = token[:15] + "..." + token[-5:]
            logger.info(f"✅ Authentication Successful. Token: {masked_token}")
        except AuthError as e:
            logger.error(f"❌ Authentication Failed: {e}")
            logger.error("Stop verifying. Please check your .env file (AppKey/Secret).")
            return

        # ----------------------------------------------------------------------
        # [Step 3] Data Request Verification (Manual Construction)
        # ----------------------------------------------------------------------
        logger.info(">>> [Step 3] Verifying Data Request (Infrastructure Only)")
        
        # Extractor를 사용하지 않으므로, 여기서 수동으로 헤더를 조립합니다.
        # 이는 '인프라 계층'이 정상 동작함을 증명하기 위함입니다.
        url = f"{config.kis.base_url}{policy.path}"
        
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": token,
            "appkey": config.kis.app_key.get_secret_value(),
            "appsecret": config.kis.app_secret.get_secret_value(),
            "tr_id": policy.tr_id
        }
        
        # 정책(yml)에 정의된 파라미터 사용
        params = policy.params

        try:
            logger.info(f"Sending Request to: {url}")
            response = await client.get(url, headers=headers, params=params)

            # ------------------------------------------------------------------
            # [Step 4] Result Verification
            # ------------------------------------------------------------------
            if isinstance(response, dict):
                rt_cd = response.get("rt_cd")
                msg = response.get("msg1")
                
                if rt_cd == "0":
                    logger.info(f"✅ Connection Successful! (rt_cd: {rt_cd})")
                    # 실제 데이터 일부를 로그로 출력하여 육안 검증
                    output = response.get("output", {})
                    price = output.get("stck_prpr", "Unknown") # 현재가
                    name = "Samsung Electronics" # 005930
                    logger.info(f"   => {name} Current Price: {price} KRW")
                else:
                    logger.warning(f"⚠️ Connection OK, but Business Error: {msg} (Code: {rt_cd})")
            else:
                logger.warning(f"⚠️ Unexpected Response Type: {type(response)}")
                
        except NetworkError as e:
            logger.error(f"❌ Network Level Failure: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    # 1. Config Load
    try:
        get_config("adapter_demo")
    except Exception as e:
        print(f"[Critical] Config Load Failed: {e}")
        sys.exit(1)

    # 2. Logger Init
    LogManager()

    # 3. Execute
    try:
        asyncio.run(run_kis_integration_test())
    except KeyboardInterrupt:
        print("\nStopped by user.")