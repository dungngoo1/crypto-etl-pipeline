with actual as (
    select batch_id, count(*) as n from {{ ref('stg_crypto_tickers') }} group by batch_id
)
select b.batch_id
from {{ source('bronze', 'ingestion_batches') }} b
left join actual a using (batch_id)
where coalesce(a.n, 0) <> b.ticker_count
