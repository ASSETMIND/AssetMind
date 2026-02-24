package com.assetmind.server_auth.user.domain.vo;


import static org.assertj.core.api.Assertions.*;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

/**
 * Email VO 객체 단위 테스트
 * 입력값 유효성 검증 로직 확인
 */
@DisplayName("Email VO 객체 단위 테스트")
class EmailTest {

    @ParameterizedTest
    @ValueSource(strings = {"test@naver.com", "user.name@gmail.co.kr", "123@kakao.com"})
    @DisplayName("성공: 올바른 이메일 형식이면 생성된다.")
    void givenValidEmail_whenNewEmail_thenCreated(String value) {
        // given = @ValueSource

        // when
        Email email = new Email(value);

        // then
        assertThat(email.value()).isEqualTo(value);
    }

    @ParameterizedTest
    @ValueSource(strings = {"invalid-email", "test@", "@gmail.com", "test@.com"})
    @DisplayName("실패: 이메일 형식이 올바르지 않으면 예외가 발생한다.")
    void givenInvalidEmail_whenNewEmail_thenThrowException(String value) {
        // given = @ValueSource

        // when & then
        assertThatThrownBy(() -> new Email(value))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("유효하지 않은 이메일 형식입니다.");
    }
}