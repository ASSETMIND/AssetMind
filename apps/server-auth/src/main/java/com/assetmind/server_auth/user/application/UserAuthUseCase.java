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
     * @return 토큰 세트(accessToken, refreshToken)
     */
    TokenSetDto login(UserLoginCommand cmd);

    /**
     * 유저 로그아웃
     * @param userId - 로그아웃할 유저의 ID
     */
    void logout(UUID userId);

    /**
     * 토큰 재발급
     * 보안을 한 층 더 강화하기 위해 재발급 시
     * AccessToken, RefreshToken 둘 다 재발급 (RTR 전략)
     * @param refreshToken - 재발급 받기위한 토큰
     * @return 토큰 세트(accessToken, refreshToken)
     */
    TokenSetDto reissueToken(String refreshToken);
}
