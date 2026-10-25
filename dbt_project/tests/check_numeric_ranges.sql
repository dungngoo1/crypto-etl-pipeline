select symbol, batch_id
from {{ ref('stg_crypto_tickers') }}
where current_price < 0 or volume_base_24h < 0 or volume_quote_24h < 0 or trade_count_24h < 0
   or (is_analytics_eligible and (
       price_change_percent_24h is null or high_price_24h is null or low_price_24h is null
       or high_price_24h < low_price_24h or current_price < low_price_24h or current_price > high_price_24h
   ))
