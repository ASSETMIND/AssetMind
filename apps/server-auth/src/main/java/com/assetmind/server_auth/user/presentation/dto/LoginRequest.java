package com.assetmind.server_auth.user.presentation.dto;

import com.assetmind.server_auth.user.application.dto.UserLoginCommand;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public record LoginRequest(
        @NotBlank(message = "이메일은 필수입니다.")
        @Email(message = "올바른 이메일 형식이 아닙니다.")
        String email,

        @NotBlank(message = "비밀번호는 필수입니다.")
        @Pattern(regexp = "^(?=.*[A-Za-z])(?=.*\\d)(?=.*[@$!%*#?&])[A-Za-z\\d@$!%*#?&]{8,}$",
                message = "비밀번호는 8자 이상, 영문/숫자/특수문자를 포함해야 합니다.")
        String password
) {

    public UserLoginCommand toCommand() {
        return new UserLoginCommand(this.email, this.password);
    }

}
