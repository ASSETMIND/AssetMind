package com.assetmind.server_stock.stock.infrastructure.persistence.common.keys;

import java.io.Serializable;
import java.time.LocalDateTime;

public record TickId(String stockCode, LocalDateTime tradeTimestamp) implements Serializable {
}
