package com.assetmind.server_auth.user.presentation;

import com.assetmind.server_auth.global.common.ApiResponse;
import com.assetmind.server_auth.global.util.CookieUtils;
import com.assetmind.server_auth.user.application.UserAuthUseCase;
import com.assetmind.server_auth.user.application.dto.TokenSetDto;
import com.assetmind.server_auth.user.presentation.dto.LoginRequest;
import com.assetmind.server_auth.user.presentation.dto.LoginResponse;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 인증 관련 Controller
 * 로그인/로그아웃, ID/PW 찾기의 API 담당
 */
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class UserAuthController {

    private final UserAuthUseCase userAuthUseCase;
    private final CookieUtils cookieUtils;

    /**
     * 로그인 API
     * POST /api/auth/login
     */
    @PostMapping("/login")
    public ApiResponse<LoginResponse> login(@RequestBody @Valid LoginRequest request, HttpServletResponse response) {
        TokenSetDto tokenSet = userAuthUseCase.login(request.toCommand());

        // 쿠키 생성
        ResponseCookie refreshTokenCookie = cookieUtils.createRefreshTokenCookie(
                tokenSet.refreshToken(), tokenSet.refreshTokenExpire() / 1000);

        // 응답 헤더에 쿠키 추가
        response.addHeader(HttpHeaders.SET_COOKIE, refreshTokenCookie.toString());

        return ApiResponse.success(new LoginResponse(tokenSet.accessToken()));
    }

    /**
     * 로그아웃 API
     * @AuthenticationPrincipal을 사용하여 SecurityContextHolder에 있는 userId를 바로 주입받음
     */
    @PostMapping("/logout")
    public ApiResponse<Void> logout(@AuthenticationPrincipal UUID userId, HttpServletResponse response) {
        userAuthUseCase.logout(userId);

        ResponseCookie deletedCookie = cookieUtils.createDeletedCookie();

        response.addHeader(HttpHeaders.SET_COOKIE, deletedCookie.toString());

        return ApiResponse.success("로그아웃 성공");
    }
}
