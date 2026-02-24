package com.assetmind.server_auth.user.application.dto;

public record UserLoginCommand(
        String email,
        String password
) {

}
