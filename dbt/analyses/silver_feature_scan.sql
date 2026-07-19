-- ============================================================================
-- silver_feature_scan.sql  (dbt analysis - compiles, does not materialize)
--
-- Silver feature scan, on the REAL data. With the base conformed, the question shifts to
-- which per-player FEATURES the fraud logic will need, and whether they belong in Silver
-- or Gold. The rule here: the feature (the aggregation) is Silver; the flag (the threshold
-- that calls it suspicious) is Gold. Each feature is built once, and the shape it exposes
-- is located where the Gold signal would read it - never asserted as fraud.
-- Run:  dbt show -s silver_feature_scan --limit 20
-- ============================================================================

with

-- Per-player FINANCIAL features: deposits in, withdrawals and bets out, plus a bet count.
-- The money-side signals build on these. (Silver: int_player_financials.)
fin as (
    select
        player_id,
        sum(if(transaction_type = 'deposit',  amount, 0)) as deposits,
        sum(if(transaction_type = 'withdraw', amount, 0)) as withdrawals,
        sum(if(transaction_type = 'bet',      amount, 0)) as bets,
        countif(transaction_type = 'bet')                 as n_bets
    from {{ ref('stg_transactions') }}
    group by player_id
),

-- Per-player ACTIVITY features: how many IPs and devices a player touched, and how long
-- they stayed active. The behaviour-side signals build on these. (Silver: int_player_activity.)
act as (
    select
        player_id,
        count(distinct ip)     as distinct_ips,
        count(distinct device) as distinct_devices,
        timestamp_diff(max(session_ts), min(session_ts), day) as active_span_days
    from {{ ref('stg_sessions') }}
    group by player_id
),

-- For multi-accounting, flip the grain to the IP and count how many players ride each one.
ip_share as (
    select ip, count(distinct player_id) as players_on_ip
    from {{ ref('stg_sessions') }}
    group by ip
)

-- The shapes each feature exposes: money-side first, then behaviour. Each is a Gold signal
-- that reads a Silver feature.
select 1 as step, 'net-negative players (withdrew > deposited)' as finding,
       countif(withdrawals > deposits) as n,
       'house-loses / one-and-done anomaly -> Gold financial signal' as note
from fin
union all
-- The laundering shape: deposit, barely bet, cash out.
select 2, 'AML low-play: bet_ratio < 0.2 AND withdrew',
       countif(deposits > 0 and safe_divide(bets, deposits) < 0.2 and withdrawals > 0),
       'deposit, barely bet, cash out -> Gold AML signal'
from fin
union all
-- The extreme of it: money in, zero play.
select 3, 'deposited but never placed a bet',
       countif(deposits > 0 and n_bets = 0),
       'money in, no play -> Gold signal input'
from fin
union all
-- Behaviour-side: a player hopping many IPs suggests VPN/bot.
select 4, 'players with > 10 distinct IPs (IP velocity)',
       countif(distinct_ips > 10),
       format('max distinct IPs for one player = %d', (select max(distinct_ips) from act))
from act
union all
-- The multi-account seed: an IP shared by more than one player. (If ~0, the logic is ready but the data has none.)
select 5, 'IPs shared by > 1 player (multi-accounting)',
       (select countif(players_on_ip > 1) from ip_share),
       'shared IP = multi-account foundation -> Gold signal'
union all
-- A long gap between first and last activity: the dormant-then-returning shape.
select 6, 'players with session span > 60 days (dormancy base)',
       countif(active_span_days > 60),
       'first->last gap feeds the dormant-reactivation signal -> Gold'
from act
order by step
