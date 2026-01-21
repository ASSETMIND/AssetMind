package com.assetmind.server_auth.user.exception;

import com.assetmind.server_auth.global.error.BusinessException;
import com.assetmind.server_auth.global.error.ErrorCode;

public class InvalidSignUpTokenException extends BusinessException {

    public InvalidSignUpTokenException() {
        super(ErrorCode.INVALID_SIGN_UP_TOKEN);
    }
}
