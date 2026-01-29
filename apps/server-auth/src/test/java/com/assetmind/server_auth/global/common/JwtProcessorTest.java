package com.assetmind.server_auth.global.common;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_auth.global.config.JwtProperties;
import com.assetmind.server_auth.global.util.JwtProcessor;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.security.SignatureException;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * JwtProcessor 단위 테스트
 * 토큰 생성 및 파싱 로직 검증
 * 토큰 검증시 예외 검증
 */
class JwtProcessorTest {

    private JwtProcessor jwtProcessor;

    @BeforeEach
    void setUp() {
        String testSecret = "sh2yA+V0RXqGXgOMAE+uieIMEOrDXHJwlb3Pt5X8qlQ=";
        JwtProperties properties = new JwtProperties(testSecret);

        jwtProcessor = new JwtProcessor(properties);
    }

    @Test
    @DisplayName("성공: 토큰 생성 후 파싱을 했을 때, 넣은 데이터가 그대로 반환되어야 한다.")
    void givenTokenMetaData_whenGenerateAndParse_thenReturnCorrectMetaData() {
        // given
        String email = "subject@test.com";
        Map<String, Object> claims = Map.of("role", "USER", "type", "test", "int", 1);
        long expireMs = 60000;

        // when
        String token = jwtProcessor.generate(email, claims, expireMs);
        Claims parsingResult = jwtProcessor.parse(token);

        // then
        assertThat(parsingResult.getSubject()).isEqualTo(email);
        assertThat(parsingResult.get("role")).isEqualTo("USER");
        assertThat(parsingResult.get("int")).isEqualTo(1);
    }

    @Test
    @DisplayName("실패: 토큰 파싱하면서 검증 시, 만료된 토큰인 경우 ExpiredJwtException 예외가 발생해야한다.")
    void givenExpiredToken_whenParse_thenThrowException() throws InterruptedException {
        // given
        // 유효기간을 아주 짧게 설정
        String token = jwtProcessor.generate("test", Map.of(), 10);

        Thread.sleep(20);

        // when & then
        assertThatThrownBy(() -> jwtProcessor.parse(token))
                .isInstanceOf(ExpiredJwtException.class);
    }

    @Test
    @DisplayName("실패: 토큰 파싱하면서 검증 시, 서명이 다른 토큰인 경우 SignatureException 예외가 발생해야한다.")
    void givenFakeToken_whenParse_thenThrowException() {
        // given
        String correctToken = jwtProcessor.generate("test", Map.of(), 60000);

        String fakeToken = correctToken + "FAKE";

        // when & then
        assertThatThrownBy(() -> jwtProcessor.parse(fakeToken))
                .isInstanceOf(SignatureException.class);
    }
}