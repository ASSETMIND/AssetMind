package com.assetmind.server_auth.user.infrastructure.persistence.redis;

import com.assetmind.server_auth.user.application.port.RefreshTokenPort;
import java.time.Duration;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

/**
 * Redis를 활용한 RefreshToken 저장소 어댑터
 * RefreshToken 을 Redis에 저장하고 관리
 * TTL을 활용해 유효기간이 지나면 데이터가 자동 삭제
 */
@Component
@RequiredArgsConstructor
public class RedisRefreshTokenAdapter implements RefreshTokenPort {

    private final StringRedisTemplate redisTemplate;

    // Redis Key 구분자 (예: "REFRESH_TOKEN:uuid-1234-1512...")
    private static final String PREFIX_KEY = "REFRESH_TOKEN:";

    @Override
    public void save(UUID userId, String refreshToken, long ttlSeconds) {
        String key = PREFIX_KEY + userId.toString();

        redisTemplate.opsForValue().set(
                key,
                refreshToken,
                Duration.ofSeconds(ttlSeconds)
        );
    }

    @Override
    public String getRefreshToken(UUID userId) {
        String key = PREFIX_KEY + userId.toString();

        return redisTemplate.opsForValue().get(key);
    }

    @Override
    public void delete(UUID userId) {
        String key = PREFIX_KEY + userId.toString();

        redisTemplate.delete(key);
    }
}
