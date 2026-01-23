package com.assetmind.server_auth.user.presentation;

import com.assetmind.server_auth.global.common.ApiResponse;
import com.assetmind.server_auth.user.application.UserRegisterUseCase;
import com.assetmind.server_auth.user.presentation.dto.SendVerificationCodeRequest;
import com.assetmind.server_auth.user.presentation.dto.UserRegisterRequest;
import com.assetmind.server_auth.user.presentation.dto.VerifyCodeRequest;
import com.assetmind.server_auth.user.presentation.dto.VerifyCodeResponse;
import jakarta.validation.Valid;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class UserRegisterController {

    private final UserRegisterUseCase userRegisterUseCase;

    @GetMapping("/check-email")
    public ApiResponse<Boolean> checkEmailDuplicate(@RequestParam String email) {
        boolean isDuplicated = userRegisterUseCase.checkEmailDuplicate(email);

        return ApiResponse.success(isDuplicated);
    }

    @PostMapping("/code")
    public ApiResponse<Void> sendVerificationCode(@RequestBody @Valid SendVerificationCodeRequest request) {
        userRegisterUseCase.sendVerificationCode(request.email());

        return ApiResponse.success("인증 코드 전송 성공");
    }

    @PostMapping("/code/verify")
    public ApiResponse<VerifyCodeResponse> verifyCode(@RequestBody @Valid VerifyCodeRequest request) {
        String token = userRegisterUseCase.verifyCode(request.email(), request.code());

        return ApiResponse.success(token);
    }

    @PostMapping("/register")
    public ApiResponse<UUID> register(@RequestBody @Valid UserRegisterRequest request) {
        UUID userId = userRegisterUseCase.register(request.toCommand());

        return ApiResponse.success(userId);
    }
}
