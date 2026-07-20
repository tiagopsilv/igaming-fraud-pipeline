-- Gold fact: one row per player, the fraud signal profile (ADR-0013). Five CORE signals
-- drive a multi-signal RISK SCORE (a player who trips several is higher confidence - the
-- standard way to cut false positives); five SECONDARY signals are logic-ready flags kept
-- out of the score. value_at_risk = money that left the house (withdrawals).
--
-- HONEST NOTE: the sample is synthetic/random, so a raised flag is coincidental. This is
-- production-grade LOGIC and an honest count, never "fraud found". Derived from the Silver
-- building blocks; the same rules were demonstrated in analyses/gold_fraud_signal_scan.sql.
with
players as (select player_id from {{ ref('int_players_conformed') }}),
fin     as (select * from {{ ref('int_player_financials') }}),
act     as (select * from {{ ref('int_player_activity') }}),

qualified as (select player_id from {{ ref('int_player_qualified_ftd') }} where is_qualified),
ghost as (
    select distinct player_id
    from {{ ref('stg_affiliate_cpa_ftd') }}
    where ftd > 0 and player_id not in (select player_id from qualified)
),
ledger_first as (
    select player_id from (
        select player_id, transaction_type,
               row_number() over (partition by player_id order by txn_ts, transaction_id) as rn
        from {{ ref('int_player_ledger') }}
    ) where rn = 1 and transaction_type != 'deposit'
),
round_dep as (
    select player_id, countif(transaction_type = 'deposit' and mod(amount, 100) = 0) as n_round
    from {{ ref('stg_transactions') }}
    group by player_id
),
country_conflict as (
    select player_id
    from {{ ref('stg_affiliate_cpa_ftd') }}
    group by player_id
    having count(distinct country) > 1
),
reg_by_day as (select created_at as d, count(*) as n from {{ ref('stg_players') }} group by created_at),
reg_p90    as (select approx_quantiles(n, 100)[offset(90)] as p90 from reg_by_day),
reg_burst  as (
    select p.player_id
    from {{ ref('stg_players') }} p
    join reg_by_day d on p.created_at = d.d
    where d.n >= (select p90 from reg_p90)
),

scored as (
    select
        p.player_id,
        -- CORE (scored). coalesce to false so a player with no transactions/sessions
        -- scores 0, not NULL (the flags are a clean, non-null profile).
        coalesce(p.player_id in (select player_id from ghost), false)                     as s_ghost_ftd,
        coalesce(f.total_deposits > 0 and safe_divide(f.total_bets, f.total_deposits) < 0.2
             and f.total_withdrawals > 0, false)                                          as s_aml_low_play,
        coalesce(a.distinct_ips > 10, false)                                              as s_ip_velocity,
        coalesce(p.player_id in (select player_id from ledger_first), false)              as s_ledger_anomaly,
        (coalesce(f.net_deposit, 0) < 0)                                                  as s_net_negative,
        -- SECONDARY (logic-ready, not scored)
        (coalesce(r.n_round, 0) >= 3)                                                     as s_structuring,
        coalesce(p.player_id in (select player_id from country_conflict), false)          as s_geo_conflict,
        (coalesce(a.distinct_devices, 0) >= 3)                                            as s_device_takeover,
        coalesce(p.player_id in (select player_id from reg_burst), false)                 as s_reg_velocity,
        (coalesce(a.active_span_days, 0) > 60)                                            as s_dormant,
        coalesce(f.total_withdrawals, 0)                                                  as value_at_risk
    from players p
    left join fin f using (player_id)
    left join act a using (player_id)
    left join round_dep r using (player_id)
)

select
    *,
    (cast(s_ghost_ftd as int64) + cast(s_aml_low_play as int64) + cast(s_ip_velocity as int64)
     + cast(s_ledger_anomaly as int64) + cast(s_net_negative as int64)) as risk_score
from scored
