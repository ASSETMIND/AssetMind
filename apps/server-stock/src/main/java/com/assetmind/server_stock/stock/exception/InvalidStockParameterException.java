package com.assetmind.server_stock.stock.exception;

import com.assetmind.server_stock.global.error.BusinessException;
import com.assetmind.server_stock.global.error.ErrorCode;

public class InvalidStockParameterException extends BusinessException {

    public InvalidStockParameterException(ErrorCode errorCode) {
        super(errorCode);
    }
}
