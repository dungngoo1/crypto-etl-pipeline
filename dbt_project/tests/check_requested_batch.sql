select '{{ var("batch_id") | replace("'", "''") }}' as missing_batch
where not exists (
    select 1 from {{ ref('latest_tickers') }}
    where batch_id = '{{ var("batch_id") | replace("'", "''") }}'
)
