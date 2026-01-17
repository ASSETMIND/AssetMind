package com.assetmind.server_auth.user.infrastructure.persistence;

import com.assetmind.server_auth.user.domain.type.Provider;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/**
 * Spring Data JPA를 Repository 구현체에서 사용하기 위한 인터페이스 정의
 */
public interface UserJpaRepository extends JpaRepository<UserEntity, UUID> {

    @Query("SELECT u "
            + "FROM UserEntity u "
            + "WHERE u.socialProvider = :provider AND u.socialProviderId = :provider_id")
    Optional<UserEntity> findBySocialId(
            @Param("provider") Provider provider,
            @Param("provider_id") String providerId
    );
}
