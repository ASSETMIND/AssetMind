package com.assetmind.server_auth.user.application;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.BDDMockito.*;

import com.assetmind.server_auth.global.error.ErrorCode;
import com.assetmind.server_auth.user.application.dto.TokenSetDto;
import com.assetmind.server_auth.user.application.dto.UserLoginCommand;
import com.assetmind.server_auth.user.application.port.PasswordEncoder;
import com.assetmind.server_auth.user.application.port.RefreshTokenPort;
import com.assetmind.server_auth.user.application.port.UserRepository;
import com.assetmind.server_auth.user.application.provider.AuthTokenProvider;
import com.assetmind.server_auth.user.domain.User;
import com.assetmind.server_auth.user.domain.type.UserRole;
import com.assetmind.server_auth.user.exception.AuthException;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

/**
 * UserAuthService 단위 테스트
 * 로그인 로직 확인
 * 로그아웃 로직 확인
 * 토큰 재발급 로직 확인
 */
@ExtendWith(MockitoExtension.class)
class UserAuthServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private RefreshTokenPort refreshTokenPort;

    @Mock
    private AuthTokenProvider authTokenProvider;

    @Mock
    private PasswordEncoder passwordEncoder;

    @Mock
    private User user;

    @InjectMocks
    private UserAuthService authService;

    private final String EMAIL = "test@email.com";
    private final String PASSWORD = "!test123";
    private final UUID USER_ID = UUID.randomUUID();

    @Test
    @DisplayName("성공: 유효한 로그인 정보라면 토큰을 발급하고 Redis에 저장하고 TokenSet을 응답한다.")
    void givenLoginCommand_whenLogin_thenReturnTokenSet() {
        // given
        UserLoginCommand cmd = new UserLoginCommand(EMAIL, PASSWORD);
        TokenSetDto mockTokenSet = new TokenSetDto("access-token", "refresh-token", 10000L);

        given(userRepository.findByEmail(cmd.email())).willReturn(Optional.of(user)); // 유저 조회 성공

        // 비밀번호 일치
        given(user.getPasswordValue()).willReturn("encoded-password");
        given(passwordEncoder.matches(PASSWORD, "encoded-password")).willReturn(true);

        // User 정보 추출
        given(user.getId()).willReturn(USER_ID);
        given(user.getUserRole()).willReturn(UserRole.GUEST);

        // 토큰 생성 성공
        given(authTokenProvider.createTokenSet(USER_ID, UserRole.GUEST)).willReturn(mockTokenSet);

        // when
        TokenSetDto result = authService.login(cmd);

        // then
        assertThat(result).isEqualTo(mockTokenSet);

        // 검증: Redis에 저장 메서드가 호출되었는가? (expireTime / 1000 계산 확인)
        then(refreshTokenPort).should().save(eq(USER_ID), eq("refresh-token"), eq(10L));
    }

    @Test
    @DisplayName("실패: 존재하지 않는 이메일이라면 예외를 발생시킨다.")
    void givenNotFoundEmail_whenLogin_thenThrowException() {
        // given
        String notFoundEmail = "notfound@test.com";
        UserLoginCommand cmd = new UserLoginCommand(notFoundEmail, PASSWORD);
        given(userRepository.findByEmail(notFoundEmail)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> authService.login(cmd))
                .isInstanceOf(AuthException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.USER_NOT_FOUND);

        // 비밀번호 검증이나 토큰 발급 로직까지 가면 안 됨
        then(passwordEncoder).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("실패: 잘못된 비밀번호라면 예외를 발생시킨다.")
    void givenInvalidPassword_whenLogin_thenThrowException() {
        // given
        String invalidPassword = "invalid-password";
        UserLoginCommand command = new UserLoginCommand(EMAIL, invalidPassword);
        given(userRepository.findByEmail(EMAIL)).willReturn(Optional.of(user));

        given(user.getPasswordValue()).willReturn("encoded-password");
        given(passwordEncoder.matches(invalidPassword, "encoded-password")).willReturn(false);

        // when & then
        assertThatThrownBy(() -> authService.login(command))
                .isInstanceOf(AuthException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INCORRECT_PASSWORD);

        // 토큰 발급 로직까지 가면 안 됨
        then(authTokenProvider).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("성공: Redis 에서 로그아웃할 유저의 리프레쉬 토큰을 삭제한다.")
    void givenUserId_whenLogout_thenDeleteRefreshToken() {
        // given

        // when
        authService.logout(USER_ID);

        // then
        then(refreshTokenPort).should().delete(USER_ID);
    }

    @Test
    @DisplayName("성공: 유효한 리프레시 토큰으로 재발급 요청 시, 토큰을 갱신하고 Redis를 업데이트한다.")
    void givenValidRefreshToken_whenReissueRefreshToken_thenReturnNewTokenSet() {
        // given
        String requestRefreshToken = "valid-old-refresh-token";

        // 새로 발급될 토큰 정보
        String newAccessToken = "new-access-token";
        String newRefreshToken = "new-refresh-token";
        TokenSetDto newTokenSet = new TokenSetDto(newAccessToken, newRefreshToken, 10000L);

        // 토큰 자체 유효성 검증 (Provider)
        willDoNothing().given(authTokenProvider).validateToken(requestRefreshToken);

        // 토큰에서 사용자 ID 및 Role 추출
        given(authTokenProvider.getUserIdFromToken(requestRefreshToken)).willReturn(USER_ID);

        // 유저 정보 최신화
        given(userRepository.findById(USER_ID)).willReturn(Optional.of(user));

        // Redis에 저장된 토큰 조회 및 일치 확인
        given(refreshTokenPort.getRefreshToken(USER_ID)).willReturn(requestRefreshToken);

        given(user.getUserRole()).willReturn(UserRole.GUEST);

        // 새 토큰 생성
        given(authTokenProvider.createTokenSet(USER_ID, UserRole.GUEST)).willReturn(newTokenSet);

        // when
        TokenSetDto result = authService.reissueToken(requestRefreshToken);

        // then
        assertThat(result).isEqualTo(newTokenSet);

        // 검증: Redis에 새로운 리프레시 토큰이 저장되었는지 (RTR: Refresh Token Rotation)
        then(refreshTokenPort).should().save(eq(USER_ID), eq(newRefreshToken), eq(10L));
    }

    @Test
    @DisplayName("실패: 요청한 리프레시 토큰이 유효하지 않은 형식(혹은 만료)이라면 예외를 발생시킨다.")
    void givenInvalidRefreshTokenFormat_whenReissueRefreshToken_thenThrowException() {
        // given
        String invalidToken = "invalid-format-token";

        // Provider 검증 실패
        willThrow(new AuthException(ErrorCode.INVALID_TOKEN))
                .given(authTokenProvider).validateToken(invalidToken);

        // when & then
        assertThatThrownBy(() -> authService.reissueToken(invalidToken))
                .isInstanceOf(AuthException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_TOKEN);

        // Redis 조회나 저장 로직이 동작하지 않음을 검증
        then(refreshTokenPort).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("실패: Redis에 저장된 리프레시 토큰이 없다면(만료됨/로그아웃됨) 예외를 발생시킨다.")
    void givenRefreshTokenNotFoundInRedis_whenReissueRefreshToken_thenThrowException() {
        // given
        String requestRefreshToken = "valid-format-but-not-in-redis";

        willDoNothing().given(authTokenProvider).validateToken(requestRefreshToken);
        given(authTokenProvider.getUserIdFromToken(requestRefreshToken)).willReturn(USER_ID);

        // Redis 조회 결과 없음 (TTL 만료 등)
        given(refreshTokenPort.getRefreshToken(USER_ID)).willReturn(isNull());

        // when & then
        assertThatThrownBy(() -> authService.reissueToken(requestRefreshToken))
                .isInstanceOf(AuthException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_TOKEN);
    }

    @Test
    @DisplayName("실패: 요청한 토큰과 Redis에 저장된 토큰이 일치하지 않는다면 예외를 발생시킨다.")
    void givenTokenMismatch_whenReissueRefreshToken_thenThrowException() {
        // given
        String requestRefreshToken = "request-refresh-token";
        String storedRefreshToken = "latest-valid-refresh-token";

        willDoNothing().given(authTokenProvider).validateToken(requestRefreshToken);
        given(authTokenProvider.getUserIdFromToken(requestRefreshToken)).willReturn(USER_ID);

        // Redis에는 다른 토큰이 저장되어 있음 (이미 다른 기기에서 갱신했거나 공격 시도) requestRefreshToken != storedRefreshToken
        given(refreshTokenPort.getRefreshToken(USER_ID)).willReturn(storedRefreshToken);

        // when & then
        assertThatThrownBy(() -> authService.reissueToken(requestRefreshToken))
                .isInstanceOf(AuthException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_TOKEN); // 혹은 TOKEN_MISMATCH
    }
}