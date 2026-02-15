package com.assetmind.server_auth.user.exception;

import com.assetmind.server_auth.global.error.BusinessException;
import com.assetmind.server_auth.global.error.ErrorCode;

public class UserDuplicatedEmail extends BusinessException {

    public UserDuplicatedEmail() {
        super(ErrorCode.USER_DUPLICATED_EMAIL);
    }
}
