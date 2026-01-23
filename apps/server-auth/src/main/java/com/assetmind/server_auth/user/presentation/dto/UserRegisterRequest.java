package com.assetmind.server_auth.user.presentation.dto;

import com.assetmind.server_auth.user.application.dto.UserRegisterCommand;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record UserRegisterRequest(
        @NotBlank(message = "이메일은 필수입니다.")
        @Email(message = "올바른 이메일 형식이 이납니다.")
        String email,

        @NotBlank(message = "비밀번호는 필수입니다.")
        @Pattern(regexp = "^(?=.*[A-Za-z])(?=.*\\d)(?=.*[@$!%*#?&])[A-Za-z\\d@$!%*#?&]{8,}$",
                message = "비밀번호는 8자 이상, 영문/숫자/특수문자를 포함해야 합니다.")
        String password,

        @NotBlank(message = "이름은 필수입니다.")
        @Size(min = 2, max = 15, message = "이름이 너무 짧거나 깁니다.")
        @JsonProperty("user_name")
        String username,

        @NotBlank(message = "회원 가입용 토큰이 필요합니다.")
        @JsonProperty("sign_up_token")
        String signUpToken
) {

    public UserRegisterCommand toCommand() {
        return new UserRegisterCommand(email, password, username, signUpToken);
    }
}
