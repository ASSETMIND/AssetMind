package com.assetmind.server_stock.market_access.infrastructure.kis.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * 한국투자증권 실시간 (웹소켓) 접속키 발급 API 요청 DTO
 * @param grantType 기본 값: "client_credentials"
 * @param appKey 한국투자증권 홈페이지에서 발급받은 appkey
 * @param secretKey 한국투자증권 홈페이지에서 발급받은 appsecret
 */
public record KisApprovalKeyRequest(
        @JsonProperty("grant_type") String grantType,
        @JsonProperty("appKey") String appKey,
        @JsonProperty("secretKey") String secretKey
) {
    public static KisApprovalKeyRequest of(String appKey, String secretKey) {
        return new KisApprovalKeyRequest("client_credentials", appKey, secretKey);
    }
}
