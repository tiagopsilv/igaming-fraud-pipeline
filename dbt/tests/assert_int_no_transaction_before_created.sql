{{ config(severity='warn') }}
-- Business rule: a transaction cannot happen before the player's account existed.
-- Warns on the synthetic sample; would error on production data.
select t.transaction_id, t.player_id, t.txn_ts, p.created_at
from {{ ref('stg_transactions') }} t
join {{ ref('int_players_conformed') }} p using (player_id)
where t.txn_ts < timestamp(p.created_at)
