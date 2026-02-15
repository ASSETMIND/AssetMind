package com.assetmind.server_auth.global.util;

import static org.assertj.core.api.Assertions.*;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseCookie;
import org.springframework.test.util.ReflectionTestUtils;

/**
 * CookieUtils 단위 테스트
 * 토큰 쿠키 생성 시 보안 설정이 잘 되는지 검증
 * 토큰 쿠기 삭제 시 maxAge = 0이 잘 설정 되는지 검증
 */
class CookieUtilsTest {

    private CookieUtils cookieUtils;

    private static final long MAX_AGE = 604800;

    @BeforeEach
    void setUp() {
        cookieUtils = new CookieUtils();

        // @Value 필드에 테스트용 값 주입
        ReflectionTestUtils.setField(cookieUtils, "secure", true);
    }

    @Test
    @DisplayName("성공: 운영 환경(Https)에서 리프레시 토큰 쿠키 생성 시 모든 보안 설정이 적용된다.")
    void givenRefreshTokenInProd_whenCreateRefreshTokenCookie_thenReturnSecureResponseCookie() {
        // given
        String token = "test-refresh-token";

        // when
        ResponseCookie cookie = cookieUtils.createRefreshTokenCookie(token, MAX_AGE);

        // then
        assertThat(cookie.getValue()).isEqualTo(token);
        assertThat(cookie.isHttpOnly()).isTrue();  // 필수
        assertThat(cookie.isSecure()).isTrue();    // 필수 (운영환경)
        assertThat(cookie.getPath()).isEqualTo("/");
        assertThat(cookie.getMaxAge().getSeconds()).isEqualTo(MAX_AGE);
        assertThat(cookie.getSameSite()).isEqualTo("Lax");
    }

    @Test
    @DisplayName("성공: 로컬 환경(Http)에서 리프레시 토큰 쿠키 생성 시 Secure = false로 보안 설정이 적용된다.")
    void givenRefreshTokenInLocal_whenCreateRefreshTokenCookie_thenReturnNotSecureResponseCookie() {
        // given
        String token = "test-refresh-token";
        ReflectionTestUtils.setField(cookieUtils, "secure", false);

        // when
        ResponseCookie cookie = cookieUtils.createRefreshTokenCookie(token, MAX_AGE);

        // then
        assertThat(cookie.getValue()).isEqualTo(token);
        assertThat(cookie.isHttpOnly()).isTrue();  // 필수
        assertThat(cookie.isSecure()).isFalse();    // 필수 (운영환경)
        assertThat(cookie.getPath()).isEqualTo("/");
        assertThat(cookie.getMaxAge().getSeconds()).isEqualTo(MAX_AGE);
        assertThat(cookie.getSameSite()).isEqualTo("Lax");
    }

    @Test
    @DisplayName("성공: 삭제용 쿠키 생성 시, maxAge가 0이고 값이 빈 상태이다.")
    void whenCreateDeleteCookie_thenReturnEmptyResponseCookie() {
        // when
        ResponseCookie cookie = cookieUtils.createDeletedCookie();

        // then
        assertThat(cookie.getValue()).isEmpty(); // 값 비움
        assertThat(cookie.getMaxAge().getSeconds()).isZero(); // 즉시 만료
        assertThat(cookie.isHttpOnly()).isTrue();
        assertThat(cookie.getPath()).isEqualTo("/");
    }
}