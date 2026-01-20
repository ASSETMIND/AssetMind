package com.assetmind.server_auth.user.domain.vo;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_auth.user.application.port.PasswordEncoder;
import com.assetmind.server_auth.user.infrastructure.security.TestPasswordEncoder;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;

/**
 * Password VO 객체 단위 테스트
 * 입력값 유효성 검증 로직 확인
 * 비밀번호 암호화 로직 확인
 */
class PasswordTest {

    private final PasswordEncoder encoder = new TestPasswordEncoder();

    @Test
    @DisplayName("성공: 평문 비밀번호를 암호화하여 생성한다.")
    void givenRawPassword_whenCreate_thenCreated() {
        // given
        String rawPassword = "testPassword1234";

        // when
        Password password = Password.from(encoder.encode(rawPassword));

        // then
        assertThat(password.value()).isEqualTo("ENCODE" + rawPassword); // 암호화 확인
        assertThat(password.value()).isNotEqualTo(rawPassword); // 평문 노출 금지 확인
    }

    @ParameterizedTest
    @NullAndEmptySource
    @DisplayName("실패: 비밀번호가 null이나 빈 값이라면 예외가 발생한다.")
    void givenInvalidRawPassword_whenCreate_thenThrowException(String invalidPassword) {
        assertThatThrownBy(() -> Password.from(invalidPassword))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("비밀번호는 필수");
    }

}