package com.assetmind.server_auth.user.infrastructure.persistence.redis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.verify;

import java.time.Duration;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

/**
 * RedisRefreshTokenAdapter 단위 테스트
 * 단위 테스트의 속도를 위해 실제 Redis를 띄우지 않고,
 * StringRedisTemplate의 메서드를 올바르게 호출 했는지 검증
 * 추후 통합테스트에서 실제 Redis를 통해 검증 예정
 */
@ExtendWith(MockitoExtension.class)
class RedisRefreshTokenAdapterTest {

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    @InjectMocks
    private RedisRefreshTokenAdapter redisRefreshTokenAdapter;

    private final UUID USER_ID = UUID.randomUUID();
    private final String REFRESH_TOKEN = "test-refresh-token";
    private final long TTL_SECONDS = 604800L; // 7일
    private final String EXPECTED_KEY = "REFRESH_TOKEN:" + USER_ID;

    @Test
    @DisplayName("저장 검증: Key에 Prefix가 붙고, TTL이 설정된 상태로 Redis에 저장한다.")
    void givenInfo_whenSave_thenSaveToken() {
        // given
        given(redisTemplate.opsForValue()).willReturn(valueOperations);

        // when
        redisRefreshTokenAdapter.save(USER_ID, REFRESH_TOKEN, TTL_SECONDS);

        // then
        then(valueOperations).should().set(
                eq(EXPECTED_KEY),
                eq(REFRESH_TOKEN),
                eq(Duration.ofSeconds(TTL_SECONDS))
        );
    }

    @Test
    @DisplayName("조회 검증: Prefix가 붙은 Key로 Redis 에서 리프레쉬 토큰을 조회한다.")
    void givenSavedKey_whenGetRefreshToken_thenReturnRefreshToken() {
        // given
        given(redisTemplate.opsForValue()).willReturn(valueOperations);
        given(valueOperations.get(EXPECTED_KEY)).willReturn(REFRESH_TOKEN);

        // when
        String result = redisRefreshTokenAdapter.getRefreshToken(USER_ID);

        // then
        assertThat(result).isEqualTo(REFRESH_TOKEN);

        // get 메서드가 정확한 키로 호출되었는지 확인
        verify(valueOperations).get(EXPECTED_KEY);
    }

    @Test
    @DisplayName("삭제 검증: Prefix가 붙은 Key로 Redis 에서 리프레쉬 토큰을 삭제한다.")
    void givenSavedKey_whenDelete_thenDeleteToken() {
        // when
        redisRefreshTokenAdapter.delete(USER_ID);

        // then
        // redisTemplate.delete()가 정확한 키로 호출되었는지 확인
        then(redisTemplate).should().delete(eq(EXPECTED_KEY));
    }
}