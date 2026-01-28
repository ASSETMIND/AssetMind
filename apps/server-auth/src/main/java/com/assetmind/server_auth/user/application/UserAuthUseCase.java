package com.assetmind.server_auth.user.application;

import com.assetmind.server_auth.user.application.dto.TokenSetDto;
import com.assetmind.server_auth.user.application.dto.UserLoginCommand;
import java.util.UUID;

/**
 * 유저 인증 관련된
 * 로그인/로그아웃을 추상화한 인터페이스
 */
public interface UserAuthUseCase {

    /**
     * 유저 로그인
     * @param cmd - 로그인 정보(이메일, 비밀번호)
     * @return accessToken
     */
    TokenSetDto login(UserLoginCommand cmd);

    /**
     * 유저 로그아웃
     * @param userId - 로그아웃할 유저의 ID
     */
    void logout(UUID userId);
}
