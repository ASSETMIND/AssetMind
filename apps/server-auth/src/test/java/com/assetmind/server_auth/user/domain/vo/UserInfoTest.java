package com.assetmind.server_auth.user.domain.vo;

import static org.assertj.core.api.Assertions.*;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * UserInfo VO 객체 단위 테스트
 * 입력값 유효성 검증 로직 테스트
 */
@DisplayName("UserInfo VO 객체 단위 테스트")
class UserInfoTest {

    @Test
    @DisplayName("성공: 유효한 Email, Username이 주어지면 객체가 생성된다.")
    void givenValidEmailAndUsername_whenNewUserInfo_thenCreated() {
        // given
        Email email = new Email("test@kakao.com");
        Username username = new Username("이재석동동동");

        // when
        UserInfo userInfo = new UserInfo(email, username);

        // then
        assertThat(userInfo.email()).isEqualTo(email);
        assertThat(userInfo.username()).isEqualTo(username);
    }

    @Test
    @DisplayName("실패: Email, Username이 null이면 예외가 발생한다.")
    void givenInValidEmailAndUsername_whenNewUserInfo_thenThrowException() {
        // given & when & then
        assertThatThrownBy(() -> new UserInfo(null, null))
                .isInstanceOf(NullPointerException.class);
    }
}