package com.assetmind.server_auth.user.infrastructure.persistence.redis;

import com.assetmind.server_auth.user.application.port.VerificationCodePort;
import java.time.Duration;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

/**
 * Redis 인증 코드 저장소 어댑터
 * 이메일 인증 코드를 Redis에 저장하고 관리
 * TTL을 활용해 유효기간이 지나면 데이터가 자동 삭제
 */
@Repository
@RequiredArgsConstructor
public class RedisVerificationCodeAdapter implements VerificationCodePort {

    private final StringRedisTemplate redisTemplate;

    // Redis Key 구분자 (예: "AUTH_CODE:test@email.com"(키) )
    private final String PREFIX_KEY = "AUTH_CODE:";

    @Override
    public void save(String email, String code, long ttlSeconds) {
        redisTemplate.opsForValue().set(
                PREFIX_KEY + email, // key
                code,   // value
                Duration.ofSeconds(ttlSeconds)  // TTL
        );
    }

    @Override
    public String getCode(String email) {
        return redisTemplate.opsForValue().get(PREFIX_KEY + email);
    }

    @Override
    public void remove(String email) {
        redisTemplate.delete(PREFIX_KEY + email);
    }
}
