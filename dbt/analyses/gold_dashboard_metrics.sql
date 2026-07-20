-- ============================================================================
-- gold_dashboard_metrics.sql  (dbt analysis - compiles, does not materialize)
--
-- Verify that the headline KPI of each Power BI panel actually computes from the Gold-ready
-- Silver building blocks, on the REAL data. If a panel has no number here, it has no data
-- model. This is the shape the star schema will serve to Power BI (Import mode).
--   Panel 1 Fraud Overview   -> see gold_fraud_signal_scan (suspicious accounts + value at risk)
--   Panel 2 Affiliate Metrics -> CPA owed, qualified FTDs, real revenue, ROI (per affiliate roll-up)
--   Panel 3 Financial Signals -> deposits/withdrawals/bets, net deposit, low-play count
-- Run:  dbt show -s gold_dashboard_metrics --limit 20
-- ============================================================================

with

-- Panel 2 - Affiliate Metrics: the reliable roll-up is the ATTRIBUTED data (never the conflated
-- funnel). CPA owed vs the real revenue those players brought gives the ROI the panel ranks on.
attr as (select * from {{ ref('int_player_affiliate_attribution') }}),
fin  as (select * from {{ ref('int_player_financials') }}),
affiliate as (
    select
        count(distinct attr.affiliate_id)                           as affiliates,
        count(*)                                                    as attributed_players,
        round(sum(attr.cpa_value), 2)                               as cpa_owed,
        round(sum(coalesce(f.net_deposit, 0)), 2)                   as real_revenue,
        round(safe_divide(sum(coalesce(f.net_deposit, 0)), sum(attr.cpa_value)), 2) as roi
    from attr
    left join fin f using (player_id)
),

-- Panel 3 - Financial Signals: the house-level money movement and the low-play count.
financial as (
    select
        round(sum(total_deposits), 2)    as deposits,
        round(sum(total_withdrawals), 2) as withdrawals,
        round(sum(total_bets), 2)        as bets,
        round(sum(net_deposit), 2)       as house_net_deposit,
        countif(total_deposits > 0 and safe_divide(total_bets, total_deposits) < 0.2 and total_withdrawals > 0) as low_play_players
    from fin
)

select 1 as step, 'Affiliate Metrics: CPA owed (R$)' as kpi, cpa_owed as value from affiliate
union all
select 2, 'Affiliate Metrics: real revenue of attributed players (R$)', real_revenue from affiliate
union all
select 3, 'Affiliate Metrics: ROI (revenue / CPA)', roi from affiliate
union all
select 4, 'Financial Signals: total deposits (R$)', deposits from financial
union all
select 5, 'Financial Signals: total withdrawals (R$)', withdrawals from financial
union all
select 6, 'Financial Signals: house net deposit (R$)', house_net_deposit from financial
union all
select 7, 'Financial Signals: low-play + withdrew players', cast(low_play_players as numeric) from financial
order by step
