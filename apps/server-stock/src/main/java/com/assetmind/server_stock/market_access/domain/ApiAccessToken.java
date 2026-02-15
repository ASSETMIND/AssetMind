package com.assetmind.server_stock.market_access.domain;

/**
 * 외부 API의 구체적인 구현에 종속되지 않는, 비즈니스 영역의 VO Token 객체
 * @param tokenValue 실제 토큰 값
 * @param expiresIn 토큰의 유효 시간
 */
public record ApiAccessToken(
        String tokenValue,
        long expiresIn
) {
    public static ApiAccessToken of(String tokenValue, long expiresIn) {
        return new ApiAccessToken(tokenValue, expiresIn);
    }
}
