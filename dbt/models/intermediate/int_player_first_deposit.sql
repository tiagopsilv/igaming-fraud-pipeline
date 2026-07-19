-- Silver: the REAL first deposit (FTD) per player, derived from transactions.
-- Ground truth for FTD, independent of what the affiliate file claims (ADR-0004).
with tx as (
    select * from {{ ref('stg_transactions') }}
    where transaction_type = 'deposit'
)

select
    player_id,
    min(txn_ts)  as first_deposit_ts,
    count(*)     as deposit_count,
    sum(amount)  as total_deposits
from tx
group by player_id
