{{ config(
    materialized='table',
    schema='gold'
) }}

WITH distinct_tokens AS (
    SELECT DISTINCT
        symbol
    FROM {{ ref('stg_crypto_tickers') }}
)

SELECT
    MD5(symbol) AS token_key, -- Tạo surrogate key bằng hàm băm MD5
    symbol,
    REPLACE(symbol, 'USDT', '') AS base_asset,
    'USDT' AS quote_asset
FROM distinct_tokens