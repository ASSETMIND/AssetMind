package com.assetmind.server_auth.global.util;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;

/**
 * HttpOnly, Secure, SameSite 보안이 적용된 쿠키를 생성하는 유틸리티 클래스
 * 쿠키 생성 로직을 관리
 */
@Component
public class CookieUtils {

    private static final String REFRESH_TOKEN_COOKIE_NAME = "refresh_token";

    @Value("${jwt.cookie.secure}")
    private boolean secure;

    /**
     * 리프레시 토큰을 담은 보안 쿠키를 생성
     * 로그인 성공 시 클라이언트에게 발급할 때 사용
     * @param refreshToken - 저장할 토큰 값
     * @return 설정이 완료된 ResponseCookie 객체
     */
    public ResponseCookie createRefreshTokenCookie(String refreshToken, long maxAge) {
        return ResponseCookie.from(REFRESH_TOKEN_COOKIE_NAME, refreshToken)
                .httpOnly(true)
                .secure(secure)
                .path("/")
                .maxAge(maxAge)
                .sameSite("Lax")
                .build();
    }

    /**
     * 로그아웃 시 브라우저의 쿠키를 삭제하기 위한 '만료된 쿠키'를 생성
     * (쿠키는 서버가 직접 삭제할 수 없으므로, 만료 시간(maxAge)을 0으로 덮어씌움)
     * @return Max-Age가 0인 삭제용 ResponseCookie 객체
     */
    public ResponseCookie createDeletedCookie() {
        return ResponseCookie.from(REFRESH_TOKEN_COOKIE_NAME, "")
                .httpOnly(true)
                .secure(secure)
                .path("/")
                .maxAge(0)
                .sameSite("Lax")
                .build();
    }
}
