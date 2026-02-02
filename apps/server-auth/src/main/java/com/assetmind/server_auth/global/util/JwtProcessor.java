package com.assetmind.server_auth.global.util;

import com.assetmind.server_auth.global.config.JwtProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.Jwts.SIG;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.Map;
import javax.crypto.SecretKey;
import org.springframework.stereotype.Component;

/**
 * 비즈니스 로직은 전혀 모르는
 * 토큰 생성과 토큰을 파싱하는 공통 유틸 모듈
 */
@Component
public class JwtProcessor {

    private final SecretKey key;

    public JwtProcessor(JwtProperties properties) {
        this.key = Keys.hmacShaKeyFor(
                properties.secret().getBytes(StandardCharsets.UTF_8)
        );
    }

    /**
     * 토큰 생성
     * @param subject - 토큰의 주인 (email or userId)
     * @param claims - 토큰에 담을 정보들 (Map을 이용)
     * @param expireMs - 유효기간
     * @return 생성된 Jwt 문자열
     */
    public String generate(String subject, Map<String, Object> claims, long expireMs) {
        return Jwts.builder()
                .subject(subject)       // sub: 누구의 토큰인가
                .claims(claims)         // payload: 커스텀 데이터
                .issuedAt(new Date())   // issueAt: 만든 날짜
                .expiration(new Date(System.currentTimeMillis() + expireMs)) // 만료기간
                .signWith(key, SIG.HS256) // 서명
                .compact();
    }

    /**
     * 토큰 검증이 포함된 토큰 파싱
     * 만료되거나 위조된 토큰이면 jjwt 라이브러리가 알아서 예외를 던짐
     * @param token - jwt 토큰
     * @return 토큰 생성시 넣었던 데이터
     */
    public Claims parse(String token) {
        return Jwts.parser()
                .verifyWith(key)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }
}
