package com.assetmind.server_stock.stock.domain.enums;

import com.assetmind.server_stock.global.error.ErrorCode;
import com.assetmind.server_stock.stock.exception.InvalidStockParameterException;
import lombok.Getter;

@Getter
public enum CandleType {
    MIN_1("1m");

    private final String value;

    CandleType(String value) {
        this.value = value;
    }

    public static CandleType from(String value) {
        for (CandleType type : values()) {
            if (type.getValue().equals(value)) {
                return type;
            }
        }
        throw new InvalidStockParameterException("지원하지 않는 캔들 타입입니다.:" + value, ErrorCode.INVALID_STOCK_PARAMETER);
    }
}
