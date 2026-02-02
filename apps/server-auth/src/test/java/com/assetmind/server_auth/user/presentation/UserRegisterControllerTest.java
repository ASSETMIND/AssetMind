package com.assetmind.server_auth.user.presentation;

import static org.mockito.BDDMockito.*;
import static org.springframework.restdocs.mockmvc.MockMvcRestDocumentation.*;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.*;
import static org.springframework.restdocs.payload.PayloadDocumentation.*;
import static org.springframework.restdocs.request.RequestDocumentation.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.assetmind.server_auth.user.application.UserRegisterUseCase;
import com.assetmind.server_auth.user.exception.InvalidVerificationCode;
import com.assetmind.server_auth.user.exception.UserDuplicatedEmail;
import com.assetmind.server_auth.user.presentation.dto.SendVerificationCodeRequest;
import com.assetmind.server_auth.user.presentation.dto.UserRegisterRequest;
import com.assetmind.server_auth.user.presentation.dto.VerifyCodeRequest;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.restdocs.AutoConfigureRestDocs;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

/**
 * UserRegisterController 슬라이스 테스트
 * Request DTO의 @Valid 입력값 검증
 * GlobalExceptionHandler의 예외 처리 검증
 * 회원가입 API 성공 응답 검증
 */
@WebMvcTest(UserRegisterController.class)
@AutoConfigureMockMvc(addFilters = false)
@AutoConfigureRestDocs
class UserRegisterControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockitoBean
    private UserRegisterUseCase userRegisterUseCase;

    private final String EMAIL = "test@test.com";

    @Test
    @DisplayName("성공: [GET] 이메일 중복 확인, 이메일이 중복이 아니면 false (200) 응답한다.")
    void givenEmail_whenCheckEmailDuplicate_thenRespondFalse200() throws Exception {
        // given
        given(userRegisterUseCase.checkEmailDuplicate(EMAIL)).willReturn(false);

        // when & then
        mockMvc.perform(get("/api/auth/check-email")
                        .param("email", EMAIL)
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").isEmpty())
                .andExpect(jsonPath("$.data").value(false))

                // API 문서화 로직
                .andDo(document("auth-check-email",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        queryParameters(
                                parameterWithName("email").description("중복 확인 할 이메일")
                        ),
                        responseFields(
                                fieldWithPath("success").description("API 성공 여부"),
                                fieldWithPath("message").description("API 응답 메시지").optional(),
                                fieldWithPath("data").description("이메일 중복 여부 (true: 중복, false: 사용 가능)")
                        )
                ));

    }

    @Test
    @DisplayName("성공: [GET] 이메일 중복 확인, 이메일이 중복이 이면 true (200) 응답한다.")
    void givenDuplicatedEmail_whenCheckEmailDuplicate_thenRespondTrue200() throws Exception {
        // given
        String duplicatedEmail = "duplicated@test.com";
        given(userRegisterUseCase.checkEmailDuplicate(duplicatedEmail)).willReturn(true);

        // when & then
        mockMvc.perform(get("/api/auth/check-email")
                        .param("email", duplicatedEmail)
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").isEmpty())
                .andExpect(jsonPath("$.data").value(true));
    }

    @Test
    @DisplayName("성공: [POST] 인증 코드 전송, 유효한 이메일이면 전송 성공을 (200) 응답한다.")
    void givenSendVerificationCodeReq_whenSendVerificationCode_thenRespond200()
            throws Exception {
        // given
        SendVerificationCodeRequest request = new SendVerificationCodeRequest(EMAIL);

        // when & then
        mockMvc.perform(post("/api/auth/code")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").value("인증 코드 전송 성공"))
                .andExpect(jsonPath("$.data").isEmpty())

                // API 문서화 로직
                .andDo(document("auth-send-code",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),

                        requestFields(
                                fieldWithPath("email").description("인증 코드를 전송할 이메일")
                        ),

                        responseFields(
                                fieldWithPath("success").description("API 성공 여부"),
                                fieldWithPath("message").description("API 응답 메시지").optional(),
                                fieldWithPath("data").description("데이터 없음 (null)").optional()
                        )
                ));

        verify(userRegisterUseCase).sendVerificationCode(request.email());
    }

    @Test
    @DisplayName("실패: [POST] 인증 코드 전송, 형식이 잘못된 이메일이면 형식 오류 예외를 (400) 응답한다.")
    void givenInvalidEmail_whenSendVerificationCode_thenRespond400() throws Exception {
        // given
        String invalidEmail = "invalid2email.com";
        SendVerificationCodeRequest request = new SendVerificationCodeRequest(invalidEmail);

        // when & then
        mockMvc.perform(post("/api/auth/code")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("올바른 이메일 형식이 아닙니다."))
                .andExpect(jsonPath("$.data").isEmpty());

        verify(userRegisterUseCase, never()).sendVerificationCode(request.email());
    }

    @Test
    @DisplayName("실패: [POST] 인증 코드 전송, 중복된 이메일이면 중복 예외를 (409) 응답한다.")
    void givenDuplicatedEmail_whenSendVerificationCode_thenRespond409() throws Exception {
        // given
        String duplicatedEmail = "duplicated@test.com";
        SendVerificationCodeRequest request = new SendVerificationCodeRequest(duplicatedEmail);
        willThrow(UserDuplicatedEmail.class)
                .given(userRegisterUseCase)
                .sendVerificationCode(request.email());

        // when & then
        mockMvc.perform(post("/api/auth/code")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").isEmpty())
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("성공: [POST] 인증 코드 검증, 코드가 일치하면 회원가입용 토큰을 (200) 응답한다.")
    void givenVerifyCodeReq_whenVerifyCode_thenRespond200() throws Exception {
        // given
        VerifyCodeRequest request = new VerifyCodeRequest(EMAIL, "123456");
        String signUpToken = "sign.token.ey";
        given(userRegisterUseCase.verifyCode(request.email(), request.code())).willReturn(signUpToken);

        // when & then
        mockMvc.perform(post("/api/auth/code/verify")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").isEmpty())

                // API 문서화 로직
                .andDo(document("auth-verify-code",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),

                        requestFields(
                                fieldWithPath("email").description("유저의 이메일"),
                                fieldWithPath("code").description("전송된 6자리 인증 코드")
                        ),

                        responseFields(
                                fieldWithPath("success").description("API 성공 여부"),
                                fieldWithPath("message").description("API 응답 메시지").optional(),
                                fieldWithPath("data.sign_up_token").description("회원가입용 임시 JWT 토큰")
                        )
                ));
    }

    @Test
    @DisplayName("실패: [POST] 인증 코드 검증, 형식이 잘못된 이메일이면 형식 오류 예외를 (400) 응답한다.")
    void givenInvalidEmail_whenVerifyCode_thenRespond400() throws Exception {
        // given
        String invalidEmail = "invalid2Email";
        VerifyCodeRequest request = new VerifyCodeRequest(invalidEmail, "123456");

        // when & then
        mockMvc.perform(post("/api/auth/code/verify")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("올바른 이메일 형식이 아닙니다."))
                .andExpect(jsonPath("$.data").isEmpty());


        verify(userRegisterUseCase, never()).sendVerificationCode(request.email());
    }

    @Test
    @DisplayName("실패: [POST] 인증 코드 검증, 코드가 불일치하면 코드 불일치 예외를 (400) 응답한다.")
    void givenInvalidCode_whenVerifyCode_thenRespond400() throws Exception {
        // given
        VerifyCodeRequest request = new VerifyCodeRequest(EMAIL, "444444");
        given(userRegisterUseCase.verifyCode(request.email(), request.code()))
                .willThrow(InvalidVerificationCode.class);

        // when & then
        mockMvc.perform(post("/api/auth/code/verify")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("유효하지 않은 인증 코드입니다."))
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("성공: [POST] 회원 가입, 모든 데이터가 유효하면 가입 성공 및 UUID를 (201) 응답한다.")
    void givenUserRegisterReq_whenRegister_thenRespond201() throws Exception {
        // given
        UserRegisterRequest request = new UserRegisterRequest(EMAIL, "@Test1234",
                "테스트001", "ey.sign.token");
        UUID willCreatedUserId = UUID.randomUUID();
        given(userRegisterUseCase.register(request.toCommand())).willReturn(willCreatedUserId);

        // when & then
        mockMvc.perform(post("/api/auth/register")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").isEmpty())
                .andExpect(jsonPath("$.data").value(willCreatedUserId.toString()))

                // API 문서화 로직
                .andDo(document("auth-register",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),

                        requestFields(
                                fieldWithPath("email").description("이메일"),
                                fieldWithPath("password").description("비밀번호"),
                                fieldWithPath("user_name").description("서비스에서 사용할 유저 이름"),
                                fieldWithPath("sign_up_token").description("인증 검증 시 발급 받은 임시 토큰")
                        ),

                        responseFields(
                                fieldWithPath("success").description("API 성공 여부"),
                                fieldWithPath("message").description("API 응답 메시지").optional(),
                                fieldWithPath("data").description("회원 가입 된 사용자 UUID").optional()
                        )
                ));
    }

    @Test
    @DisplayName("실패: [POST] 회원 가입, 요청 비밀번호 패턴 불일치 시 형식 예외를 (400) 응답한다.")
    void givenInvalidPassword_whenRegister_thenRespond400() throws Exception {
        // given
        UserRegisterRequest request = new UserRegisterRequest(EMAIL, "12345678",
                "테스트001", "ey.sign.token");

        // when & then
        mockMvc.perform(post("/api/auth/register")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("비밀번호는 8자 이상, 영문/숫자/특수문자를 포함해야 합니다."))
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("실페: [POST] 회원 가입, 토큰 이메일과 요청 이메일이 불일치하면 불일치 예외를 (400) 응답한다.")
    void givenInvalidTokenEmail_whenRegister_thenRespond400() throws Exception {
        // given
        String invalidEmail = "invalid@email.test";
        UserRegisterRequest request = new UserRegisterRequest(invalidEmail, "@Test1234",
                "테스트001", "ey.sign.token");

        given(userRegisterUseCase.register(request.toCommand())).willThrow(IllegalArgumentException.class);

        // when & then
        mockMvc.perform(post("/api/auth/register")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").isEmpty())
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("실패: [POST] 회원 가입, 요청 이메일이 중복된 이메일이면 중복 예외를 (409) 응답한다.")
    void givenDuplicatedEmail_whenRegister_thenRespond400() throws Exception {
        // given
        String duplicatedEmail = "duplicated@email.test";
        UserRegisterRequest request = new UserRegisterRequest(duplicatedEmail, "@Test1234",
                "테스트001", "ey.sign.token");

        given(userRegisterUseCase.register(request.toCommand())).willThrow(UserDuplicatedEmail.class);

        // when & then
        mockMvc.perform(post("/api/auth/register")
                        .content(objectMapper.writeValueAsString(request))
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").isEmpty())
                .andExpect(jsonPath("$.data").isEmpty());
    }
}