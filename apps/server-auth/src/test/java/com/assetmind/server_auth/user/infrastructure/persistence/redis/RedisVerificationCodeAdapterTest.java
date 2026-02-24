package com.assetmind.server_auth.user.infrastructure.persistence.redis;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;

/**
 * RedisVerificationCodeAdapter 단위 테스트
 * 단위 테스트의 속도를 위해 실제 Redis를 띄우지 않고,
 * StringRedisTemplate의 메서드를 올바르게 호출 했는지 검증
 * 추후 통합테스트에서 실제 Redis를 통해 검증 예정
 */
@ExtendWith(MockitoExtension.class)
class RedisVerificationCodeAdapterTest {

    @InjectMocks
    private RedisVerificationCodeAdapter redisVerificationCodeAdapter;

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    private final String EMAIL = "test@assetmind.com";
    private final String CODE = "123456";
    private final long TTL = 180L;
    private final String EXPECTED_KEY = "AUTH_CODE:" + EMAIL;

    @Test
    @DisplayName("저장 검증: Key에 Prefix가 붙고, TTL이 설정된 상태로 set()이 호출되어야 한다")
    void givenEmailCodeTTL_whenSave_thenSavedCorrectData() {
        // given
        given(redisTemplate.opsForValue()).willReturn(valueOperations);

        // when
        redisVerificationCodeAdapter.save(EMAIL, CODE, TTL);

        // then
        // verify: 실제로 이 메서드가 호출되었는지 감시
        verify(valueOperations).set(
                eq(EXPECTED_KEY),           // "AUTH_CODE:test@assetmind.com" 인지 확인
                eq(CODE),                   // 코드가 맞는지 확인
                eq(Duration.ofSeconds(TTL)) // Duration 변환이 잘 되었는지 확인
        );
    }

    @Test
    @DisplayName("조회 검증: Prefix가 붙은 Key로 get()을 호출하고 값을 반환해야 한다")
    void givenSavedKey_whenGetCode_thenReturnSavedCode() {
        // given
        given(redisTemplate.opsForValue()).willReturn(valueOperations);
        given(valueOperations.get(EXPECTED_KEY)).willReturn(CODE); // Redis에 값이 있다고 가정

        // when
        String result = redisVerificationCodeAdapter.getCode(EMAIL);

        // then
        assertThat(result).isEqualTo(CODE);
        verify(valueOperations).get(EXPECTED_KEY); // 정확한 키로 조회했는지 확인
    }

    @Test
    @DisplayName("삭제 검증: Prefix가 붙은 Key로 delete()가 호출되어야 한다")
    void givenSavedKey_whenDelete_thenDeleted() {
        // when
        redisVerificationCodeAdapter.remove(EMAIL);

        // then
        verify(redisTemplate).delete(EXPECTED_KEY); // opsForValue()가 아니라 Template 자체의 delete 메서드 검증
    }
}