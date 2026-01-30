package com.assetmind.server_auth.user.presentation;

import static org.mockito.BDDMockito.*;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.assetmind.server_auth.global.config.SecurityConfig;
import com.assetmind.server_auth.global.error.ErrorCode;
import com.assetmind.server_auth.global.util.CookieUtils;
import com.assetmind.server_auth.user.application.UserAuthUseCase;
import com.assetmind.server_auth.user.application.dto.TokenSetDto;
import com.assetmind.server_auth.user.application.dto.UserLoginCommand;
import com.assetmind.server_auth.user.exception.AuthException;
import com.assetmind.server_auth.user.presentation.dto.LoginRequest;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.Cookie;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseCookie;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

/**
 * UserAuthControllerTest 슬라이스 테스트
 * Request DTO의 @Valid 입력값 검증
 * GlobalExceptionHandler의 예외 처리 검증
 * 로그인 / 로그아웃 API 로직 검증
 */
@WebMvcTest(UserAuthController.class)
@AutoConfigureMockMvc
@Import(SecurityConfig.class)
class UserAuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockitoBean
    private UserAuthUseCase authUseCase;

    @MockitoBean
    private CookieUtils cookieUtils;

    @Test
    @DisplayName("성공: [POST] 유효한 로그인 정보로 로그인에 성공하면 accessToken은 body로, refreshToken은 cookie에 넣어서 응답한다.")
    void givenLoginRequest_whenLogin_thenRespondTokenSet200() throws Exception {
        // given
        LoginRequest request = new LoginRequest("test@email.com", "!Pass123");
        TokenSetDto tokenSet = new TokenSetDto("access-token", "refresh-token", 10000L); // 10초

        // Mocking: 서비스가 토큰셋 반환
        given(authUseCase.login(any(UserLoginCommand.class))).willReturn(tokenSet);

        // Mocking: 쿠키 유틸이 쿠키 생성
        ResponseCookie mockCookie = ResponseCookie.from("refresh_token", "refresh-token")
                .httpOnly(true)
                .path("/")
                .maxAge(10)
                .build();
        given(cookieUtils.createRefreshTokenCookie(any(), eq(10L))).willReturn(mockCookie);

        // when & then
        mockMvc.perform(post("/api/auth/login")
                        .with(csrf()) // POST 요청 필수
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").isEmpty())
                .andExpect(jsonPath("$.data.access_token").value("access-token"))
                // 헤더에 Set-Cookie가 존재하는지 확인
                .andExpect(header().exists("Set-Cookie"))
                .andExpect(header().string("Set-Cookie", org.hamcrest.Matchers.containsString("refresh_token=refresh-token")));
    }

    @Test
    @DisplayName("실패: [POST] 잘못된 형식의 이메일로 로그인을 시도하면 형식 오류 예외를 (400) 응답한다.")
    void givenInvalidEmail_whenLogin_thenRespond400() throws Exception {
        // given
        LoginRequest request = new LoginRequest("invalid-email", "!Pass123"); // 이메일 형식 X

        // when & then
        mockMvc.perform(post("/api/auth/login")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andDo(print())
                .andExpect(status().isBadRequest()) // 400 Bad Request
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("올바른 이메일 형식이 아닙니다."))
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("실패: [POST] 잘못된 형식의 비밀번호로 로그인을 시도하면 형식 오류 예외를 (400) 응답한다.")
    void givenInvalidPassword_whenLogin_thenRespond400() throws Exception {
        // given
        LoginRequest request = new LoginRequest("test@email.com", "123"); // 비밀번호 규칙 위반 (너무 짧음 등)

        // when & then
        mockMvc.perform(post("/api/auth/login")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andDo(print())
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("비밀번호는 8자 이상, 영문/숫자/특수문자를 포함해야 합니다."))
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("실패: [POST] 존재하지 않는 이메일로 로그인을 시도하면 예외를 (404) 응답한다.")
    void givenNotExistEmail_whenLogin_thenRespond404() throws Exception {
        // given
        LoginRequest request = new LoginRequest("notfound@email.com", "!Pass123");

        // Mocking: 서비스에서 예외 발생 시키기
        given(authUseCase.login(any(UserLoginCommand.class)))
                .willThrow(new AuthException(ErrorCode.USER_NOT_FOUND));

        // when & then
        mockMvc.perform(post("/api/auth/login")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andDo(print())
                .andExpect(status().isNotFound()) // 404 Not Found
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value(ErrorCode.USER_NOT_FOUND.getMessage()))
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("실패: [POST] 맞지 않는 비밀번호로 로그인을 시도하면 예외를 (401) 응답한다.")
    void givenIncorrectPassword_whenLogin_thenRespond401() throws Exception {
        // given
        LoginRequest request = new LoginRequest("test@email.com", "wrongPassword!123");

        // Mocking: 비밀번호 불일치 예외
        given(authUseCase.login(any(UserLoginCommand.class)))
                .willThrow(new AuthException(ErrorCode.INCORRECT_PASSWORD)); // ErrorCode의 상태값이 401인지 확인 필요

        // when & then
        mockMvc.perform(post("/api/auth/login")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andDo(print())
                // 만약 ErrorCode.INCORRECT_PASSWORD의 status가 401이라면:
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value(ErrorCode.INCORRECT_PASSWORD.getMessage()))
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("성공: [POST] 로그인된 유저가 유효한 userId로 로그아웃을 하면 refreshToken이 삭제되고, 빈 쿠키 값을 넣어서 응답한다.")
    void givenValidUserId_whenLogout_thenRespondEmptyCookie200() throws Exception {
        // given
        UUID userId = UUID.randomUUID();

        // 인증 객체 생성 (Filter 통과 가정)
        Authentication auth = new UsernamePasswordAuthenticationToken(userId, null, List.of(new SimpleGrantedAuthority("GUEST")));

        // Mocking: 쿠키 삭제용 쿠키 생성
        ResponseCookie deletionCookie = ResponseCookie.from("refresh_token", "")
                .maxAge(0) // 즉시 만료
                .build();
        given(cookieUtils.createDeletedCookie()).willReturn(deletionCookie);

        // when & then
        mockMvc.perform(post("/api/auth/logout")
                        .with(csrf())
                        .with(authentication(auth))) // 👈 인증된 상태 주입
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").value("로그아웃 성공"))
                .andExpect(jsonPath("$.data").isEmpty())
                .andExpect(header().string("Set-Cookie", org.hamcrest.Matchers.containsString("Max-Age=0")));

        // 서비스 로그아웃 호출 확인
        then(authUseCase).should().logout(eq(userId));
    }

    @Test
    @DisplayName("성공: [POST] 유효한 Refresh Token 쿠키로 재발급 요청 시, 새 토큰을 발급하고 쿠키를 갱신한다.")
    void givenValidRefreshTokenCookie_whenReissue_thenRespondNewTokenSet200() throws Exception {
        // given
        String oldRefreshToken = "old-refresh-token";
        String newAccessToken = "new-access-token";
        String newRefreshToken = "new-refresh-token";

        TokenSetDto newTokenSet = new TokenSetDto(newAccessToken, newRefreshToken, 10000L);

        // 1. Mocking: 서비스 로직
        given(authUseCase.reissueToken(eq(oldRefreshToken))).willReturn(newTokenSet);

        // 2. Mocking: 응답용 새 쿠키 생성
        ResponseCookie newCookie = ResponseCookie.from("refresh_token", newRefreshToken)
                .httpOnly(true)
                .path("/")
                .maxAge(10)
                .build();
        given(cookieUtils.createRefreshTokenCookie(eq(newRefreshToken), eq(10L))).willReturn(newCookie);

        // when & then
        mockMvc.perform(post("/api/auth/reissue")
                        .with(csrf())
                        .cookie(new Cookie("refresh_token", oldRefreshToken)))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").isEmpty())
                .andExpect(jsonPath("$.data.access_token").value(newAccessToken))
                .andExpect(header().exists("Set-Cookie"))
                .andExpect(header().string("Set-Cookie", org.hamcrest.Matchers.containsString("refresh_token=" + newRefreshToken)));
    }

    @Test
    @DisplayName("실패: [POST] 요청에 Refresh Token 쿠키가 없다면 401 Unauthorized 응답한다.")
    void givenNoRefreshTokenCookie_whenReissue_thenRespond401() throws Exception {
        // given
        // 쿠키를 넣지 않고 요청

        // when & then
        mockMvc.perform(post("/api/auth/reissue")
                        .with(csrf()))
                .andDo(print())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("필수 쿠키가 누락되었습니다."))
                .andExpect(jsonPath("$.data").isEmpty())
                .andExpect(status().isUnauthorized()); // @CookieValue(required=true)에 의해 401 발생
    }

    @Test
    @DisplayName("실패: [POST] 만료되거나 유효하지 않은 Refresh Token으로 요청 시 401 응답한다.")
    void givenInvalidRefreshToken_whenReissue_thenRespond401() throws Exception {
        // given
        String invalidToken = "invalid-token";

        // Mocking: 서비스에서 예외 발생
        given(authUseCase.reissueToken(eq(invalidToken)))
                .willThrow(new AuthException(ErrorCode.INVALID_TOKEN));

        // when & then
        mockMvc.perform(post("/api/auth/reissue")
                        .with(csrf())
                        .cookie(new jakarta.servlet.http.Cookie("refresh_token", invalidToken)))
                .andDo(print())
                .andExpect(status().isUnauthorized()) // 401
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value(ErrorCode.INVALID_TOKEN.getMessage()))
                .andExpect(jsonPath("$.data").isEmpty());
    }
}