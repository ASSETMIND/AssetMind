package com.assetmind.server_stock.stock.infrastructure.persistence.redis;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import java.time.Duration;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

@ExtendWith(MockitoExtension.class)
class RedisAlertThrottlingAdapterTest {

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    @InjectMocks
    private RedisAlertThrottlingAdapter adapter;

    @Test
    @DisplayName("성공: Redis에 키가 없어서 락 획득에 성공하면 true를 반환한다.")
    void givenStockCode_whenAllowAlert_thenSetValueLOCKEDAndReturnTrue() {
        // given
        String stockCode = "005930";
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.setIfAbsent(eq("alert:surge:throttle:" + stockCode), eq("LOCKED"), any(Duration.class)))
                .thenReturn(true);

        // when
        boolean result = adapter.allowAlert(stockCode);

        // then
        assertTrue(result);
    }

    @Test
    @DisplayName("실패: Redis에 키가 이미 존재하여 락 획득에 실패하면 false를 반환한다.")
    void givenExistsKeyStockCode_whenAllowAlert_thenReturnFalse() {
        // given
        String stockCode = "005930";
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.setIfAbsent(eq("alert:surge:throttle:" + stockCode), eq("LOCKED"), any(Duration.class)))
                .thenReturn(false);

        // when
        boolean result = adapter.allowAlert(stockCode);

        // then
        assertFalse(result);
    }
}