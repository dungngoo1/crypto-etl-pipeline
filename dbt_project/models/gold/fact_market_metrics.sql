select
    md5(length(s.symbol)::text || ':' || s.symbol || ':' || s.batch_id) as metric_key,
    t.token_key,
    s.*
from {{ ref('stg_crypto_tickers') }} s
inner join {{ ref('dim_tokens') }} t using (symbol)
