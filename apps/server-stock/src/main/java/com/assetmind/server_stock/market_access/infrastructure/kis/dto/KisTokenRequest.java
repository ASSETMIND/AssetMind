package com.assetmind.server_stock.market_access.infrastructure.kis.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

// 한국투자증권 접근토큰발급 API 요청 DTO
public record KisTokenRequest(
        @JsonProperty("grant_type") String grantType, // 권한 부여 Type
        @JsonProperty("appkey") String appKey, // 한국투자증권 홈페이지에서 발급 받은 앱키
        @JsonProperty("appsecret") String appSecret // 한국투자증권 홈페이지에서 발급받은 앱시크릿키
) {

    /**
     * new 키워드를 통해서 객체를 생성하는 것보다 의미는 메서드 명을 위해
     * 팩토리 메서드 패턴으로 생성자를 캡슐화 했음
     * @param appKey: 앱키
     * @param appSecret: 앱시크릿키
     * @return KisTokenRequest 객체
     */
    public static KisTokenRequest createKisTokenReq(String appKey, String appSecret) {
        return new KisTokenRequest("client_credentials", appKey, appSecret);
    }
}
