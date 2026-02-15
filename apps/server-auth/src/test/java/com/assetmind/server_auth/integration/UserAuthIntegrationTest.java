package com.assetmind.server_auth.integration;

import com.assetmind.server_auth.global.error.ErrorCode;
import com.assetmind.server_auth.support.IntegrationTestSupport;
import com.assetmind.server_auth.user.application.dto.TokenSetDto;
import com.assetmind.server_auth.user.application.port.RefreshTokenPort;
import com.assetmind.server_auth.user.application.provider.AuthTokenProvider;
import com.assetmind.server_auth.user.domain.type.UserRole;
import com.assetmind.server_auth.user.infrastructure.persistence.jpa.UserEntity;
import com.assetmind.server_auth.user.infrastructure.persistence.jpa.UserJpaRepository;
import com.assetmind.server_auth.user.presentation.dto.LoginRequest;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.restdocs.AutoConfigureRestDocs;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.restdocs.payload.JsonFieldType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.restdocs.cookies.CookieDocumentation.*;
import static org.springframework.restdocs.headers.HeaderDocumentation.headerWithName;
import static org.springframework.restdocs.headers.HeaderDocumentation.requestHeaders;
import static org.springframework.restdocs.mockmvc.MockMvcRestDocumentation.document;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.*;
import static org.springframework.restdocs.payload.PayloadDocumentation.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@Transactional
@AutoConfigureRestDocs // REST Docs 활성화
class UserAuthIntegrationTest extends IntegrationTestSupport {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper objectMapper;
    @Autowired UserJpaRepository userRepository;
    @Autowired StringRedisTemplate redisTemplate;
    @Autowired PasswordEncoder passwordEncoder;
    @Autowired AuthTokenProvider authTokenProvider;
    @Autowired RefreshTokenPort refreshTokenPort;

    private final String EMAIL = "user@auth.com";
    private final String PASSWORD = "Password123!";
    private UserEntity savedUser;

    @BeforeEach
    void setUp() {
        // 테스트 전 Redis 데이터 초기화
        redisTemplate.getConnectionFactory().getConnection().flushAll();

        // 테스트용 유저 DB 저장
        savedUser = userRepository.save(new UserEntity(
                UUID.randomUUID(), EMAIL, "testUser",
                passwordEncoder.encode(PASSWORD),
                null, null, UserRole.USER
        ));
    }

    // =================================================================
    // 1. 로그인 (Login)
    // =================================================================

    @Test
    @DisplayName("로그인 성공: 유효한 계정 정보로 로그인 시 토큰이 발급된다.")
    void given_ValidLoginRequest_when_Login_then_Success() throws Exception {
        // given
        LoginRequest request = new LoginRequest(EMAIL, PASSWORD);

        // when
        mockMvc.perform(post("/api/auth/login")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").isEmpty())
                .andExpect(jsonPath("$.data.access_token").exists())
                .andExpect(cookie().exists("refresh_token"))
                .andExpect(cookie().httpOnly("refresh_token", true))
                // --- REST Docs ---
                .andDo(document("auth-login",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        requestFields(
                                fieldWithPath("email").type(JsonFieldType.STRING).description("사용자 이메일"),
                                fieldWithPath("password").type(JsonFieldType.STRING).description("사용자 비밀번호")
                        ),
                        responseCookies(
                                cookieWithName("refresh_token").description("Refresh Token (HttpOnly, Secure)")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("성공 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL).description("응답 메시지 (성공 시 null)").optional(),
                                fieldWithPath("data.access_token").type(JsonFieldType.STRING).description("Access Token (JWT)")
                        )
                ));

        // then
        String savedRefreshToken = refreshTokenPort.getRefreshToken(savedUser.getId());
        assertThat(savedRefreshToken).isNotNull();
    }

    @Test
    @DisplayName("로그인 실패: 비밀번호가 일치하지 않으면 401 예외를 반환한다.")
    void given_WrongPassword_when_Login_then_Unauthorized() throws Exception {
        // given
        LoginRequest request = new LoginRequest(EMAIL, "WrongPw123!");

        // when & then
        mockMvc.perform(post("/api/auth/login")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value(ErrorCode.INCORRECT_PASSWORD.getMessage()));
    }

    @Test
    @DisplayName("로그인 실패: 존재하지 않는 이메일이면 404 예외를 반환한다.")
    void given_NonExistentEmail_when_Login_then_NotFound() throws Exception {
        // given
        LoginRequest request = new LoginRequest("unknown@auth.com", PASSWORD);

        // when & then
        mockMvc.perform(post("/api/auth/login")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value(ErrorCode.USER_NOT_FOUND.getMessage()));
    }

    // =================================================================
    // 2. 로그아웃 (Logout)
    // =================================================================

    @Test
    @DisplayName("로그아웃 성공: 로그아웃 시 Redis에서 토큰이 삭제되고, 쿠키 만료 응답을 받는다.")
    void given_LoggedInUser_when_Logout_then_TokenDeleted() throws Exception {
        // given
        String refreshToken = "dummy-refresh-token";
        refreshTokenPort.save(savedUser.getId(), refreshToken, 10000L);

        TokenSetDto tokenSet = authTokenProvider.createTokenSet(savedUser.getId(), UserRole.USER);

        // when
        mockMvc.perform(post("/api/auth/logout")
                        .header("Authorization", "Bearer " + tokenSet.accessToken())
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").value("로그아웃 성공"))
                .andExpect(jsonPath("$.data").isEmpty())
                .andExpect(cookie().maxAge("refresh_token", 0))
                // --- REST Docs ---
                .andDo(document("auth-logout",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        requestHeaders(
                                headerWithName("Authorization").description("Bearer Access Token")
                        ),
                        responseCookies(
                                cookieWithName("refresh_token").description("만료된 Refresh Token (Max-Age=0)")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("성공 여부"),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("응답 메시지"),
                                fieldWithPath("data").type(JsonFieldType.NULL).description("데이터 (없음)").optional()
                        )
                ));

        // then
        String deletedToken = refreshTokenPort.getRefreshToken(savedUser.getId());
        assertThat(deletedToken).isNull();
    }

    @Test
    @DisplayName("로그아웃 실패: Access Token 없이 로그아웃 요청 시 401(EntryPoint) 응답을 받는다.")
    void given_NoAccessToken_when_Logout_then_Unauthorized() throws Exception {
        // given (헤더 없음)

        // when & then
        mockMvc.perform(post("/api/auth/logout")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false));
    }

    // =================================================================
    // 3. 토큰 재발급 (Reissue - RTR)
    // =================================================================

    @Test
    @DisplayName("재발급 성공: 유효한 Refresh Token으로 요청 시, 토큰이 재발급되고 Redis 값도 교체된다(RTR).")
    void given_ValidRefreshToken_when_Reissue_then_RotateTokenAndSuccess() throws Exception {
        // given
        TokenSetDto oldTokenSet = authTokenProvider.createTokenSet(savedUser.getId(), UserRole.USER);
        refreshTokenPort.save(savedUser.getId(), oldTokenSet.refreshToken(), 100L);
        Thread.sleep(1000); // 토큰 값 차이 발생용

        // when
        mockMvc.perform(post("/api/auth/reissue")
                        .cookie(new Cookie("refresh_token", oldTokenSet.refreshToken()))
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").isEmpty())
                .andExpect(jsonPath("$.data.access_token").exists())
                .andExpect(cookie().exists("refresh_token"))
                // --- REST Docs ---
                .andDo(document("auth-reissue",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        requestCookies(
                                cookieWithName("refresh_token").description("유효한 Refresh Token")
                        ),
                        responseCookies(
                                cookieWithName("refresh_token").description("새로운 Refresh Token (RTR 적용)")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("성공 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL).description("응답 메시지 (성공 시 null)").optional(),
                                fieldWithPath("data.access_token").type(JsonFieldType.STRING).description("새로운 Access Token")
                        )
                ));

        // then
        String newRefreshTokenInRedis = refreshTokenPort.getRefreshToken(savedUser.getId());
        assertThat(newRefreshTokenInRedis).isNotNull();
        assertThat(newRefreshTokenInRedis).isNotEqualTo(oldTokenSet.refreshToken());
    }

    @Test
    @DisplayName("재발급 실패: Redis에 저장된 토큰이 없으면(로그아웃 됨/만료됨) 401 예외를 반환한다.")
    void given_LoggedOutUser_when_Reissue_then_Unauthorized() throws Exception {
        // given
        TokenSetDto oldTokenSet = authTokenProvider.createTokenSet(savedUser.getId(), UserRole.USER);
        // Redis 저장 X (이미 만료됨 가정)

        // when & then
        mockMvc.perform(post("/api/auth/reissue")
                        .cookie(new Cookie("refresh_token", oldTokenSet.refreshToken()))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false));
    }

    @Test
    @DisplayName("재발급 실패: 위조된 Refresh Token으로 요청 시 401 예외를 반환한다.")
    void given_InvalidRefreshToken_when_Reissue_then_Unauthorized() throws Exception {
        // given
        String invalidToken = "eyJhbGciOiJIUzI1NiJ9.invalid.signature";

        // when & then
        mockMvc.perform(post("/api/auth/reissue")
                        .cookie(new Cookie("refresh_token", invalidToken))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isUnauthorized());
    }
}