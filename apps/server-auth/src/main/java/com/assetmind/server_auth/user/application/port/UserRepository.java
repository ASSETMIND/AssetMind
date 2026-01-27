package com.assetmind.server_auth.user.application.port;

import com.assetmind.server_auth.user.domain.User;
import com.assetmind.server_auth.user.domain.vo.SocialID;
import java.util.Optional;
import java.util.UUID;

/**
 * User 도메인 객체 저장소의 행동을 정의
 * 해당 인터페이스를 통해 User 도메인 객체의 데이터를 저장하고 조회
 * 구체적인 구현은 Infrastructure 계층에서 담당
 */
public interface UserRepository {

    /**
     * User를 저장하거나 수정
     * @param user - 저장할 User 도메인 객체
     * @return 저장 및 수정된 User 도메인 객체
     */
    User save(User user);

    /**
     * User 도메인 객체를 DB에서 UUID로 조회
     * @param id - User 도메인 객체의 식별자
     * @return User 도메인 객체
     */
    Optional<User> findById(UUID id);

    /**
     * User 도메인 객체를 DB에서 소셜 정보로 조회
     * 추후의 Provider(카카오/구글 ..) 이메일이 변경되어도 ProviderID는 변하지 않으므로
     * Provider와 ProviderID의 조합으로 User 도메인 객체를 조회
     * @param socialId - User 도메인 객체의 소셜 정보(Provider + ProviderID)
     * @return User 도메인 객체
     */
    Optional<User> findBySocialId(SocialID socialId);

    /**
     * DB에 해당 이메일이 존재하는지 조회
     * @param email - 찾으려는 email
     * @return true(존재 o) / false(존재 x)
     */
    boolean existsByEmail(String email);

    /**
     * User 도메인 객체를 DB에서 Email로 조회
     * @param email - User 도메인 객체의 email
     * @return Ussr 도메인 객체
     */
    Optional<User> findByEmail(String email);
}
