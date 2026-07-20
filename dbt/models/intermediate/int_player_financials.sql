-- Silver: per-player FINANCIAL rollup - a reusable building block for the Gold
-- fraud signals, dim_player and the dashboard (net deposit, bet_ratio). Computed
-- once here (DRY), consumed by many marts.
with tx as (
    select * from {{ ref('stg_transactions') }}
),

agg as (
    select
        player_id,
        sum(if(transaction_type = 'deposit', amount, 0)) as total_deposits,
        sum(if(transaction_type = 'withdraw', amount, 0)) as total_withdrawals,
        sum(if(transaction_type = 'bet', amount, 0)) as total_bets,
        countif(transaction_type = 'deposit') as n_deposits,
        countif(transaction_type = 'withdraw') as n_withdrawals,
        countif(transaction_type = 'bet') as n_bets
    from tx
    group by player_id
)

select
    player_id,
    total_deposits,
    total_withdrawals,
    total_bets,
    total_deposits - total_withdrawals as net_deposit,
    safe_divide(total_bets, total_deposits) as bet_ratio,
    n_deposits,
    n_withdrawals,
    n_bets
from agg
