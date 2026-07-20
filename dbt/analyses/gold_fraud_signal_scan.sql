-- ============================================================================
-- gold_fraud_signal_scan.sql  (dbt analysis - compiles, does not materialize)
--
-- Gold-layer fraud discovery, on the REAL data. Silver built the trustworthy per-player
-- building blocks; the question here is which fraud SIGNALS the Gold can raise from them,
-- how many players each catches, and the value at risk (R$). The design target is
-- fct_fraud_signals: per-player flags plus a multi-signal RISK SCORE - because a single
-- signal over-flags, and a player who trips several is far higher confidence (the standard
-- way to cut false positives).
--
-- The scan has two parts. PART 1 is the five CORE signals with material value at risk; they
-- drive the risk score. PART 2 walks the rest of the fraud catalog (structuring, geo
-- conflict, device takeover, registration velocity, dormant reactivation) - each computable
-- here, kept as logic-ready flags but OUT of the score, because on this data they are thin.
--
-- HONEST NOTE: the sample is synthetic/random, so any hit is coincidental. This is
-- production-ready logic and an honest count, never "fraud found".
-- Run:  dbt show -s gold_fraud_signal_scan --limit 30
-- ============================================================================

with

players as (select player_id from {{ ref('int_players_conformed') }}),
fin     as (select * from {{ ref('int_player_financials') }}),
act     as (select * from {{ ref('int_player_activity') }}),

-- The strongest lead first: affiliate ghost-FTD. An affiliate claims a first deposit
-- (ftd > 0) for a player who never QUALIFIED - the CPA is owed on air.
qualified as (select player_id from {{ ref('int_player_qualified_ftd') }} where is_qualified),
ghost as (
    select distinct player_id
    from {{ ref('stg_affiliate_cpa_ftd') }}
    where ftd > 0 and player_id not in (select player_id from qualified)
),

-- The ledger anomaly: the player's FIRST transaction is money-out (bet/withdraw) before
-- any deposit - the reconciliation red flag from the Silver ledger.
ledger_first as (
    select player_id from (
        select player_id, transaction_type,
               row_number() over (partition by player_id order by txn_ts, transaction_id) as rn
        from {{ ref('int_player_ledger') }}
    ) where rn = 1 and transaction_type != 'deposit'
),

-- PART 2 building blocks -----------------------------------------------------
-- Structuring/smurfing: a player who splits funding into repeated ROUND deposits (whole
-- hundreds) - the classic below-a-limit pattern. Flag >= 3 round deposits.
round_dep as (
    select player_id, countif(transaction_type = 'deposit' and mod(amount, 100) = 0) as n_round
    from {{ ref('stg_transactions') }}
    group by player_id
),
-- Geo conflict: one player tagged under more than one acquisition country across affiliate
-- rows - either self-referral farming or dirty attribution.
country_conflict as (
    select player_id
    from {{ ref('stg_affiliate_cpa_ftd') }}
    group by player_id
    having count(distinct country) > 1
),
-- Registration velocity: accounts created on a BURST day (daily volume in the top decile).
-- created_at is date-only, so this is day-grain, not per-IP - an honest limit.
reg_by_day as (select created_at as d, count(*) as n from {{ ref('stg_players') }} group by created_at),
reg_p90    as (select approx_quantiles(n, 100)[offset(90)] as p90 from reg_by_day),
reg_burst  as (
    select p.player_id
    from {{ ref('stg_players') }} p
    join reg_by_day d on p.created_at = d.d
    where d.n >= (select p90 from reg_p90)
),

-- Per-player signals. CORE five carry the value at risk (money that left the house);
-- the secondary five are logic-ready flags.
scored as (
    select
        p.player_id,
        -- CORE (drive the risk score). coalesce to false so a player with no
        -- transactions/sessions scores 0, not NULL (matches the fct_fraud_signals model).
        coalesce(p.player_id in (select player_id from ghost), false)                     as s_ghost_ftd,
        coalesce(f.total_deposits > 0 and safe_divide(f.total_bets, f.total_deposits) < 0.2
             and f.total_withdrawals > 0, false)                                          as s_aml_low_play,
        coalesce(a.distinct_ips > 10, false)                                              as s_ip_velocity,
        coalesce(p.player_id in (select player_id from ledger_first), false)              as s_ledger_anomaly,
        (coalesce(f.net_deposit, 0) < 0)                                                  as s_net_negative,
        -- SECONDARY (logic-ready, not scored)
        (coalesce(r.n_round, 0) >= 3)                                                     as s_structuring,
        (p.player_id in (select player_id from country_conflict))                         as s_geo_conflict,
        (a.distinct_devices >= 3)                                                         as s_device_takeover,
        (p.player_id in (select player_id from reg_burst))                                as s_reg_velocity,
        (a.active_span_days > 60)                                                         as s_dormant,
        coalesce(f.total_withdrawals, 0)                                                  as value_at_risk
    from players p
    left join fin f using (player_id)
    left join act a using (player_id)
    left join round_dep r using (player_id)
),

-- The risk score: count of CORE signals a player trips. A score >= 2 is the high-confidence set.
flagged as (
    select *,
        (cast(s_ghost_ftd as int64) + cast(s_aml_low_play as int64) + cast(s_ip_velocity as int64)
         + cast(s_ledger_anomaly as int64) + cast(s_net_negative as int64)) as risk_score
    from scored
)

-- PART 1: each core signal, its reach, and the value at risk; then the multi-signal set.
select 1 as step, 'CORE  affiliate ghost-FTD (claimed, never qualified)' as signal,
       countif(s_ghost_ftd) as players_flagged,
       round(sum(if(s_ghost_ftd, value_at_risk, 0)), 2) as value_at_risk
from flagged
union all
select 2, 'CORE  AML low-play (bet_ratio < 0.2 AND withdrew)', countif(s_aml_low_play),
       round(sum(if(s_aml_low_play, value_at_risk, 0)), 2)
from flagged
union all
select 3, 'CORE  IP velocity (> 10 distinct IPs)', countif(s_ip_velocity),
       round(sum(if(s_ip_velocity, value_at_risk, 0)), 2)
from flagged
union all
select 4, 'CORE  ledger anomaly (money-out before funding)', countif(s_ledger_anomaly),
       round(sum(if(s_ledger_anomaly, value_at_risk, 0)), 2)
from flagged
union all
select 5, 'CORE  net-negative (withdrew > deposited)', countif(s_net_negative),
       round(sum(if(s_net_negative, value_at_risk, 0)), 2)
from flagged
union all
select 6, 'CORE  MULTI-SIGNAL (risk_score >= 2, high confidence)', countif(risk_score >= 2),
       round(sum(if(risk_score >= 2, value_at_risk, 0)), 2)
from flagged
-- PART 2: the rest of the catalog - computable, logic-ready, out of the score.
union all
select 7, 'SEC   structuring (>= 3 round deposits)', countif(s_structuring),
       round(sum(if(s_structuring, value_at_risk, 0)), 2)
from flagged
union all
select 8, 'SEC   geo conflict (> 1 acquisition country)', countif(s_geo_conflict),
       round(sum(if(s_geo_conflict, value_at_risk, 0)), 2)
from flagged
union all
select 9, 'SEC   device takeover (>= 3 distinct devices)', countif(s_device_takeover),
       round(sum(if(s_device_takeover, value_at_risk, 0)), 2)
from flagged
union all
select 10, 'SEC   registration velocity (burst day, top decile)', countif(s_reg_velocity),
       round(sum(if(s_reg_velocity, value_at_risk, 0)), 2)
from flagged
union all
select 11, 'SEC   dormant reactivation (active span > 60d)', countif(s_dormant),
       round(sum(if(s_dormant, value_at_risk, 0)), 2)
from flagged
order by step
