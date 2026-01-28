package com.assetmind.server_auth.integration;

import com.assetmind.server_auth.support.IntegrationTestSupport;
import com.assetmind.server_auth.user.application.provider.SignUpTokenProvider;
import com.assetmind.server_auth.user.application.port.EmailSendPort;
import com.assetmind.server_auth.user.domain.type.UserRole;
import com.assetmind.server_auth.user.infrastructure.persistence.jpa.UserEntity;
import com.assetmind.server_auth.user.infrastructure.persistence.jpa.UserJpaRepository;
import com.assetmind.server_auth.user.presentation.dto.SendVerificationCodeRequest;
import com.assetmind.server_auth.user.presentation.dto.UserRegisterRequest;
import com.assetmind.server_auth.user.presentation.dto.VerifyCodeRequest;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 회원가입 통합 테스트 (Controller + Service + Repository + Redis)
 */
@Transactional
class UserRegisterIntegrationTest extends IntegrationTestSupport {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper objectMapper;
    @Autowired UserJpaRepository userRepository;
    @Autowired StringRedisTemplate redisTemplate;
    @Autowired PasswordEncoder passwordEncoder;
    @Autowired SignUpTokenProvider signUpTokenProvider; // 실제 토큰 생성기 사용

    // 외부 연동인 이메일 발송만 Mocking
    @MockitoBean EmailSendPort emailSendPort;

    private final String EMAIL = "test@test.com";

    // =================================================================
    // 1. 이메일 중복 확인 (checkEmailDuplicate)
    // =================================================================

    @Test
    @DisplayName("성공: [GET] 중복된 이메일이 아니면 false를 응답한다.")
    void checkEmail_WhenValidEmail_ThenReturnFalse() throws Exception {
        // given: DB 비어있음

        // when & then
        mockMvc.perform(get("/api/auth/check-email")
                        .param("email", EMAIL)
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data").value(false));
    }

    @Test
    @DisplayName("성공: [GET] 중복된 이메일이면 true를 응답한다.")
    void checkEmail_WhenDuplicatedEmail_ThenReturnTrue() throws Exception {
        // given: DB에 유저 저장
        saveUserInDb(EMAIL);

        // when & then
        mockMvc.perform(get("/api/auth/check-email")
                        .param("email", EMAIL)
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data").value(true));
    }

    // =================================================================
    // 2. 인증 코드 전송 (sendVerificationCode)
    // =================================================================

    @Test
    @DisplayName("성공: [POST] 중복되지 않은 이메일이면 Redis에 저장하고 이메일을 발송한다.")
    void sendVerification_WhenValidEmail_ThenSaveRedisAndSendEmail() throws Exception {
        // given
        SendVerificationCodeRequest request = new SendVerificationCodeRequest(EMAIL);

        // when
        mockMvc.perform(post("/api/auth/code")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));

        // then 1: Redis 저장 확인 (ServiceTest의 verificationCodePort.save 검증 대응)
        String redisKey = "AUTH_CODE:" + EMAIL; // 실제 키 패턴 확인 필요
        String savedCode = redisTemplate.opsForValue().get(redisKey);
        assertThat(savedCode).isNotNull().hasSize(6);

        // then 2: 이메일 발송 포트 호출 확인 (ServiceTest의 verify(emailSendPort) 대응)
        verify(emailSendPort).sendEmail(eq(EMAIL), anyString(), eq(savedCode));
    }

    @Test
    @DisplayName("실패: [POST] 중복된 이메일이면 409 예외를 던진다.")
    void sendVerification_WhenDuplicatedEmail_ThenThrowException() throws Exception {
        // given
        saveUserInDb(EMAIL);
        SendVerificationCodeRequest request = new SendVerificationCodeRequest(EMAIL);

        // when & then
        mockMvc.perform(post("/api/auth/code")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isConflict()) // UserDuplicatedEmail -> 409 Conflict
                .andExpect(jsonPath("$.success").value(false));
    }

    // =================================================================
    // 3. 인증 코드 검증 (verifyCode)
    // =================================================================

    @Test
    @DisplayName("성공: [POST] 유효한 코드면 Redis에서 삭제하고 토큰을 발급한다.")
    void verifyCode_WhenValidCode_ThenRemoveAndReturnToken() throws Exception {
        // given: Redis에 코드 세팅
        String correctCode = "123456";
        redisTemplate.opsForValue().set("AUTH_CODE:" + EMAIL, correctCode);

        VerifyCodeRequest request = new VerifyCodeRequest(EMAIL, correctCode);

        // when
        mockMvc.perform(post("/api/auth/code/verify")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.sign_up_token").isNotEmpty());

        // then: Redis에서 삭제되었는지 확인 (ServiceTest의 verify(..remove) 대응)
        String savedCode = redisTemplate.opsForValue().get("AUTH_CODE:" + EMAIL);
        assertThat(savedCode).isNull();
    }

    @Test
    @DisplayName("실패: [POST] 유효하지 않은 코드면 400 예외를 던지고 코드는 유지된다.")
    void verifyCode_WhenInvalidCode_ThenThrowException() throws Exception {
        // given
        String correctCode = "123456";
        redisTemplate.opsForValue().set("AUTH_CODE:" + EMAIL, correctCode);

        VerifyCodeRequest request = new VerifyCodeRequest(EMAIL, "999999"); // 틀린 코드

        // when & then
        mockMvc.perform(post("/api/auth/code/verify")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));

        // then: Redis에 코드가 여전히 남아있는지 확인
        String savedCode = redisTemplate.opsForValue().get("AUTH_CODE:" + EMAIL);
        assertThat(savedCode).isEqualTo(correctCode);
    }

    // =================================================================
    // 4. 회원 가입 (register)
    // =================================================================

    @Test
    @DisplayName("성공: [POST] 올바른 요청이면 회원가입에 성공하고 DB에 저장한다.")
    void register_WhenValidRequest_ThenSaveUser() throws Exception {
        // given
        String token = signUpTokenProvider.createToken(EMAIL); // 실제 토큰 생성기 사용
        UserRegisterRequest request = new UserRegisterRequest(
                EMAIL, "Password123!", "테스터", token
        );

        // when
        mockMvc.perform(post("/api/auth/register")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data").isNotEmpty()); // UUID 반환 확인

        // then: DB 저장 검증
        UserEntity savedUser = userRepository.findByEmail(EMAIL).orElseThrow();
        assertThat(savedUser.getUsername()).isEqualTo("테스터");
        assertThat(passwordEncoder.matches("Password123!", savedUser.getPassword())).isTrue();
    }

    @Test
    @DisplayName("실패: [POST] 토큰의 이메일과 입력 이메일이 다르면 400/401 에러 발생")
    void register_WhenEmailMismatch_ThenThrowException() throws Exception {
        // given
        String token = signUpTokenProvider.createToken("other@test.com"); // 토큰은 다른 이메일
        UserRegisterRequest request = new UserRegisterRequest(
                EMAIL, "Password123!", "테스터", token // 요청은 EMAIL
        );

        // when & then
        mockMvc.perform(post("/api/auth/register")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest()); // 혹은 isUnauthorized
    }

    @Test
    @DisplayName("실패: [POST] 가입 시점에 이메일이 중복되면 409 에러 발생")
    void register_WhenDuplicatedEmail_ThenThrowException() throws Exception {
        // given
        saveUserInDb(EMAIL); // 이미 가입됨
        String token = signUpTokenProvider.createToken(EMAIL);

        UserRegisterRequest request = new UserRegisterRequest(
                EMAIL, "Password123!", "테스터", token
        );

        // when & then
        mockMvc.perform(post("/api/auth/register")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isConflict());
    }

    // 헬퍼 메서드: DB에 유저 저장
    private void saveUserInDb(String email) {
        userRepository.save(new UserEntity(
                UUID.randomUUID(), email, "existingUser", "password",
                null, null, UserRole.USER
        ));
    }
}