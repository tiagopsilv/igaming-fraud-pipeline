-- Qualified-FTD rule: a player flagged qualified must have a real first deposit AND total bets
-- at or above the baseline. Guards the rule CPA depends on. Expect 0 rows.
select
    player_id,
    total_bets
from {{ ref('int_player_qualified_ftd') }}
where
    is_qualified
    and (first_deposit_ts is null or total_bets < {{ var('qualified_ftd_baseline') }})
