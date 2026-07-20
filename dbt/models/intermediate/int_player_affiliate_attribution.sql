-- Silver: resolve ONE affiliate per player (ADR-0002/0004), gated on the QUALIFIED
-- FTD (ADR-0011). The affiliate that claims the FTD wins, with a deterministic
-- tiebreak (highest cpa_value, then lowest affiliate_id). Only qualified players
-- earn a CPA credit. Never sums the conflated affiliate rows.
with qualified as (
    select player_id
    from {{ ref('int_player_qualified_ftd') }}
    where is_qualified
),

claims as (
    select
        affiliate_id,
        player_id,
        country,
        cpa_value,
        row_number() over (
            partition by player_id order by cpa_value desc, affiliate_id asc
        ) as pick
    from {{ ref('stg_affiliate_cpa_ftd') }}
    where ftd > 0
)

select
    c.player_id,
    c.affiliate_id,
    c.country as acquisition_country,   -- of the attributed row (not an affiliate attribute)
    c.cpa_value
from claims as c
inner join qualified using (player_id)      -- gate: only qualified FTDs earn CPA (ADR-0011)
where c.pick = 1
