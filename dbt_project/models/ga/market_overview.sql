select
    batch_id, batch_timestamp, max(ingested_at) as captured_at,
    coalesce(quote_asset, 'UNKNOWN') as quote_asset,
    count(*) as returned_pairs,
    count(*) filter (where is_analytics_eligible) as active_pairs,
    count(*) filter (where not is_analytics_eligible) as excluded_pairs,
    count(*) filter (where is_analytics_eligible and price_change_percent_24h > 0) as advancing_pairs,
    count(*) filter (where is_analytics_eligible and price_change_percent_24h < 0) as declining_pairs,
    avg(price_change_percent_24h) filter (where is_analytics_eligible) as avg_change_percent_24h,
    sum(volume_quote_24h) filter (where is_analytics_eligible) as volume_quote_24h,
    sum(trade_count_24h) filter (where is_analytics_eligible) as trade_count_24h
from {{ ref('fact_market_metrics') }}
where ingested_at <= (
    select captured_at from {{ source('bronze', 'ingestion_batches') }}
    where batch_id = '{{ var("batch_id") | replace("'", "''") }}'
)
group by batch_id, batch_timestamp, coalesce(quote_asset, 'UNKNOWN')
