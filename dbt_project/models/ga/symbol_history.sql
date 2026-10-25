select
    metric_key, batch_id, batch_timestamp, ingested_at, symbol, base_asset, quote_asset,
    current_price, price_change_percent_24h, volume_quote_24h, snapshot_timestamp
from {{ ref('fact_market_metrics') }}
where is_analytics_eligible
  and ingested_at <= (
      select captured_at from {{ source('bronze', 'ingestion_batches') }}
      where batch_id = '{{ var("batch_id") | replace("'", "''") }}'
  )
