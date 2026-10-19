-- scripts/init_warehouse.sql

-- 1. Tạo 3 schema kiến trúc Medallion
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- 2. Tạo sẵn bảng Bronze để hứng dữ liệu Raw
CREATE TABLE IF NOT EXISTS bronze.raw_crypto_tickers (
    symbol VARCHAR(20) NOT NULL,
    raw_payload JSONB NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, ingested_at)
);

-- Index để tối ưu truy vấn theo symbol và thời gian
CREATE INDEX IF NOT EXISTS idx_bronze_symbol ON bronze.raw_crypto_tickers(symbol);
CREATE INDEX IF NOT EXISTS idx_bronze_ingested_at ON bronze.raw_crypto_tickers(ingested_at);