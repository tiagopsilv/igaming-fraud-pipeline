-- Silver: the player wallet LEDGER - the running balance per transaction, ordered
-- in time. Deposits are money in (+); withdrawals and bets are money out (-). This
-- is the reconciliation building block (audit-replay): the running balance should
-- never go negative (you cannot spend money you never had).
--
-- CAVEAT: the data has bet amounts but no bet OUTCOMES (win/loss), so bets are a
-- pure outflow here - a conservative reconstruction. The integrity test built on
-- this warns rather than errors (see tests/assert_int_ledger_first_txn_is_deposit).
with tx as (
    select * from {{ ref('stg_transactions') }}
)

select
    transaction_id,
    player_id,
    txn_ts,
    transaction_type,
    amount,
    case when transaction_type = 'deposit' then amount else -amount end as signed_amount,
    sum(case when transaction_type = 'deposit' then amount else -amount end)
        over (partition by player_id order by txn_ts, transaction_id) as running_balance
from tx
