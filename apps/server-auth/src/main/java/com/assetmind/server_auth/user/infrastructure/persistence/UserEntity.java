package com.assetmind.server_auth.user.infrastructure.persistence;

import com.assetmind.server_auth.user.domain.type.Provider;
import com.assetmind.server_auth.user.domain.type.UserRole;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.LocalDateTime;
import java.util.UUID;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

/**
 * User 도메인의 영속성 정보를 DB에 저장하는 도메인의 엔티티
 */
@Entity
@Table(name = "users", uniqueConstraints = {
        @UniqueConstraint(
                name = "uk_users_social",
                columnNames = {"social_provider", "social_provider_id"}
        )
})
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@EntityListeners(AuditingEntityListener.class)
public class UserEntity {

    @Id
    @Column(columnDefinition = "uuid")
    private UUID id;

    @Column(nullable = false, unique = true)
    private String email;

    @Column(nullable = false)
    private String username;

    @Column(nullable = false)
    private String password;

    @Enumerated(EnumType.STRING)
    @Column(name = "social_provider", nullable = true)
    private Provider socialProvider;

    @Column(name = "social_provider_id", nullable = true)
    private String socialProviderId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private UserRole role;

    @CreatedDate
    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(nullable = false)
    private LocalDateTime updatedAt;

    public UserEntity(UUID id, String email, String username, String password,
            Provider socialProvider, String socialProviderId, UserRole role)
    {
        this.id = id;
        this.email = email;
        this.username = username;
        this.password = password;
        this.socialProvider = socialProvider;
        this.socialProviderId = socialProviderId;
        this.role = role;
    }

}
