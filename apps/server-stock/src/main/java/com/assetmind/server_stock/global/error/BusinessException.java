package com.assetmind.server_stock.global.error;

import lombok.Getter;

@Getter
public class BusinessException extends RuntimeException {
    private ErrorCode errorCode;
    private String message;

    public BusinessException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.errorCode = errorCode;
    }

    public BusinessException(String message, ErrorCode errorCode) {
        this.message = message;
        this.errorCode = errorCode;
    }
}
