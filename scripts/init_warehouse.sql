CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS ga_candidate;
CREATE SCHEMA IF NOT EXISTS ga;

CREATE TABLE IF NOT EXISTS bronze.ingestion_batches (
    batch_id TEXT PRIMARY KEY,
    batch_timestamp TIMESTAMPTZ NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    ticker_count INTEGER NOT NULL CHECK (ticker_count > 0)
);
CREATE TABLE IF NOT EXISTS bronze.raw_crypto_tickers (
    symbol TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    batch_timestamp TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    raw_payload JSONB NOT NULL,
    metadata_payload JSONB NOT NULL,
    PRIMARY KEY (symbol, batch_id)
);
CREATE INDEX IF NOT EXISTS idx_bronze_v2_ingested_at ON bronze.raw_crypto_tickers(ingested_at);
CREATE INDEX IF NOT EXISTS idx_bronze_v2_batch ON bronze.raw_crypto_tickers(batch_id);
CREATE TABLE IF NOT EXISTS ga.publication_status (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    batch_id TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
