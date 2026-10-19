{{ config(
    materialized='table',
    schema='gold'
) }}

WITH silver_data AS (
    SELECT *
    FROM {{ ref('stg_crypto_tickers') }}
),

tokens AS (
    SELECT
        token_key,
        symbol
    FROM {{ ref('dim_tokens') }}
)

SELECT
    -- Kết hợp symbol, snapshot_timestamp và ingested_at để đảm bảo tính duy nhất tuyệt đối
    MD5(CONCAT(s.symbol, '_', s.snapshot_timestamp::text, '_', s.ingested_at::text)) AS metric_key,
    t.token_key,
    s.current_price,
    s.price_change_24h,
    s.price_change_percent_24h,
    s.high_price_24h,
    s.low_price_24h,
    s.volume_base_24h,
    s.volume_quote_24h,
    s.trade_count_24h,
    s.snapshot_timestamp,
    s.ingested_at
FROM silver_data s
INNER JOIN tokens t ON s.symbol = t.symbol