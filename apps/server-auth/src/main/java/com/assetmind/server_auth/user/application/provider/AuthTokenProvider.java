package com.assetmind.server_auth.user.application.provider;

import com.assetmind.server_auth.global.common.JwtProcessor;
import com.assetmind.server_auth.global.error.ErrorCode;
import com.assetmind.server_auth.user.application.dto.TokenSetDto;
import com.assetmind.server_auth.user.domain.type.UserRole;
import com.assetmind.server_auth.user.exception.AuthException;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.MalformedJwtException;
import java.security.SignatureException;
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
        Claims claims = getClaims(token);

        return UUID.fromString(claims.getSubject());
    }

    /**
     * 토큰을 통해 해당 토큰 주인의 role을 반환한다.
     * @param token
     * @return GUEST/USER
     */
    public UserRole getRoleFromToken(String token) {
        Claims claims = getClaims(token);
        String roleString = claims.get(ROLE_CLAIM, String.class);

        return UserRole.valueOf(roleString);
    }

    /**
     * 토큰 값을 검증하고 예외를 던진다.
     * @param token
     */
    public void validateToken(String token) {
        getClaims(token);
    }

    private Claims getClaims(String token) {
        try {
            Claims claims = jwtProcessor.parse(token);

            // 로그인 시 받은 Auth 용 토큰이 아니라면 타입 에러
            if (claims.get(ROLE_CLAIM) == null) {
                throw new AuthException(ErrorCode.INVALID_TOKEN_TYPE);
            }

            return claims;
        } catch (ExpiredJwtException e) {
            // 토큰이 만료 됐을 때
            throw new AuthException(ErrorCode.EXPIRED_TOKEN);
        } catch (MalformedJwtException e) {
            // 토큰 서명이 유효하지 않을 떄
            throw new AuthException(ErrorCode.INVALID_TOKEN_SIGNATURE);
        } catch (AuthException e) {
            // try 문에서 던진 예외가 다른 예외로 잡히지 않기 위함
            throw e;
        } catch (Exception e) {
            // 그외 모든 오류
            throw new AuthException(ErrorCode.INVALID_TOKEN);
        }
    }
}
