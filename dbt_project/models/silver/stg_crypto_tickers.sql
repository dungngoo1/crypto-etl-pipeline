with flattened as (
    select
        symbol, batch_id, batch_timestamp, ingested_at,
        nullif(metadata_payload->>'baseAsset', '') as base_asset,
        nullif(metadata_payload->>'quoteAsset', '') as quote_asset,
        coalesce(metadata_payload->>'status', 'UNKNOWN') as trading_status,
        coalesce((metadata_payload->>'isSpotTradingAllowed')::boolean, false) as is_spot_trading_allowed,
        (raw_payload->>'lastPrice')::numeric as current_price,
        (raw_payload->>'openPrice')::numeric as open_price_24h,
        (raw_payload->>'priceChange')::numeric as price_change_24h,
        (raw_payload->>'priceChangePercent')::numeric as price_change_percent_24h,
        (raw_payload->>'highPrice')::numeric as high_price_24h,
        (raw_payload->>'lowPrice')::numeric as low_price_24h,
        (raw_payload->>'volume')::numeric as volume_base_24h,
        (raw_payload->>'quoteVolume')::numeric as volume_quote_24h,
        (raw_payload->>'count')::bigint as trade_count_24h,
        to_timestamp((raw_payload->>'openTime')::double precision / 1000.0) as window_open_timestamp,
        to_timestamp((raw_payload->>'closeTime')::double precision / 1000.0) as snapshot_timestamp
    from {{ source('bronze', 'raw_crypto_tickers') }}
),
classified as (
    select *,
        case
            when base_asset is null or quote_asset is null then 'missing_metadata'
            when trading_status <> 'TRADING' or not is_spot_trading_allowed then 'inactive'
            when current_price is null or current_price <= 0 then 'nonpositive_price'
            when trade_count_24h is null or trade_count_24h <= 0
                or volume_quote_24h is null or volume_quote_24h <= 0 then 'no_activity'
            else null
        end as exclusion_reason
    from flattened
)
select *, exclusion_reason is null as is_analytics_eligible
from classified
