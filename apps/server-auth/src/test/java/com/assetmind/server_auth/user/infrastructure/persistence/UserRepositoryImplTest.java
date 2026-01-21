package com.assetmind.server_auth.user.infrastructure.persistence;

import static org.assertj.core.api.Assertions.*;


import com.assetmind.server_auth.global.config.JpaConfig;
import com.assetmind.server_auth.user.domain.User;
import com.assetmind.server_auth.user.domain.type.Provider;
import com.assetmind.server_auth.user.domain.type.UserRole;
import com.assetmind.server_auth.user.domain.vo.Email;
import com.assetmind.server_auth.user.domain.vo.Password;
import com.assetmind.server_auth.user.domain.vo.SocialID;
import com.assetmind.server_auth.user.domain.vo.UserInfo;
import com.assetmind.server_auth.user.domain.vo.Username;
import com.assetmind.server_auth.user.infrastructure.persistence.jpa.UserEntityMapper;
import com.assetmind.server_auth.user.infrastructure.persistence.jpa.UserRepositoryImpl;
import java.util.Optional;
import java.util.UUID;
import org.hibernate.exception.ConstraintViolationException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.context.annotation.Import;

/**
 * JPA를 이용한 UserRepository의 구현체가
 * 잘 저장하고 잘 조회되는지 검증
 */
@DataJpaTest
@Import({UserRepositoryImpl.class, UserEntityMapper.class, JpaConfig.class}) // 컴포넌트 스캔대상에 해당 모듈들을 포함
class UserRepositoryImplTest {

    @Autowired
    private UserRepositoryImpl userRepository;

    @Autowired
    private TestEntityManager em;

    private User createTestUser(UUID id, String email, String username, String rawPassword, Provider provider, String providerId, UserRole role) {
        return User.withId(
                id,
                new UserInfo(new Email(email), new Username(username)),
                new Password(rawPassword),
                new SocialID(provider, providerId),
                role
        );
    }

    @Nested
    @DisplayName("User 저장 (save)")
    class Save {
        @Test
        @DisplayName("성공: 소셜 정보가 없는 User를 저장할 때 Nullable가 정상 작동하고, Domain의 정보가 Entity로 매핑된 후 저장된다.")
        void givenGuestRoleUser_whenSave_thenSaved() {
            // given
            UUID uuid = UUID.randomUUID();
            User testUser = createTestUser(uuid, "test@test.com", "테스트001", "test1234",
                    null, null, UserRole.GUEST);

            // when
            User result = userRepository.save(testUser);

            // then
            assertThat(result.getId()).isEqualTo(testUser.getId());
            assertThat(result.getSocialID()).isNull();
        }

        @Test
        @DisplayName("성공: 소셜 정보가 있는 User를 저장할 때 모든 Domain의 정보가 Entity로 매핑된 후 저장된다.")
        void givenUserRoleUser_whenSave_thenSaved() {
            // given
            UUID uuid = UUID.randomUUID();
            User testUser = createTestUser(uuid, "test@test.com", "테스트001", "test1234",
                    Provider.GOOGLE, "google-123", UserRole.USER);

            // when
            User result = userRepository.save(testUser);

            // then
            assertThat(result.getId()).isEqualTo(testUser.getId());
            assertThat(result.getSocialID()).isNotNull();
            assertThat(result.getUserRole()).isEqualTo(UserRole.USER);
        }

        @Test
        @DisplayName("실패: User를 저장할 때 중복된 이메일이면 저장 실패한다.")
        void givenDuplicatedEmailUser_whenSave_thenThrowException() {
            // given
            String email = "dup@test.com";
            User savedUser = createTestUser(UUID.randomUUID(), email, "테스트001", "test1234", null,
                    null, UserRole.GUEST);
            userRepository.save(savedUser);
            em.flush();
            em.clear();

            User duplicatedUser = createTestUser(UUID.randomUUID(), email, "테스트001", "test1234", null,
                    null, UserRole.GUEST);

            // when & then
            assertThatThrownBy(() -> {
                userRepository.save(duplicatedUser);
                em.flush();
            })
                    .isInstanceOf(ConstraintViolationException.class);
        }

        @Test
        @DisplayName("실패: User를 저장할 때 이미 존재하는 소셜 계정(Provider + ID)이면 저장 실패한다.")
        void givenAlreadySocialUser_whenSave_thenThrowException() {
            // given
            SocialID alreadySocialId = new SocialID(Provider.KAKAO, "kakao-1234");
            User savedUser = createTestUser(UUID.randomUUID(), "test01@test.com", "테스트001", "test1234",
                    alreadySocialId.provider(), alreadySocialId.providerID(), UserRole.USER);
            userRepository.save(savedUser);
            em.flush();
            em.clear();

            User duplicatedUser = createTestUser(UUID.randomUUID(), "test02@test.com", "테스트002", "test1234",
                    alreadySocialId.provider(), alreadySocialId.providerID(), UserRole.USER);

            // when & then
            assertThatThrownBy(() -> {
                userRepository.save(duplicatedUser);
                em.flush();
            })
                    .isInstanceOf(ConstraintViolationException.class);
        }
    }

    @Nested
    @DisplayName("UUID를 통해 User 조회 (findById)")
    class FindById {
        @Test
        @DisplayName("성공: 저장된 User를 ID(UUID)로 성공적으로 조회한다.")
        void givenValidUserId_whenFindById_thenReturnSavedUser() {
            // given
            UUID uuid = UUID.randomUUID();
            User testUser = createTestUser(uuid, "test@test.com", "테스트001", "test1234",
                    Provider.GOOGLE, "google-123", UserRole.USER);
            userRepository.save(testUser);

            // when
            Optional<User> found = userRepository.findById(uuid);

            // then
            assertThat(found).isPresent();
            assertThat(found.get().getId()).isEqualTo(testUser.getId());
            assertThat(found.get().getUsernameValue()).isEqualTo(testUser.getUsernameValue());
        }

        @Test
        @DisplayName("실패: 저장된 User를 잘못된 ID(UUID)로 조회하면 빈 객체를 반환한다.")
        void givenInvalidUserId_whenFindById_thenReturnEmpty() {
            // given
            UUID invalidUuid = UUID.randomUUID();

            // when
            Optional<User> found = userRepository.findById(invalidUuid);

            // then
            assertThat(found).isEmpty();
        }
    }

    @Nested
    @DisplayName("SocialId(provider + providerId)를 통해 User 조회 (findBySocialId)")
    class FindBySocialId {
        @Test
        @DisplayName("성공: 저장된 User를 Social 정보로 성공적으로 조회한다.")
        void givenValidSocialId_whenFindBySocialId_thenReturnSavedUser() {
            // given
            UUID uuid = UUID.randomUUID();
            SocialID socialId = new SocialID(Provider.KAKAO, "kakao-1234");
            User testUser = createTestUser(uuid, "test@test.com", "테스트001", "test1234",
                    socialId.provider(), socialId.providerID(), UserRole.USER);
            userRepository.save(testUser);

            // when
            Optional<User> found = userRepository.findBySocialId(socialId);

            // then
            assertThat(found).isPresent();
            assertThat(found.get().getId()).isEqualTo(testUser.getId());
            assertThat(found.get().getUsernameValue()).isEqualTo(testUser.getUsernameValue());
            assertThat(found.get().getSocialID()).isEqualTo(socialId);
        }

        @Test
        @DisplayName("실패: 저장된 User를 잘못된 Social 정보로 조화하면 빈 객체를 반환한다.")
        void givenInvalidSocialId_whenFindBySocialId_thenReturnEmpty() {
            // given
            SocialID invalidSocialId = new SocialID(Provider.KAKAO, "kakao-1234");
            User testUser = createTestUser(UUID.randomUUID(), "test@test.com", "테스트001", "test1234",
                    Provider.GOOGLE, "google-123", UserRole.USER);
            userRepository.save(testUser);

            // when
            Optional<User> found = userRepository.findBySocialId(invalidSocialId);

            // then
            assertThat(found).isEmpty();
        }
    }
}