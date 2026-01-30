package com.assetmind.server_auth.user.presentation.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record LoginResponse(
        @JsonProperty("access_token")
        String accessToken
) {

}
