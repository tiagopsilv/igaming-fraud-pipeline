-- Gold aggregate: one row per affiliate, the acquisition performance panel (ADR-0014).
-- Built on the RESOLVED attribution (one qualified player per affiliate, ADR-0002/0004/0011),
-- never on the conflated raw funnel rows. Leads with the trustworthy attributed metrics:
--   qualified_ftds - qualified players credited to the affiliate
--   cpa_owed       - CPA payable on those qualified FTDs
--   real_revenue   - net deposit (deposits - withdrawals) of those players; an honest revenue
--                    proxy, since NGR/GGR need bonus/tax/bet-outcome data the source lacks
--   roi            - real_revenue / cpa_owed
--   ghost_ftds     - FTDs the affiliate CLAIMED but that never qualified (the acquisition-fraud
--                    signal): CPA asked for on air.
with attributed as (
    select player_id, affiliate_id, cpa_value
    from {{ ref('int_player_affiliate_attribution') }}
),
fin as (select player_id, net_deposit from {{ ref('int_player_financials') }}),
qualified as (select player_id from {{ ref('int_player_qualified_ftd') }} where is_qualified),
ghost as (
    select affiliate_id, count(distinct player_id) as ghost_ftds
    from {{ ref('stg_affiliate_cpa_ftd') }}
    where ftd > 0 and player_id not in (select player_id from qualified)
    group by affiliate_id
),
perf as (
    select
        a.affiliate_id,
        count(distinct a.player_id)   as qualified_ftds,
        sum(a.cpa_value)              as cpa_owed,
        sum(f.net_deposit)            as real_revenue
    from attributed a
    left join fin f using (player_id)
    group by a.affiliate_id
)

select
    p.affiliate_id,
    p.qualified_ftds,
    p.cpa_owed,
    p.real_revenue,
    safe_divide(p.real_revenue, p.cpa_owed) as roi,
    coalesce(g.ghost_ftds, 0)               as ghost_ftds
from perf p
left join ghost g using (affiliate_id)
