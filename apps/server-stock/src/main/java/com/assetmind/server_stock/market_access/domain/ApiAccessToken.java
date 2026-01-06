package com.assetmind.server_stock.market_access.domain;

// 외부 API의 구체적인 구현에 종속되지 않는, 비즈니스 영역의 VO 객체
public record ApiAccessToken(
        String tokenValue,
        long expiresIn
) {
    public static ApiAccessToken createApiAccessToken(String tokenValue, long expiresIn) {
        return new ApiAccessToken(tokenValue, expiresIn);
    }
}
