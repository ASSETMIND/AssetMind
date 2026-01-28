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
}