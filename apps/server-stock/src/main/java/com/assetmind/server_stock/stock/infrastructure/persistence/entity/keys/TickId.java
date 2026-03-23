package com.assetmind.server_stock.stock.infrastructure.persistence.entity.keys;

import java.io.Serializable;
import java.time.LocalDateTime;

public record TickId(String stockCode, LocalDateTime tradeTimestamp) implements Serializable {
}
