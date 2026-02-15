package com.assetmind.server_auth.user.exception;

import com.assetmind.server_auth.global.error.BusinessException;
import com.assetmind.server_auth.global.error.ErrorCode;

public class InvalidVerificationCode extends BusinessException {

    public InvalidVerificationCode() {
        super(ErrorCode.INVALID_VERIFICATION_CODE);
    }
}
