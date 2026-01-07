package com.assetmind.auth.security.jwt;

import java.util.List;

public interface JwtTokenProvider {

    String createAccessToken(Long userId, List<String> roles);

    String createRefreshToken(Long userId);

    boolean validateToken(String token);

    Long getUserId(String token);

    List<String> getRoles(String token);
}