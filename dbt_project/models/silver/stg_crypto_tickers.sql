{{ config(
    materialized='table',
    schema='silver'
) }}

WITH source_data AS (
    SELECT
        symbol,
        raw_payload,
        ingested_at
    FROM {{ source('bronze', 'raw_crypto_tickers') }}
),

flattened AS (
    SELECT
        symbol,
        (raw_payload->>'lastPrice')::NUMERIC AS current_price,
        (raw_payload->>'priceChange')::NUMERIC AS price_change_24h,
        (raw_payload->>'priceChangePercent')::NUMERIC AS price_change_percent_24h,
        (raw_payload->>'highPrice')::NUMERIC AS high_price_24h,
        (raw_payload->>'lowPrice')::NUMERIC AS low_price_24h,
        (raw_payload->>'volume')::NUMERIC AS volume_base_24h,
        (raw_payload->>'quoteVolume')::NUMERIC AS volume_quote_24h,
        (raw_payload->>'count')::BIGINT AS trade_count_24h,
        TO_TIMESTAMP((raw_payload->>'closeTime')::BIGINT / 1000) AS snapshot_timestamp,
        ingested_at
    FROM source_data
)

SELECT *
FROM flattened
WHERE current_price IS NOT NULL
  AND current_price > 0