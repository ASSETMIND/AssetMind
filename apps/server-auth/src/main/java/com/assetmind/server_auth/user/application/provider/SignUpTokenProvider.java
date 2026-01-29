package com.assetmind.server_auth.user.application.provider;

import com.assetmind.server_auth.global.util.JwtProcessor;
import com.assetmind.server_auth.user.exception.InvalidSignUpTokenException;
import io.jsonwebtoken.Claims;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

/**
 * 회원가입 도중 이메일 인증에 성공을 증명하는
 * 회원가입용 임시 토큰 발행 헬퍼 클래스
 */
@Component
@RequiredArgsConstructor
public class SignUpTokenProvider {

    private final JwtProcessor jwtProcessor;

    // 토큰 Claims의 payload - "type": "SIGN_UP"
    private static final String TYPE_CLAIM = "type";
    private static final String TYPE_SIGN_UP = "SIGN_UP";

    // 가입 토큰 유효기간: 30분 - 사용자가 정보 입력 시간 고려
    private static final long EXPIRATION_MS = 30 * 60 * 1000L;

    /**
     * 회원 가입용 토큰 생성
     * 인증 번호 검증 성공 시 사용
     * @param email - 토큰의 주인 (subject)
     * @return Jwt 문자열
     */
    public String createToken(String email) {
        return jwtProcessor.generate(
                email,
                Map.of(TYPE_CLAIM, TYPE_SIGN_UP),
                EXPIRATION_MS
        );
    }

    /**
     * 토큰 검증 및 이메일 추출
     * @param token
     * @return
     */
    public String getEmailFromToken(String token) {
        Claims claims = jwtProcessor.parse(token);

        validateTokenType(claims);

        return claims.getSubject();
    }

    /**
     * 토큰의 용도가 회원가입용 토큰인지 검증
     * @param claims
     */
    public void validateTokenType(Claims claims) {
        String type = claims.get(TYPE_CLAIM, String.class);

        if (type == null || !type.equals(TYPE_SIGN_UP)) {
            throw new InvalidSignUpTokenException();
        }
    }
}
