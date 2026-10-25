with expected as (
    select batch_id, count(*) as n from {{ ref('stg_crypto_tickers') }} group by batch_id
), actual as (
    select batch_id, count(*) as n from {{ ref('fact_market_metrics') }} group by batch_id
)
select e.batch_id from expected e left join actual a using (batch_id)
where coalesce(a.n, 0) <> e.n
