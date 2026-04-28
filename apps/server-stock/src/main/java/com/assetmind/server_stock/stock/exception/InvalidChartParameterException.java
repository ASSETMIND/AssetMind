package com.assetmind.server_stock.stock.exception;

import com.assetmind.server_stock.global.error.BusinessException;
import com.assetmind.server_stock.global.error.ErrorCode;

public class InvalidChartParameterException extends BusinessException {
    public InvalidChartParameterException(ErrorCode errorCode, String message) {
        super(message, errorCode);
    }
}
