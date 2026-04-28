package com.assetmind.server_stock.stock.domain.dtos;

import java.time.LocalDateTime;

/**
 * {@link com.assetmind.server_stock.stock.domain.repository.CandleRepository}에서
 * 1분봉, 1일봉 모두 유연하게 다루기 위한 특정 JPA Entity에 종속되지 않는 공통 DTO
 */
public record OhlcvDto(
        String stockCode,
        LocalDateTime candleTimestamp,
        Double openPrice,
        Double highPrice,
        Double lowPrice,
        Double closePrice,
        Long volume
) {

}
