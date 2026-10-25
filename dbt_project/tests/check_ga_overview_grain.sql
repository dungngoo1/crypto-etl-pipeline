select batch_id, quote_asset from {{ ref('market_overview') }}
group by batch_id, quote_asset having count(*) > 1
