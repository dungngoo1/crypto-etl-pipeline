with latest as (
    select *, row_number() over (
        partition by symbol
        order by (base_asset is not null) desc, ingested_at desc, batch_id desc
    ) as rn
    from {{ ref('stg_crypto_tickers') }}
)
select md5(symbol) as token_key, symbol, base_asset, quote_asset,
    trading_status as latest_trading_status
from latest
where rn = 1
