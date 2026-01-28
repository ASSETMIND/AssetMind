package com.assetmind.server_auth.user.application.provider;

import com.assetmind.server_auth.global.common.JwtProcessor;
import com.assetmind.server_auth.user.application.dto.TokenSetDto;
import com.assetmind.server_auth.user.domain.type.UserRole;
import io.jsonwebtoken.Claims;
import java.util.Map;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

/**
 * 로그인 성공 후 서비스 이용을 위한
 * Access/Refresh Token을 발행 헬퍼 클래스
 */
@Component
@RequiredArgsConstructor
public class AuthTokenProvider {

    private final JwtProcessor jwtProcessor;

    // accessToken 만료시간 30분
    private static final long ACCESS_EXPIRATION_MS = 30 * 60 * 1000L;

    // refreshToken 만료시간 7일
    private static final long REFRESH_EXPIRATION_MS = 7 * 24 * 60 * 60 * 1000L;

    private static final String ROLE_CLAIM = "role";

    /**
     * accessToken과 refreshToken을 생성하고
     * access/refresh token 세트를 응답한다.
     * @param userId - 서명, 토큰의 주인
     * @param role - body
     * @return
     */
    public TokenSetDto createTokenSet(UUID userId, UserRole role) {
        String subject = userId.toString();
        Map<String, Object> claims = Map.of(ROLE_CLAIM, role);

        String accessToken = jwtProcessor.generate(subject, claims, ACCESS_EXPIRATION_MS);
        String refreshToken = jwtProcessor.generate(subject, claims, REFRESH_EXPIRATION_MS);

        return new TokenSetDto(accessToken, refreshToken, REFRESH_EXPIRATION_MS);
    }

    /**
     * 토큰을 통해 subject인 UUID를 반환한다.
     * @param token
     * @return UUID
     */
    public UUID getUserIdFromToken(String token) {
        Claims claims = jwtProcessor.parse(token);

        return UUID.fromString(claims.getSubject());
    }

    /**
     * 토큰을 통해 해당 토큰 주인의 role을 반환한다.
     * @param token
     * @return GUEST/USER
     */
    public UserRole getRoleFromToken(String token) {
        Claims claims = jwtProcessor.parse(token);
        String roleString = claims.get(ROLE_CLAIM, String.class);
        return UserRole.valueOf(roleString);

    }
}
