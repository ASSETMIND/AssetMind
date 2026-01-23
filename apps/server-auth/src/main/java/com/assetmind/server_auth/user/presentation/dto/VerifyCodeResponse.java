package com.assetmind.server_auth.user.presentation.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record VerifyCodeResponse(
        @JsonProperty("sign_up_token")
        String signUpToken
) {

}
