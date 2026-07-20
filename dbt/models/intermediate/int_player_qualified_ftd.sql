-- Silver: the QUALIFIED FTD (ADR-0011). The glossary pays CPA for a player who
-- deposited AND bet the baseline, not merely anyone who deposited. Baseline is a
-- parametrizable business premise (a dbt var).
with first_deposit as (
    select * from {{ ref('int_player_first_deposit') }}
),

bets as (
    select
        player_id,
        sum(amount) as total_bets
    from {{ ref('stg_transactions') }}
    where transaction_type = 'bet'
    group by player_id
)

select
    fd.player_id,
    fd.first_deposit_ts,
    coalesce(b.total_bets, 0) as total_bets,
    coalesce(b.total_bets, 0) >= {{ var('qualified_ftd_baseline') }} as is_qualified
from first_deposit as fd
left join bets as b using (player_id)
