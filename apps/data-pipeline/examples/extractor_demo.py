"""
Adapter Integration Test Suite (Multi-Provider)

이 스크립트는 Infrastructure Layer(HTTP Adapter, Auth Strategy)가 
4종의 타겟 시스템(KIS, FRED, ECOS, UPBIT)과 정상적으로 통신할 수 있는지 검증합니다.

Domain Layer(Extractor)를 거치지 않고 직접 헤더와 URL을 조립하여 요청함으로써,
비즈니스 로직의 간섭 없이 순수 네트워크 및 인증 상태를 진단합니다.

주요 검증 항목:
1. KIS: OAuth2 Access Token 발급 및 TR 호출.
2. FRED: Query Parameter 기반 API Key 주입 및 JSON 응답 변환.
3. ECOS: Path Variable 기반 URL 조립 및 호출.
4. UPBIT: JWT Token 생성 및 Bearer 인증 헤더 주입.

Usage:
    python examples/extractor_demo.py
"""

import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

# [System Path Setup]
# 프로젝트 루트 경로를 시스템 경로에 추가하여 모듈 임포트 지원
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from src.extractor.adapters.http_client import AsyncHttpAdapter
from src.extractor.adapters.auth import KISAuthStrategy, UPBITAuthStrategy
from src.extractor.domain.exceptions import AuthError, NetworkError
from src.common.config import get_config, AppConfig
from src.common.log import LogManager

# 로거 설정 (전역)
logger = None

async def verify_kis(client: AsyncHttpAdapter, config: AppConfig):
    """[KIS] 한국투자증권 API 연결성 검증."""
    logger.info("=" * 60)
    logger.info(">>> [Target 1] KIS (Korea Investment & Securities)")
    
    try:
        policy = config.extraction_policy.get("test_kis_connectivity")
        if not policy:
            logger.warning("Skipping KIS: Policy not found.")
            return

        # 1. Auth Strategy를 통한 토큰 발급
        auth_strategy = KISAuthStrategy(config)
        token = await auth_strategy.get_token(client)
        logger.info(f"✅ Auth Token Issued: {token[:10]}...{token[-5:]}")

        # 2. 요청 조립 (Manual Construction)
        url = f"{config.kis.base_url}{policy.path}"
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": token,
            "appkey": config.kis.app_key.get_secret_value(),
            "appsecret": config.kis.app_secret.get_secret_value(),
            "tr_id": policy.tr_id
        }

        # 3. 실행 및 검증
        response = await client.get(url, headers=headers, params=policy.params)
        
        if response.get("rt_cd") == "0":
            output = response.get("output", {})
            price = output.get("stck_prpr", "N/A")
            logger.info(f"✅ Connection Success | Samsung Elec Price: {price} KRW")
        else:
            logger.error(f"❌ Business Error | Code: {response.get('rt_cd')} | Msg: {response.get('msg1')}")

    except Exception as e:
        logger.error(f"❌ KIS Verification Failed: {e}")


async def verify_fred(client: AsyncHttpAdapter, config: AppConfig):
    """[FRED] 미 연준 경제 데이터 API 연결성 검증."""
    logger.info("-" * 60)
    logger.info(">>> [Target 2] FRED (Federal Reserve Economic Data)")

    try:
        policy = config.extraction_policy.get("test_fred_connectivity")
        if not policy:
            logger.warning("Skipping FRED: Policy not found.")
            return

        # 1. 요청 조립 (Query Param Auth)
        url = f"{config.fred.base_url}{policy.path}"
        
        # FRED는 API Key를 Query String으로 전달 + JSON 강제
        params = policy.params.copy()
        params["api_key"] = config.fred.api_key.get_secret_value()
        params["file_type"] = "json"

        # 2. 실행 및 검증
        response = await client.get(url, params=params)
        
        # FRED는 'seriess'라는 키 안에 결과가 있음
        if "seriess" in response:
            series_info = response["seriess"][0]
            title = series_info.get("title", "Unknown")
            logger.info(f"✅ Connection Success | Title: {title}")
        elif "error_message" in response:
             logger.error(f"❌ Business Error | Msg: {response.get('error_message')}")
        else:
            logger.warning(f"⚠️ Unexpected Response Structure: {response.keys()}")

    except Exception as e:
        logger.error(f"❌ FRED Verification Failed: {e}")


async def verify_ecos(client: AsyncHttpAdapter, config: AppConfig):
    """[ECOS] 한국은행 경제통계 API 연결성 검증."""
    logger.info("-" * 60)
    logger.info(">>> [Target 3] ECOS (Bank of Korea)")

    try:
        policy = config.extraction_policy.get("test_ecos_connectivity")
        if not policy:
            logger.warning("Skipping ECOS: Policy not found.")
            return

        # 1. 요청 조립 (Path Variable Manual Construction)
        # ECOS Extractor의 로직을 여기서 수동으로 재현하여 URL이 올바르게 호출되는지 확인
        key = config.ecos.api_key.get_secret_value()
        base = config.ecos.base_url
        path = policy.path.strip("/") # StatisticSearch
        
        p = policy.params
        # URL 패턴: /Service/Key/json/kr/1/10/StatCode/Cycle/Start/End/ItemCode
        url = (
            f"{base}/{path}/{key}/json/kr/1/10/"
            f"{p['stat_code']}/{p['cycle']}/{p['start_date']}/{p['end_date']}/{p['item_code1']}"
        )

        logger.debug(f"Generated ECOS URL: {url}")

        # 2. 실행 및 검증
        response = await client.get(url)
        
        # ECOS 응답 구조 확인
        if path in response and "row" in response[path]:
            rows = response[path]["row"]
            if rows:
                latest_data = rows[-1]
                logger.info(f"✅ Connection Success | Date: {latest_data['TIME']} | Rate: {latest_data['DATA_VALUE']}%")
            else:
                logger.warning("✅ Connection Success but no data rows found.")
        elif "RESULT" in response:
             logger.error(f"❌ Business Error | Code: {response['RESULT']['CODE']} | Msg: {response['RESULT']['MESSAGE']}")
        else:
             logger.error(f"❌ Invalid Response Structure")

    except Exception as e:
        logger.error(f"❌ ECOS Verification Failed: {e}")


async def verify_upbit(client: AsyncHttpAdapter, config: AppConfig):
    """[UPBIT] 업비트 암호화폐 거래소 API 연결성 검증."""
    logger.info("-" * 60)
    logger.info(">>> [Target 4] UPBIT (Crypto Exchange)")

    try:
        policy = config.extraction_policy.get("test_upbit_connectivity")
        if not policy:
            logger.warning("Skipping UPBIT: Policy not found.")
            return

        # 1. Auth Strategy (JWT 생성)
        # UPBITAuthStrategy는 내부적으로 PyJWT를 사용하여 토큰을 생성함
        auth_strategy = UPBITAuthStrategy(config)
        
        # UPBIT는 GET 요청 시 Query Param을 포함하여 Hash를 생성해야 함 (복잡한 인증)
        # Strategy 내부 로직 검증을 위해 Strategy를 사용하여 토큰을 얻습니다.
        # 주의: get_token 메서드가 payload를 받을 수 있도록 설계되어 있어야 정확하지만,
        # 여기서는 Simple Auth(No param hashing) 혹은 Strategy 구현에 따라 동작을 확인합니다.
        
        # 데모를 위해 'Authorization' 헤더 없이 호출 가능한 Public API인지 확인하거나,
        # 인증이 필요한 경우 Strategy를 사용합니다. (여기선 인증 헤더 주입 시도)
        token = await auth_strategy.get_token(client)
        
        headers = {
            "accept": "application/json",
            "authorization": token
        }
        
        url = f"{config.upbit.base_url}{policy.path}"

        # 2. 실행 및 검증
        response = await client.get(url, headers=headers, params=policy.params)
        
        if isinstance(response, list) and len(response) > 0:
            data = response[0]
            market = data.get("market")
            trade_price = data.get("trade_price")
            logger.info(f"✅ Connection Success | Market: {market} | Price: {trade_price:,} KRW")
        elif isinstance(response, dict) and "error" in response:
             err = response["error"]
             logger.error(f"❌ Business Error | Name: {err.get('name')} | Msg: {err.get('message')}")
        else:
            logger.warning(f"⚠️ Unexpected Response Type: {type(response)}")

    except Exception as e:
        logger.error(f"❌ UPBIT Verification Failed: {e}")


async def main():
    """통합 테스트 메인 엔트리포인트."""
    global logger
    
    # 1. Config & Logger 초기화
    try:
        config = get_config("extractor_demo")
        LogManager()
        logger = LogManager.get_logger("ExtractorDemo")
        logger.info(">>> [Start] Extractor Integration Tests initialized.")
    except Exception as e:
        print(f"[Critical] Configuration Load Failed: {e}")
        return

    # 2. HTTP Client 생성 (Context Manager)
    async with AsyncHttpAdapter(timeout=10.0) as client:
        # 3. 순차적 검증 수행 (가독성을 위해 순차 실행)
        # 병렬 실행을 원하면 asyncio.gather() 사용 가능
        
        await verify_kis(client, config)
        await verify_fred(client, config)
        await verify_ecos(client, config)
        await verify_upbit(client, config)

    logger.info("=" * 60)
    logger.info(">>> [End] All Adapter Tests Completed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Test stopped by user.")