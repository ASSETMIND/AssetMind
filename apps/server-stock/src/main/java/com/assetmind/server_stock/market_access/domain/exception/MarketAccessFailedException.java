package com.assetmind.server_stock.market_access.domain.exception;

public class MarketAccessFailedException extends RuntimeException {

    public MarketAccessFailedException(String message) {
        super(message);
    }

    public MarketAccessFailedException(String message, Throwable cause) {
        super(message, cause);
    }
}
