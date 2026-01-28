package com.assetmind.server_auth.user.application.dto;

public record TokenSetDto(
        String accessToken,
        String refreshToken,
        long  refreshTokenExpire
) {

}
