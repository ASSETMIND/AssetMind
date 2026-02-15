package com.assetmind.server_auth.global.filter;

import com.assetmind.server_auth.global.error.ErrorCode;
import com.assetmind.server_auth.user.application.provider.AuthTokenProvider;
import com.assetmind.server_auth.user.domain.type.UserRole;
import com.assetmind.server_auth.user.exception.AuthException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 클라이언트의 요청이 Controller에 도착하기 전에,
 * 요청 헤더의 "Authorization"에서 AccessToken을 꺼내 검증하고
 * 유효하다면 Security Context에 인증 정보 저장
 */
@Slf4j
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final AuthTokenProvider authTokenProvider;

    private static final String AUTHORIZATION_HEADER = "Authorization";

    private static final String PREFIX_BEARER = "Bearer ";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {

        // 토큰 추출 (없으면 null 반환)
        String token = resolveToken(request);

        // 토큰이 있고 유효하다면 인증 처리 (토큰이 필요없는 url 같은 경우에는 인증 처리가 필요 없음)
        if (token != null) {
            try {
                authTokenProvider.validateToken(token);

                UUID userId = authTokenProvider.getUserIdFromToken(token);
                UserRole role = authTokenProvider.getRoleFromToken(token);

                // Authentication 객체 생성 (권한 정보 포함!)
                Authentication authentication = new UsernamePasswordAuthenticationToken(
                        userId, // Principal
                        null,   // Credentials
                        List.of(new SimpleGrantedAuthority(role.getAuthority())) // Authorities (필수)
                );

                // SecurityContext에 저장
                SecurityContextHolder.getContext().setAuthentication(authentication);
                log.debug("Security Context에 '{}' 인증 정보를 저장했습니다.", userId);

            } catch (Exception e) {
                // 토큰은 있는데 파싱하다 터진 경우 -> 로그만 찍고 넘김 (결국 인증 실패로 401 뜸)
                log.error("사용자 인증 정보 저장 실패: {}", e.getMessage());
                SecurityContextHolder.clearContext();
            }
        }

        // 다음 필터로 진행
        filterChain.doFilter(request, response);
    }

    private String resolveToken(HttpServletRequest request) {
        String bearerToken = request.getHeader(AUTHORIZATION_HEADER);

        // 토큰이 존재하고, Bearer 로 시작하는 경우에만 추출
        if (StringUtils.hasText(bearerToken) && bearerToken.startsWith(PREFIX_BEARER)) {
            return bearerToken.substring(PREFIX_BEARER.length());
        }
        // 없거나 형식이 안 맞으면 null 반환
        return null;
    }
}
