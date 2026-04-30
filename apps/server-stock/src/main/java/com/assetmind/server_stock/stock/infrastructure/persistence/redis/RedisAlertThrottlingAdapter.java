package com.assetmind.server_stock.stock.infrastructure.persistence.redis;

import com.assetmind.server_stock.stock.application.port.AlertThrottlingPort;
import java.time.Duration;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

/**
 * {@link AlertThrottlingPort}에 대한 구현체(Adapter)로써
 * Redis를 이용하여 실시간으로 급등락한 종목에 대한 중복된 알림을 방지하기 위해
 * Redis에 전송한 알림은 캐싱해놓는 방식으로 쓰로틀링을 구현
 *
 * Key - alert:surge:throttle:{stockCode}
 * Value - "LOCKED"
 */
@Component
@RequiredArgsConstructor
public class RedisAlertThrottlingAdapter implements AlertThrottlingPort {

    private final StringRedisTemplate redisTemplate;

    private static final String KEY_PREFIX = "alert:surge:throttle:";
    private static final Duration THROTTLE_TTL = Duration.ofMinutes(30);

    @Override
    public boolean allowAlert(String stockCode) {
        String key = KEY_PREFIX + stockCode;

        // SETNX (Set if Not eXists) : 키가 없을 때만 값을 세팅하고 true를 반환
        // 만약 키가 존재한다면 false를 반환하여 중복 알림 방지
        Boolean isAllowed = redisTemplate.opsForValue()
                .setIfAbsent(key, "LOCKED", THROTTLE_TTL);
        return Boolean.TRUE.equals(isAllowed);
    }
}
