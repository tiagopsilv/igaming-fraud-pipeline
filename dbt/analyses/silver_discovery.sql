-- ============================================================================
-- silver_discovery.sql  (dbt analysis - compiles, does not materialize)
--
-- Silver-layer discovery, run on the REAL data in BigQuery (the Bronze stg_ views).
-- Bronze typed the data 1:1; this works out, step by step, what Silver must CONFORM,
-- JOIN and DERIVE before the data is business-ready. Each CTE answers one question and
-- the next follows from it; the final SELECT is the evidence, one row per finding.
-- Run:  dbt show -s silver_discovery --limit 20
-- ============================================================================

with

-- (1) Email arrives with mixed case (22% uppercase). The question that decides the fix:
--     is this only casing (normalize) or are there duplicate accounts behind the capitals
--     (dedup)? If lowercasing leaves the distinct count unchanged, it is pure casing.
q1_email as (
    select
        countif(regexp_contains(email, r'[A-Z]')) as emails_uppercase,
        count(distinct email)                     as distinct_raw,
        count(distinct lower(email))              as distinct_lowercased
    from {{ ref('stg_players') }}
),

-- (2) Before joining sessions, transactions and affiliate onto players, confirm the keys
--     are sound: does every child player_id exist in players? An orphan would drop rows.
q2_integrity as (
    select
        (select count(*) from {{ ref('stg_sessions') }} s
         where not exists (select 1 from {{ ref('stg_players') }} p where p.player_id = s.player_id)) as orphan_sessions,
        (select count(*) from {{ ref('stg_transactions') }} t
         where not exists (select 1 from {{ ref('stg_players') }} p where p.player_id = t.player_id)) as orphan_transactions,
        (select count(distinct a.player_id) from {{ ref('stg_affiliate_cpa_ftd') }} a
         where not exists (select 1 from {{ ref('stg_players') }} p where p.player_id = a.player_id)) as orphan_affiliate
),

-- (3) With the joins safe, derive the ground truth. The affiliate file claims first
--     deposits; the actual deposits are in the transactions. Who really deposited?
q3_real_ftd as (
    select count(distinct player_id) as players_with_deposit
    from {{ ref('stg_transactions') }}
    where transaction_type = 'deposit'
),

-- (4) The glossary tightens it: CPA is paid for a QUALIFIED first deposit (deposit AND
--     bet the baseline), not any deposit. Of those who deposited, how many qualify? The
--     gap is CPA a deposit-only view would over-pay.
deposits as (
    select distinct player_id from {{ ref('stg_transactions') }} where transaction_type = 'deposit'
),
bets as (
    select player_id, sum(amount) as total_bet
    from {{ ref('stg_transactions') }} where transaction_type = 'bet' group by player_id
),
q4_qualified as (
    select
        count(distinct d.player_id)             as deposited,
        countif(b.total_bet is not null)        as also_bet,
        countif(coalesce(b.total_bet, 0) >= 50) as qualified_baseline_50
    from deposits d
    left join bets b using (player_id)
),

-- (5) The cross-source impossibilities. A transaction dated before the account existed
--     cannot happen in a real system.
q5_tx_before as (
    select count(*) as tx_before_created
    from {{ ref('stg_transactions') }} t
    join {{ ref('stg_players') }} p using (player_id)
    where t.txn_ts < timestamp(p.created_at)
),

-- (6) The same rule, deeper: money cannot leave before it arrived. A withdrawal before
--     the player's first deposit is impossible.
first_dep as (
    select player_id, min(txn_ts) as first_deposit_ts
    from {{ ref('stg_transactions') }} where transaction_type = 'deposit' group by player_id
),
q6_wd_before as (
    select count(*) as wd_before_deposit
    from {{ ref('stg_transactions') }} w
    join first_dep f using (player_id)
    where w.transaction_type = 'withdraw' and w.txn_ts < f.first_deposit_ts
),

-- (7) A conforming risk in the affiliate file: is one player tagged under more than one
--     country across its rows?
q7_multi_country as (
    select countif(cnt > 1) as players_multi_country
    from (select player_id, count(distinct country) as cnt
          from {{ ref('stg_affiliate_cpa_ftd') }} group by player_id)
),

-- (8-9) The affiliate funnel must be internally monotone: a row cannot report more FTDs
--       than registrations, nor more registrations than clicks. These become Silver tests.
q8_funnel as (
    select
        countif(ftd > registrations)    as ftd_gt_reg,
        countif(registrations > clicks) as reg_gt_clicks
    from {{ ref('stg_affiliate_cpa_ftd') }}
),

-- (10) The reason the affiliate rows are never summed: the same (affiliate, player) pair
--      repeats. That is the conflated grain, resolved by attribution (ADR-0004).
q9_dup as (
    select
        (select count(*) from {{ ref('stg_affiliate_cpa_ftd') }})
        - (select count(*) from (select distinct affiliate_id, player_id
                                 from {{ ref('stg_affiliate_cpa_ftd') }})) as excess_dup_rows
)

-- The findings, in the order they were reached.
select 1 as step, 'email uppercase -> normalize (not dedup)' as finding,
       emails_uppercase as n,
       format('distinct raw=%d = lowercased=%d, so no real duplicate', distinct_raw, distinct_lowercased) as note
from q1_email
union all
select 2, 'orphan child player_ids (referential integrity)',
       orphan_sessions + orphan_transactions + orphan_affiliate,
       format('sessions=%d, transactions=%d, affiliate=%d', orphan_sessions, orphan_transactions, orphan_affiliate)
from q2_integrity
union all
select 3, 'real FTD: players with an actual deposit', players_with_deposit,
       'int_player_first_deposit = MIN(deposit ts) per player'
from q3_real_ftd
union all
select 4, 'qualified FTD: deposited AND bets >= baseline(50)', qualified_baseline_50,
       format('of %d that deposited, %d also placed bets', deposited, also_bet)
from q4_qualified
union all
select 5, 'transactions before created_at (impossible)', tx_before_created, 'becomes a Silver custom test'
from q5_tx_before
union all
select 6, 'withdrawals before first deposit (impossible)', wd_before_deposit, 'becomes a Silver custom test'
from q6_wd_before
union all
select 7, 'players tagged with >1 country (multi-tagging)', players_multi_country, 'DQ / fraud smell'
from q7_multi_country
union all
select 8, 'affiliate ftd > registrations (impossible funnel)', ftd_gt_reg, 'business rule -> Silver custom test'
from q8_funnel
union all
select 9, 'affiliate registrations > clicks (impossible funnel)', reg_gt_clicks, 'business rule -> Silver custom test'
from q8_funnel
union all
select 10, 'duplicate (affiliate, player) rows (conflated grain)', excess_dup_rows, 'resolved by attribution (ADR-0004)'
from q9_dup
order by step
