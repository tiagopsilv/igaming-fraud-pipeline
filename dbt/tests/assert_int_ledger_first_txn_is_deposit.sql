{{ config(severity='warn') }}
-- Ledger reconciliation: a player's FIRST transaction must be a deposit - no money-out
-- (bet/withdraw) before funding. This is the unambiguous subset of "balance never
-- negative" (it does not depend on the missing bet-outcome data). Warns on the sample.
with first_txn as (
    select
        player_id,
        transaction_type,
        row_number() over (partition by player_id order by txn_ts, transaction_id) as rn
    from {{ ref('int_player_ledger') }}
)

select
    player_id,
    transaction_type
from first_txn
where
    rn = 1
    and transaction_type != 'deposit'
