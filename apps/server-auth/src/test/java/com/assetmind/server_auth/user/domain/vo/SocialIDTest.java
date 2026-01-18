package com.assetmind.server_auth.user.domain.vo;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_auth.user.domain.type.Provider;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;

/**
 * SocailID VO 객체 단위 테스트
 * 입력값 유효성 검증 로직 확인
 */
class SocialIDTest {

    @Test
    @DisplayName("성공: 올바른 Provider와 ProviderID가 주어지면 정상적으로 객체를 생성한다.")
    void givenValidSocialInfo_whenNewSocialID_thenCreated() {
        // given
        Provider provider = Provider.GOOGLE;
        String providerId = "testID1234";

        // when
        SocialID socialID = new SocialID(provider, providerId);

        // then
        assertThat(socialID.provider()).isEqualTo(provider);
        assertThat(socialID.providerID()).isEqualTo(providerId);
    }

    @Test
    @DisplayName("실패: Provider가 null이면 예외가 발생한다.")
    void givenInvalidProvider_whenNewSocialID_thenThrowException() {
        // given
        Provider provider = null;
        String providerId = "testID1234";

        // when & then
        assertThatThrownBy(() -> new SocialID(provider, providerId))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("소셜 로그인 제공자는 필수 입니다.");
    }

    @ParameterizedTest
    @NullAndEmptySource
    @DisplayName("실패: ProviderId가 null이거나 공백이면 예외가 발생한다.")
    void givenInvalidProviderId_whenNewSocialID_thenThrowException(String providerId) {
        // given = @NullAndEmptySource

        // when & then
        assertThatThrownBy(() -> new SocialID(Provider.GOOGLE, providerId))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("소셜 로그인 식별값은 필수 입니다.");
    }

    @Test
    @DisplayName("성공: toString()이 지정된 포맷(Provider : ProviderId)로 출력된다.")
    void givenSocialID_whenToString_thenValidFormat() {
        // given
        SocialID socialID = new SocialID(Provider.GOOGLE, "testID1234");

        // when
        String format = socialID.toString();

        // then
        assertThat(format).isEqualTo("GOOGLE : testID1234");
    }

}