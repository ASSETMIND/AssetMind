package com.assetmind.server_auth.user.application.provider;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.BDDMockito.*;

import com.assetmind.server_auth.global.common.JwtProcessor;
import com.assetmind.server_auth.user.exception.InvalidSignUpTokenException;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

/**
 * SignUpTokenProvider 단위 테스트
 * 모킹된 JwtProcessor를 가지고
 * 회원가입용 토큰 생성 검증
 * 토큰 검증 및 이메일 추출 로직 검증
 */
@ExtendWith(MockitoExtension.class)
class SignUpTokenProviderTest {

    @Mock
    private JwtProcessor jwtProcessor;

    @InjectMocks
    private SignUpTokenProvider signUpTokenProvider;

    private String email = "test@test.com";
    private String validToken = "valid-token";

    @Test
    @DisplayName("성공: 이메일로 토큰을 생성 요청을 하면 해당 이메일과 SIGN_UP 타입으로 토큰을 생성한다.")
    void givenEmail_whenCreateToken_thenReturnCorrectSignUpToken() {
        // given
        given(jwtProcessor.generate(anyString(), anyMap(), anyLong())).willReturn(validToken);

        // when
        String result = signUpTokenProvider.createToken(email);

        // then
        assertThat(result).isEqualTo(validToken);
        verify(jwtProcessor).generate(
                eq(email),
                eq(Map.of("type", "SIGN_UP")),
                eq(30 * 60 * 1000L)
        );
    }

    @Test
    @DisplayName("성공: 토큰 검증 시 SIGN_UP 타입이 맞으면 해당 토큰의 subject인 이메일을 반환한다.")
    void givenValidToken_whenGetEmailFromToken_thenReturnValidEmail() {
        // given
        // JwtProcessor가 파싱해서 돌려줄 Claims mock 객체 생성
        Claims claims = Jwts.claims()
                .subject(email)
                .add("type", "SIGN_UP")
                .build();

        given(jwtProcessor.parse(validToken)).willReturn(claims);

        // when
        String result = signUpTokenProvider.getEmailFromToken(validToken);

        // then
        assertThat(result).isEqualTo(email);
    }

    @Test
    @DisplayName("실패: 토큰 검증 시 SIGN_UP 타입이 아니면 예외를 던진다.")
    void givenNotSignUpTypeToken_whenGetEmailFromToken_thenThrowException() {
        // given
        Claims claims = Jwts.claims()
                .subject(email)
                .add("type", "ACCESS")
                .build();

        given(jwtProcessor.parse(validToken)).willReturn(claims);

        // when & then
        assertThatThrownBy(() -> signUpTokenProvider.getEmailFromToken(validToken))
                .isInstanceOf(InvalidSignUpTokenException.class)
                .hasMessageContaining("유효하지 않거나 용도가 잘못된 회원가입 토큰");
    }

    @Test
    @DisplayName("실패: 토큰 검증 시 타입 Claims이 없으면 예외를 던진다.")
    void givenNullClaimsToken_whenGetEmailFromToken_thenThrowException() {
        // given
        Claims claims = Jwts.claims()
                .subject(email)
                .build();

        given(jwtProcessor.parse(validToken)).willReturn(claims);

        // when & then
        assertThatThrownBy(() -> signUpTokenProvider.getEmailFromToken(validToken))
                .isInstanceOf(InvalidSignUpTokenException.class)
                .hasMessageContaining("유효하지 않거나 용도가 잘못된 회원가입 토큰");
    }
}