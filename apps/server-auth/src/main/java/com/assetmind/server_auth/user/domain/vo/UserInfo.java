package com.assetmind.server_auth.user.domain.vo;

import java.util.Objects;

/**
 * 유저의 정보를 담은 VO 객체
 * @param email - 유저 이름
 * @param username - 유저 이메일
 */
public record UserInfo(
        Email email,
        Username username
) {

    /**
     * 유저를 생성할 때 들어온 유저의 정보 값이 null인지 확인
     * @param email
     * @param username
     */
    public UserInfo {
        Objects.requireNonNull(email);
        Objects.requireNonNull(username);
    }

    @Override
    public boolean equals(Object o) {
        if (!(o instanceof UserInfo userInfo)) {
            return false;
        }
        return Objects.equals(email, userInfo.email) && Objects.equals(username,
                userInfo.username);
    }

    @Override
    public int hashCode() {
        return Objects.hash(email, username);
    }
}
