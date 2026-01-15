package com.assetmind.server_auth.user.domain.vo;

import com.assetmind.server_auth.user.domain.type.Provider;

/**
 * 소셜 로그인 식별자 정보
 * @param provider - 소셜 로그인 제공하는 곳
 * @param providerID - 식별 ID
 */
public record SocialID(
        Provider provider,
        String providerID
) {
    public SocialID {
        if (provider == null) {
            throw new IllegalArgumentException("소셜 로그인 제공자는 필수 입니다.");
        }

        if (providerID == null || providerID.isBlank()) {
            throw new IllegalArgumentException("소셜 로그인 식별값은 필수 입니다.");
        }
    }

    @Override
    public String toString() {
        return provider.toString() + " : " + providerID;
    }
}
