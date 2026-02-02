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
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.stereotype.Component;

/**
 * 사용자가 인증 없이(혹은 유효하지 않은 토큰으로) 보호된 리소스에 접근하려 할 때,
 * 401 에러를 JSON으로 응답을 담당하는 핸들러
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthenticationEntryPoint implements AuthenticationEntryPoint {

    private final ObjectMapper objectMapper;

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response,
            AuthenticationException authException) throws IOException, ServletException {

        log.error(">>> [JWT Authentication EntryPoint] 인증 실패 - URL: {}, Error: {} ",
                request.getRequestURI(), authException.getMessage());

        // HTTP Status, Content-Type 설정
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");

        ApiResponse<Object> responseBody = ApiResponse.fail(ErrorCode.INVALID_TOKEN.getMessage());

        // JSON 응답 전송
        objectMapper.writeValue(response.getOutputStream(), responseBody);
    }
}
