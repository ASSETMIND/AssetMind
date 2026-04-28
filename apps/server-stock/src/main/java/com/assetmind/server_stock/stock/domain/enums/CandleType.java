package com.assetmind.server_stock.stock.domain.enums;

import com.assetmind.server_stock.global.error.ErrorCode;
import com.assetmind.server_stock.stock.exception.InvalidStockParameterException;
import lombok.Getter;

@Getter
public enum CandleType {
    MIN_1("1m", 1), // 1분봉
    MIN_3("3m", 3), // 3분봉
    MIN_5("5m", 5), // 5분봉
    MIN_15("15m", 15), // 15분봉
    DAY_1("1d", 1440), // 1일봉
    DAY_3("3d", 4320), // 3일봉
    DAY_5("5d", 7200), // 5일봉

    WEEK_1("1w", 0),  // 주봉
    MONTH_1("1M", 0), // 월봉
    YEAR_1("1y", 0); // 년봉

    private final String value;
    private final int windowMinutes;

    CandleType(String value, int windowMinutes) {
        this.value = value;
        this.windowMinutes = windowMinutes;
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
