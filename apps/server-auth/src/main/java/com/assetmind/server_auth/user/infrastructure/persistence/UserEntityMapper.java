package com.assetmind.server_auth.user.infrastructure.persistence;

import com.assetmind.server_auth.user.domain.User;
import com.assetmind.server_auth.user.domain.type.Provider;
import com.assetmind.server_auth.user.domain.vo.Email;
import com.assetmind.server_auth.user.domain.vo.Password;
import com.assetmind.server_auth.user.domain.vo.SocialID;
import com.assetmind.server_auth.user.domain.vo.UserInfo;
import com.assetmind.server_auth.user.domain.vo.Username;
import org.springframework.stereotype.Component;

/**
 * Domain(User) <-> Entity(UserEntity) 변환 매퍼
 */
@Component
public class UserEntityMapper {

    public UserEntity toEntity(User user) {
        Provider provider = (user.getSocialID().provider() != null) ? user.getSocialID().provider() : null;
        String socialId = (user.getSocialID().providerID() != null) ? user.getSocialID().providerID() : null;

        return new UserEntity(
                user.getId(),
                user.getEmailValue(),
                user.getUsernameValue(),
                user.getPasswordValue(),
                provider,
                socialId,
                user.getUserRole()
        );
    }

    public User toDomain(UserEntity userEntity) {
        UserInfo userInfo = new UserInfo(new Email(userEntity.getEmail()),
                new Username(userEntity.getUsername()));

        Password password = new Password(userEntity.getPassword());

        SocialID socialID = null;
        if (userEntity.getSocialProvider() != null && userEntity.getSocialProviderId() != null) {
            socialID = new SocialID(userEntity.getSocialProvider(), userEntity.getSocialProviderId());
        }

        return User.withId(
                userEntity.getId(),
                userInfo,
                password,
                socialID,
                userEntity.getRole()
        );
    }
}
