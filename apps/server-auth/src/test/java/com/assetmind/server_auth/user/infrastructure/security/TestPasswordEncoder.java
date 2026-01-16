package com.assetmind.server_auth.user.infrastructure.security;

import com.assetmind.server_auth.user.domain.port.PasswordEncoder;

public class TestPasswordEncoder implements PasswordEncoder {

    private final static String PREFIX = "ENCODE";

    @Override
    public String encode(String rawPassword) {
        if (rawPassword == null) return null;
        return PREFIX + rawPassword;
    }

    @Override
    public boolean matches(String rawPassword, String encodedPassword) {
        if (rawPassword == null || encodedPassword == null) return false;
        return encodedPassword.equals(PREFIX + rawPassword);
    }
}
