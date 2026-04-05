-- 레거시 테이블(stock_data) 삭제
DROP TABLE IF EXISTS stock_data;

-- 종목 메타 데이터 테이블 생성
CREATE TABLE IF NOT EXISTS stock_meta_data (
    stock_code VARCHAR(20) PRIMARY KEY,
    stock_name VARCHAR(100) NOT NULL,
    market VARCHAR(50)
);

-- 실시간 체결 데이터 파티셔닝 테이블(부모 테이블) 생성
CREATE TABLE raw_tick (
    id BIGSERIAL,
    stock_code VARCHAR(20) NOT NULL,
    current_price DOUBLE PRECISION NOT NULL,
    price_change DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL,
    trade_timestamp TIMESTAMP NOT NULL,

    PRIMARY KEY (id, trade_timestamp)
) PARTITION BY RANGE (trade_timestamp);

CREATE INDEX idx_raw_tick_stock_time ON raw_tick (stock_code, trade_timestamp DESC);

-- 테스트용 더미 파티셔닝 테이블
CREATE TABLE raw_tick_20260320 PARTITION OF raw_tick
    FOR VALUES FROM ('2026-03-20 00:00:00+09') TO ('2026-03-21 00:00:00+09');

-- 차트 생성에 필요한 OHLCV(시가, 고가, 저가, 종가, 거래량) 캔들 테이블 생성
-- 1분봉 테이블
CREATE TABLE ohlcv_1m (
    stock_code VARCHAR(20) NOT NULL,
    candle_timestamp TIMESTAMPTZ NOT NULL,
    open_price INTEGER NOT NULL,
    high_price INTEGER NOT NULL,
    low_price INTEGER NOT NULL,
    close_price INTEGER NOT NULL,
    volume BIGINT NOT NULL,
    PRIMARY KEY (stock_code, candle_timestamp)
);
-- 1분봉 최신순 조회를 위한 인덱스
CREATE INDEX idx_ohlcv_1m_lookup ON ohlcv_1m (stock_code, candle_timestamp DESC);

-- 일봉 테이블
CREATE TABLE ohlcv_1d (
    stock_code VARCHAR(20) NOT NULL,
    candle_timestamp TIMESTAMPTZ NOT NULL,
    open_price INTEGER NOT NULL,
    high_price INTEGER NOT NULL,
    low_price INTEGER NOT NULL,
    close_price INTEGER NOT NULL,
    volume BIGINT NOT NULL,
    PRIMARY KEY (stock_code, candle_timestamp)
);
-- 1일봉 최신순 조회를 위한 인덱스
CREATE INDEX idx_ohlcv_1d_lookup ON ohlcv_1d (stock_code, candle_timestamp DESC);