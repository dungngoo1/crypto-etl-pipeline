select symbol, batch_id
from {{ ref('stg_crypto_tickers') }}
group by symbol, batch_id having count(*) <> 1
