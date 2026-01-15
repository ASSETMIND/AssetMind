package com.assetmind.server_auth.user.domain;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_auth.global.error.BusinessException;
import com.assetmind.server_auth.global.error.ErrorCode;
import com.assetmind.server_auth.user.domain.port.UserIdGenerator;
import com.assetmind.server_auth.user.domain.type.Provider;
import com.assetmind.server_auth.user.domain.type.UserRole;
import com.assetmind.server_auth.user.domain.vo.Email;
import com.assetmind.server_auth.user.domain.vo.SocialID;
import com.assetmind.server_auth.user.domain.vo.UserInfo;
import com.assetmind.server_auth.user.domain.vo.Username;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/**
 * User domain 단위 테스트 작성
 * 입력값 유효성 검증 로직 확인
 * 비즈니스 로직 확인
 */
class UserTest {

    // 테스트용 더미 데이터 준비
    private final Email validEmail = new Email("test@email.com");
    private final Username validUsername = new Username("이재석동동동");
    private final UserInfo validUserInfo = new UserInfo(new Email("test@email.com"), new Username("이재석동동동"));
    private final SocialID validSocialID = new SocialID(Provider.KAKAO, "testID1234");

    // ID 생성기 Stub (고정된 UUID 반환)
    private final UUID FIXED_UUID = UUID.fromString("dea7b2fb-e7ac-4c45-86cb-9e0e5cd81e93");
    private final UserIdGenerator idGenerator = () -> FIXED_UUID;

    @Nested
    @DisplayName("신규 유저 생성 (createGuest)")
    class CreateGuest {

        @Test
        @DisplayName("성공: 유효한 정보로 GUEST 유저를 생성한다.")
        void givenValidInfo_whenCreateGuest_thenCreated() {
            // when
            User user = User.createGuest(validUserInfo, validSocialID, idGenerator);

            // then
            assertThat(user.getId()).isEqualTo(FIXED_UUID);
            assertThat(user.getUserRole()).isEqualTo(UserRole.GUEST);
            assertThat(user.getSocialID()).isEqualTo(validSocialID);
            assertThat(user.getUserInfo().email()).isEqualTo(validEmail);
            assertThat(user.getUserInfo().username()).isEqualTo(validUsername);
        }

        @Test
        @DisplayName("실패: 필수 정보(UserInfo)가 없으면 생성할 수 없다.")
        void givenNullUserInfo_whenCreateGuest_thenThrowException() {
            // when & then
            assertThatThrownBy(() -> User.createGuest(null, validSocialID, idGenerator))
                    .isInstanceOf(NullPointerException.class);
        }

        @Test
        @DisplayName("실패: 필수 정보(SocialID)가 없으면 생성할 수 없다.")
        void givenNullSocialID_whenCreateGuest_thenThrowException() {
            // when & then
            assertThatThrownBy(() -> User.createGuest(validUserInfo, null, idGenerator))
                    .isInstanceOf(NullPointerException.class);
        }
    }

    @Nested
    @DisplayName("회원 등급 업그레이드 (upgradeToRoleUser)")
    class UpgradeRole {

        @Test
        @DisplayName("성공: GUEST 상태인 유저가 USER로 승격된다.")
        void givenGuestRoleUser_whenUpgradeRole_thenUpgradeToUser() {
            // given
            User guestUser = User.createGuest(validUserInfo, validSocialID, idGenerator);

            // when
            guestUser.upgradeToRoleUser();

            // then
            assertThat(guestUser.getUserRole()).isEqualTo(UserRole.USER);
        }

        @Test
        @DisplayName("실패: 이미 USER인 경우 BusinessException이 발생한다.")
        void givenUserRoleUser_whenUpgradeRole_thenThrowException() {
            // given
            User user = User.createGuest(validUserInfo, validSocialID, idGenerator);
            user.upgradeToRoleUser(); // 먼저 USER(정회원)으로 상태 변경

            // when & then
            assertThatThrownBy(user::upgradeToRoleUser)
                    .isInstanceOf(BusinessException.class)
                    .extracting("errorCode")
                    .isEqualTo(ErrorCode.ALREADY_GET_USER_PERMISSION);
        }
    }

    @Test
    @DisplayName("성공: DB에 저장된 ID와 상태를 그대로 복원한다.")
    void givenStoredUserId_whenWithId_thenGetValidUser() {
        // given
        // db에 해당 dbId로 저장되었다고 가정
        UUID dbId = UUID.randomUUID();
        UserRole dbRole = UserRole.USER;

        // when
        User restoredUser = User.withId(dbId, validUserInfo, validSocialID, dbRole);

        // then
        assertThat(restoredUser.getId()).isEqualTo(dbId); // ID가 새로 생성되지 않고 유지됨
        assertThat(restoredUser.getUserRole()).isEqualTo(UserRole.USER);
    }
}