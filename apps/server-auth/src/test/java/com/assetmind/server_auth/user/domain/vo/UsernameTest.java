package com.assetmind.server_auth.user.domain.vo;

import static org.assertj.core.api.Assertions.*;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

/**
 * Username VO 객체 단위 테스트
 * 입력값 유효성 검증 로직 확인
 */
@DisplayName("Username VO 객체 단위 테스트")
class UsernameTest {

    @ParameterizedTest
    @ValueSource(strings = {"테슽", "테스트123", "이글자는15글자허용테스트입니"})
    @DisplayName("성공: 올바른 유저 이름 형식이면 생성된다.")
    void givenValidUsername_whenNewUsername_thenCreated(String value) {
        // given = @ValueSource

        // when
        Username username = new Username(value);

        // then
        assertThat(username.value()).isEqualTo(value);
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {" ", "테", "이글자는16글자실패테스트입니다"})
    @DisplayName("실패: 2글자 미만 15글자 초과 유저 이름은 예외가 발생한다.")
    void givenInvalidUsername_whenNewUsername_thenThrowException(String value) {
        // given = @ValueSource

        // when & then
        assertThatThrownBy(() -> new Username(value))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("유저 이름은 2자 이상 15자 이하여야 합니다.");
    }
}