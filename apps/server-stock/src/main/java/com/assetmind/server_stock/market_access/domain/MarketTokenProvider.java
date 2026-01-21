package com.assetmind.server_stock.market_access.domain;

/**
 * 외부 시스템(KIS API 등)과 통신하여 인증 토큰을 발급받는 역할을 정의한 인터페이스
 * 해당 인터페이스는 기술적인 구현을 알지 못하며,
 * 오직 도메인 영역에 필요한 토큰 객체를 반환하는 '행위'만을 정의
 * 따라서 외부 시스템과 관련된 영역인 Infrastructure Layer 에서 해당 인터페이스를 구현
 * 이를 통해 도메인 로직은 외부 API의 변경에 영향을 받지 않음 (DIP 적용)
 *
 * 요약:
 * 주식 거래 시트템 접근 권한 토큰을 획득하는 명세서(계약서?)
 * 구현체는 외부 시스템과 관련된 영역인 Infrastructure Layer에 위치
 */

public interface MarketTokenProvider {

    /**
     * 유효한 접근 토큰을 발급받아 반환한다.
     * @return 도메인 전용 AccessToken VO
     */
    ApiAccessToken fetchToken();
}
