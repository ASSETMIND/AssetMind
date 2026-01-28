package com.assetmind.server_auth.user.application.provider;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.BDDMockito.*;

import com.assetmind.server_auth.global.common.JwtProcessor;
import com.assetmind.server_auth.global.error.ErrorCode;
import com.assetmind.server_auth.user.application.dto.TokenSetDto;
import com.assetmind.server_auth.user.domain.type.UserRole;
import com.assetmind.server_auth.user.exception.AuthException;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.MalformedJwtException;
import io.jsonwebtoken.security.SignatureException;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import org.junit.jupiter.api.Test;

/**
 * AuthTokenProvider 단위 테스트
 * 모킹된 JwtProcessor를 가지고
 * 인증용 토큰 생성 검증
 * 토큰(UUID, UserRole) 추출 로직 검증
 */
@ExtendWith(MockitoExtension.class)
class AuthTokenProviderTest {

    @Mock
    private JwtProcessor jwtProcessor;

    @Mock
    private Claims claims;

    @InjectMocks
    private AuthTokenProvider authTokenProvider;

    private final UUID USER_ID = UUID.randomUUID();
    private final UserRole ROLE = UserRole.GUEST;

    @Test
    @DisplayName("성공: Access/Refresh 토큰이 정상 생성된다.")
    void givenValidInfo_whenCreateTokenSet_thenReturnTokenSet() {
        // given
        String mockAccessToken = "access-token";
        String mockRefreshToken = "refresh-token";

        given(jwtProcessor.generate(anyString(), anyMap(), anyLong())).willReturn(mockAccessToken, mockRefreshToken);

        // when
        TokenSetDto result = authTokenProvider.createTokenSet(USER_ID, ROLE);

        // then
        assertThat(result.accessToken()).isEqualTo(mockAccessToken);
        assertThat(result.refreshToken()).isEqualTo(mockRefreshToken);

        verify(jwtProcessor, times(2)).generate(eq(USER_ID.toString()), anyMap(), anyLong());
    }

    @Test
    @DisplayName("성공: 유효한 토큰이라면 UUID를 반환한다.")
    void givenValidToken_whenGetUserIdFromToken_thenReturnUUID() {
        // given
        String validToken = "valid-token";
        given(jwtProcessor.parse(validToken)).willReturn(claims);

        given(claims.get("role")).willReturn(ROLE.toString());
        given(claims.getSubject()).willReturn(USER_ID.toString());

        // when
        UUID result = authTokenProvider.getUserIdFromToken(validToken);

        // then
        assertThat(result).isEqualTo(USER_ID);
    }

    @Test
    @DisplayName("성공: 유효한 토큰이라면 UserRole을 반환한다.")
    void givenValidToken_whenGetRoleFromToken_thenReturnUserRole() {
        // given
        String token = "valid-token";
        given(jwtProcessor.parse(token)).willReturn(claims);

        given(claims.get("role")).willReturn(ROLE.toString());

        // 실제 값 추출용 (UserRole.valueOf("USER"))
        given(claims.get("role", String.class)).willReturn("GUEST");

        // when
        UserRole resultRole = authTokenProvider.getRoleFromToken(token);

        // then
        assertThat(resultRole).isEqualTo(ROLE);
    }

    @Test
    @DisplayName("성공: 유효한 토큰이면 검증에 성공한다.")
    void givenValidToken_whenValidateToken_thenReturnVoid() {
        // given
        String token = "valid-token";
        given(jwtProcessor.parse(token)).willReturn(claims);
        given(claims.get("role")).willReturn(ROLE); // Role 존재

        // when & then (예외가 발생하지 않음을 검증)
        assertThatCode(() -> authTokenProvider.validateToken(token))
                .doesNotThrowAnyException();
    }

    @Test
    @DisplayName("실패: Auth 전용 토큰이 아니라면(Role 없음) 예외를 던진다.")
    void givenSignUpToken_whenValidateToken_thenThrowException() {
        // given
        String signUpToken = "signup-token"; // 가입용 토큰(Role 없음)
        given(jwtProcessor.parse(signUpToken)).willReturn(claims);

        // *핵심*: Role Claim이 Null임
        given(claims.get("role")).willReturn(null);

        // when & then
        assertThatThrownBy(() -> authTokenProvider.validateToken(signUpToken))
                .isInstanceOf(AuthException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_TOKEN_TYPE);
    }

    @Test
    @DisplayName("실패: 형식이 잘못된 토큰이라면 예외를 던진다.")
    void givenMalformedToken_whenValidateToken_thenThrowException() {
        // given
        String malformedToken = "malformed-token";
        given(jwtProcessor.parse(malformedToken))
                .willThrow(new MalformedJwtException("malformed"));

        // when & then
        assertThatThrownBy(() -> authTokenProvider.validateToken(malformedToken))
                .isInstanceOf(AuthException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_TOKEN_SIGNATURE);
    }

    @Test
    @DisplayName("실패: 만료된 토큰이라면 예외를 던진다.")
    void givenExpiredToken_whenValidateToken_thenThrowException() {
        // given
        String expiredToken = "expired-token";
        // 라이브러리 예외(ExpiredJwtException) 발생 시뮬레이션
        given(jwtProcessor.parse(expiredToken))
                .willThrow(new ExpiredJwtException(null, null, "expired"));

        // when & then -> AuthException(EXPIRED_TOKEN)으로 변환되어야 함
        assertThatThrownBy(() -> authTokenProvider.validateToken(expiredToken))
                .isInstanceOf(AuthException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.EXPIRED_TOKEN);
    }
}