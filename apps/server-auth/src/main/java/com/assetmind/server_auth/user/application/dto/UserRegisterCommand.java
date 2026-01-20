package com.assetmind.server_auth.user.application.dto;

public record UserRegisterCommand(
        String email,
        String password,
        String username,
        String signUpToken
) {

}
