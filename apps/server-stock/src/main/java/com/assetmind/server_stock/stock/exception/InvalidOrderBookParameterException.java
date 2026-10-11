package com.assetmind.server_stock.stock.exception;

import com.assetmind.server_stock.global.error.BusinessException;
import com.assetmind.server_stock.global.error.ErrorCode;

public class InvalidOrderBookParameterException extends BusinessException {

    public InvalidOrderBookParameterException(ErrorCode errorCode) {
        super(errorCode);
    }

    public InvalidOrderBookParameterException(String message, ErrorCode errorCode) {
        super(message, errorCode);
    }
}
