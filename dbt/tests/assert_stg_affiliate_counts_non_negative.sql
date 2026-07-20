-- Bronze DQ (ADR-0010): funnel counts and CPA must be non-negative (0 is valid).
-- Fails if any row is returned.
select
    affiliate_id,
    player_id,
    clicks,
    registrations,
    ftd,
    cpa_value
from {{ ref('stg_affiliate_cpa_ftd') }}
where
    clicks < 0
    or registrations < 0
    or ftd < 0
    or cpa_value < 0
