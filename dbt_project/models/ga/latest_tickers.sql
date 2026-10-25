-- Exactly the selected batch; never choose latest per symbol.
select
    metric_key, batch_id, batch_timestamp, ingested_at,
    symbol, base_asset, quote_asset, trading_status,
    current_price, price_change_percent_24h, high_price_24h, low_price_24h,
    volume_quote_24h, trade_count_24h, snapshot_timestamp,
    dense_rank() over (partition by quote_asset order by price_change_percent_24h desc) as gain_rank,
    dense_rank() over (partition by quote_asset order by price_change_percent_24h asc) as loss_rank,
    row_number() over (partition by quote_asset order by volume_quote_24h desc, symbol) as volume_rank
from {{ ref('fact_market_metrics') }}
where is_analytics_eligible
  and batch_id = '{{ var("batch_id") | replace("'", "''") }}'
