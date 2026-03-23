package com.assetmind.server_stock.stock.infrastructure.persistence.entity.keys;

import java.io.Serializable;
import java.time.LocalDateTime;

public record OhlcvId (
        String stockCode,
        LocalDateTime candleTimestamp
) implements Serializable {

}
