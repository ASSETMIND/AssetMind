package com.assetmind.server_auth.user.application.port;

import java.util.UUID;

/**
 * 로그인 이후 refreshToken을 저장소를 통해
 * 다루는 일련의 행위들을 추상화하는 인터페이스
 */
public interface RefreshTokenPort {

    /**
     * refreshToken을 저장
     * @param userId - 저장할 때의 Key 값
     * @param refreshToken - 저장되는 Value 값
     * @param ttlSeconds - 유효시간(초)
     */
    void save(UUID userId, String refreshToken, long ttlSeconds);

    /**
     * userId를 통해 저장된 refreshToken을 반환
     * @param userId - Key
     * @return Key에 맞는 저장된 refreshToken
     */
    String getRefreshToken(UUID userId);

    /**
     * userId를 통해 저장된 refreshToken을 삭제
     * @param userId - Key
     */
    void delete(UUID userId);
}
