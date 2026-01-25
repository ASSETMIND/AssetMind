package com.assetmind.server_auth.user.presentation;

import static org.junit.jupiter.api.Assertions.*;

import com.assetmind.server_auth.user.application.UserRegisterUseCase;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest
@AutoConfigureMockMvc(addFilters = false)
class UserRegisterControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Mock
    private UserRegisterUseCase userRegisterUseCase;

    @Test
    @DisplayName("성공: [GET] 이메일 중복 확인, 이메일이 중복이 아니면 false (200)을 반환한다.")
    void checkEmailDuplicate() {
    }

    @Test
    @DisplayName("성공: [GET] 이메일 중복 확인, 이메일이 중복이 이면 true (200)을 반환한다.")
    void checkEmailDuplicate_duplicated() {
    }

    @Test
    @DisplayName("성공: [POST] 인증 코드 전송, 유효한 이메일이면 전송 성공")
    void sendVerificationCode() {
    }

    @Test
    void verifyCode() {
    }

    @Test
    void register() {
    }
}