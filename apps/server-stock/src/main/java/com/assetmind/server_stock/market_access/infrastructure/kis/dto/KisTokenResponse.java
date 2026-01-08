package com.assetmind.server_stock.market_access.infrastructure.kis.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

// 한국투자증권 접근토큰발급 API 응답 DTO
public record KisTokenResponse(
        @JsonProperty("access_token") String accessToken, // API 요청 시 필요한 Access Token
        @JsonProperty("token_type") String tokenType, // 접근 토큰 유형: "Bearer"
        @JsonProperty("expires_in") long expiresIn // 유효기간(초)
) {

}
