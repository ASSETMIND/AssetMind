package com.assetmind.server_auth.user.infrastructure.persistence;

import com.assetmind.server_auth.user.domain.User;
import com.assetmind.server_auth.user.domain.port.UserRepository;
import com.assetmind.server_auth.user.domain.vo.SocialID;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

/**
 * Spring Data JPA를 사용하여 Domain 영역에서 정의한 UserRepository 구현체
 */
@Repository
@RequiredArgsConstructor
public class UserRepositoryImpl implements UserRepository {

    private final UserJpaRepository jpaRepository;
    private final UserEntityMapper mapper;

    @Override
    public User save(User user) {
        UserEntity entity = mapper.toEntity(user);
        UserEntity savedEntity = jpaRepository.save(entity);

        return mapper.toDomain(savedEntity);
    }

    @Override
    public Optional<User> findById(UUID id) {
        return jpaRepository.findById(id)
                .map(mapper::toDomain);
    }

    @Override
    public Optional<User> findBySocialId(SocialID socialId) {
        return jpaRepository.findBySocialId(socialId.provider(), socialId.providerID())
                .map(mapper::toDomain);
    }
}
