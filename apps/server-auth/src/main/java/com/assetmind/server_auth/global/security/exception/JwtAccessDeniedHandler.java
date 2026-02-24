package com.assetmind.server_auth.global.security.exception;

import com.assetmind.server_auth.global.common.ApiResponse;
import com.assetmind.server_auth.global.error.ErrorCode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.stereotype.Component;

/**
 * 인증은 되었으나(로그인 O), 해당 리소스에 접근할 권한이 없을 때(Role 부족 등)
 * 403 에러를 JSON으로 응답을 담당하는 핸들러
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAccessDeniedHandler implements AccessDeniedHandler {

    private final ObjectMapper objectMapper;

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
            AccessDeniedException accessDeniedException) throws IOException, ServletException {

        log.warn(">>> [JWT Access Denied] 인가 실패 - URL: {}, Error: {}",
                request.getRequestURI(), accessDeniedException.getMessage());

        // HTTP Status, Content-Type 설정 (403 Forbidden)
        response.setStatus(HttpServletResponse.SC_FORBIDDEN);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");

        ApiResponse<Object> responseBody = ApiResponse.fail(ErrorCode.FORBIDDEN_ACCESS.getMessage());

        // JSON 응답 전송
        objectMapper.writeValue(response.getOutputStream(), responseBody);
    }
}
