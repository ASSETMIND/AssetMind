package com.assetmind.server_stock.market_access.infrastructure.kis.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * 한국투자증권 접근토큰발급 API 응답 DTO
 * @param accessToken API 요청 시 필요한 Access Token
 * @param tokenType "Bearer"
 * @param expiresIn 유효기간(초)
 */
public record KisTokenResponse(
        @JsonProperty("access_token") String accessToken,
        @JsonProperty("token_type") String tokenType,
        @JsonProperty("expires_in") long expiresIn
) {

}
