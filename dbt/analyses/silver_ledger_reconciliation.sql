-- ============================================================================
-- silver_ledger_reconciliation.sql  (dbt analysis - compiles, does not materialize)
--
-- Silver ledger reconciliation, on the REAL data. A player's wallet is a ledger: deposits
-- in, withdrawals and bets out. A ledger's rule is that the running balance never goes
-- negative - you cannot spend money you never had. This reconstructs the balance
-- transaction by transaction, in time order, and counts where it dips below zero. The
-- running balance is a reusable Silver building block (int_player_ledger); "never negative"
-- is a Silver data-quality assertion; the fraud reading (structuring / laundering) is Gold.
--
-- CAVEAT: the data has bet amounts but no bet outcomes (win/loss), so bets are treated as a
-- pure outflow - a conservative floor that can over-count negatives. The finding is split
-- accordingly: the broad count is an upper bound, while the unambiguous subset (money out
-- before any deposit) holds regardless of how the bets resolved.
-- Run:  dbt show -s silver_ledger_reconciliation --limit 20
-- ============================================================================

-- Reconstruct the ledger: for each player, walk the transactions in time and carry the
-- signed cash flow (deposit +, withdraw/bet -) as a running balance.
with ledger as (
    select
        player_id,
        txn_ts,
        transaction_type,
        sum(case when transaction_type = 'deposit' then amount else -amount end)
            over (partition by player_id order by txn_ts, transaction_id) as running_balance
    from {{ ref('stg_transactions') }}
),

-- Per player: the lowest the balance ever reached, and the two timestamps that decide the
-- unambiguous case - when the first activity happened vs the first deposit.
per_player as (
    select
        player_id,
        min(running_balance)                                 as min_balance,
        min(txn_ts)                                          as first_activity_ts,
        min(if(transaction_type = 'deposit', txn_ts, null))  as first_deposit_ts
    from ledger
    group by player_id
)

-- (1) Did the balance ever go negative at all? Conservative: the missing wins inflate this,
--     so it is read as an upper bound, not a verdict.
select 1 as step, 'players whose running balance goes NEGATIVE (conservative, no win data)' as finding,
       countif(min_balance < 0) as n,
       format('worst reconstructed balance = %.2f', min(min_balance)) as note
from per_player
union all
-- (2) The unambiguous case that no win can explain: money out (bet or withdraw) before the
--     first deposit ever landed.
select 2, 'UNAMBIGUOUS: money-out (bet/withdraw) BEFORE the first deposit',
       countif(first_deposit_ts is null or first_activity_ts < first_deposit_ts),
       'negative funds before any deposit -> impossible regardless of wins'
from per_player
union all
-- (3) The extreme: players who transacted with zero funding, ever.
select 3, 'players who never deposited at all but still transacted',
       countif(first_deposit_ts is null),
       'bet/withdraw with zero funding ever'
from per_player
order by step
