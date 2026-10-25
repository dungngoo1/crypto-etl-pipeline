-- Run with psql. Old watchlist history is preserved unchanged for audit.
BEGIN;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'bronze' AND table_name = 'raw_crypto_tickers'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'bronze' AND table_name = 'raw_crypto_tickers' AND column_name = 'batch_id'
    ) THEN
        ALTER TABLE bronze.raw_crypto_tickers RENAME TO raw_crypto_tickers_legacy;
    END IF;
END $$;
\ir init_warehouse.sql
COMMIT;
