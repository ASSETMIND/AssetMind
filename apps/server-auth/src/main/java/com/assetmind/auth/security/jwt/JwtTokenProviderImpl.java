package com.assetmind.auth.security.jwt;

import java.util.List;

public class JwtTokenProviderImpl implements JwtTokenProvider {

    @Override
    public String createAccessToken(Long userId, List<String> roles) {
        return null;
    }

    @Override
    public String createRefreshToken(Long userId) {
        return null;
    }

    @Override
    public boolean validateToken(String token) {
        return false;
    }

    @Override
    public Long getUserId(String token) {
        return null;
    }

    @Override
    public List<String> getRoles(String token) {
        return null;
    }
}