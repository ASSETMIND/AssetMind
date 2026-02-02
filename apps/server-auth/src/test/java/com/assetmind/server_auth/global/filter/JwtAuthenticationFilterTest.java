package com.assetmind.server_auth.global.filter;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willDoNothing;
import static org.mockito.BDDMockito.willThrow;

import com.assetmind.server_auth.global.error.ErrorCode;
import com.assetmind.server_auth.user.application.provider.AuthTokenProvider;
import com.assetmind.server_auth.user.domain.type.UserRole;
import com.assetmind.server_auth.user.exception.AuthException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

@ExtendWith(MockitoExtension.class)
class JwtAuthenticationFilterTest {

    @Mock
    private AuthTokenProvider authTokenProvider;

    @Mock
    private HttpServletRequest request;

    @Mock
    private HttpServletResponse response;

    @Mock
    private FilterChain filterChain;

    @InjectMocks
    private JwtAuthenticationFilter jwtAuthenticationFilter;

    // 테스트 독립성을 위해 테스트가 끝나면 ContextHolder를 비움
    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    @Test
    @DisplayName("성공: 유효한 토큰이 헤더에 있다면 인증 객체를 SecurityContext에 저장하고 다음 필터로 진행한다.")
    void givenValidToken_whenDoFilter_thenSetAuthentication() throws Exception {
        // given
        String validToken = "valid-access-token";
        String bearerToken = "Bearer " + validToken;
        UUID userId = UUID.randomUUID();
        UserRole role = UserRole.USER; // ROLE_USER

        // 헤더 세팅
        given(request.getHeader("Authorization")).willReturn(bearerToken);

        // Provider 동작 Mocking
        willDoNothing().given(authTokenProvider).validateToken(validToken);
        given(authTokenProvider.getUserIdFromToken(validToken)).willReturn(userId);
        given(authTokenProvider.getRoleFromToken(validToken)).willReturn(role);

        // when
        jwtAuthenticationFilter.doFilterInternal(request, response, filterChain);

        // then
        // SecurityContext에 인증 객체가 담겼는지 확인
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        assertThat(authentication).isNotNull();
        assertThat(authentication.getPrincipal()).isEqualTo(userId);
        assertThat(authentication.getAuthorities()).hasSize(1);
        assertThat(authentication.getAuthorities().iterator().next().getAuthority()).isEqualTo(role.getAuthority());

        then(filterChain).should().doFilter(request, response);
    }

    @Test
    @DisplayName("통과: 헤더에 토큰이 없다면 인증 객체 없이 다음 필터로 진행한다. (공개 API 접근 시나리오)")
    void givenNoToken_whenDoFilter_thenPassThrough() throws Exception {
        // given
        given(request.getHeader("Authorization")).willReturn(null);

        // when
        jwtAuthenticationFilter.doFilterInternal(request, response, filterChain);

        // then
        // 공개 API 이므로 토큰은 null
        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();

        then(authTokenProvider).shouldHaveNoInteractions();

        then(filterChain).should().doFilter(request, response);
    }

    @Test
    @DisplayName("실패: 토큰 형식이 Bearer가 아니라면 인증 객체 없이 다음 필터로 진행한다.")
    void givenInvalidHeaderFormat_whenDoFilter_thenPassThrough() throws Exception {
        // given
        given(request.getHeader("Authorization")).willReturn("Basic invalid-format");

        // when
        jwtAuthenticationFilter.doFilterInternal(request, response, filterChain);

        // then
        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
        then(authTokenProvider).shouldHaveNoInteractions();
        then(filterChain).should().doFilter(request, response);
    }

    @Test
    @DisplayName("예외 처리: 토큰 검증 중 예외가 발생하면(만료/위조) SecurityContext를 비우고 다음 필터로 진행한다.")
    void givenInvalidToken_whenDoFilter_thenClearContextAndPass() throws Exception {
        // given
        String invalidToken = "invalid-token";
        given(request.getHeader("Authorization")).willReturn("Bearer " + invalidToken);

        // validateToken 호출 시 예외 발생 Mocking
        willThrow(new AuthException(ErrorCode.INVALID_TOKEN))
                .given(authTokenProvider).validateToken(invalidToken);

        // when
        jwtAuthenticationFilter.doFilterInternal(request, response, filterChain);

        // then
        // Context가 비어있는지 검증
        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();

        // 다음 필터 호출 하는지 검증 (다음 필터들이 401 예외 검증)
        then(filterChain).should().doFilter(request, response);
    }
}