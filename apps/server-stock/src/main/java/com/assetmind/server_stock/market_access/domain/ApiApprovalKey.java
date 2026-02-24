package com.assetmind.server_stock.market_access.domain;

/**
 * 외부 API의 구체적인 구현에 종속되지 않는, 비즈니스 영역의 VO Approval Key 객체
 * 실시간 API를 이용하기 전에 WebSocket 접속키로 사용
 */
public record ApiApprovalKey(String value) {

    public static ApiApprovalKey from(String rawKey) {
        return new ApiApprovalKey(rawKey);
    }
}
