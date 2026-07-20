{{ config(severity='warn') }}
-- Business rule: a transaction cannot happen before the player's account existed.
-- Warns on the synthetic sample; would error on production data.
select
    t.transaction_id,
    t.player_id,
    t.txn_ts,
    p.created_at
from {{ ref('stg_transactions') }} as t
inner join {{ ref('int_players_conformed') }} as p using (player_id)
where t.txn_ts < timestamp(p.created_at)
