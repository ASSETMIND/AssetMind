package com.assetmind.server_stock.market_access.infrastructure.kis.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * 한국투자증권 실시간 (웹소켓) 접속키 발급 API 응답 DTO
 * @param approvalKey 웹소켓 이용 시 발급받은 웹소켓 접속키를 appkey와 appsecret 대신 헤더에 넣어 API 호출합니다.
 */
public record KisApprovalKeyResponse(
        @JsonProperty("approval_key") String approvalKey
) {

}
