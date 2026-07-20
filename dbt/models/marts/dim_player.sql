-- Gold dimension: the player (SCD Type 1, ADR-0003). One row per player, current
-- attributes only - no history, because the source has no updated_at to drive an SCD-2
-- (ADR-0008). Conformed identity from Silver plus the acquisition context (the affiliate
-- and country that acquired the QUALIFIED player) and the qualified-FTD flag. Acquisition
-- country lives here, not on dim_affiliate, because it varies per acquired player (ADR-0006).
with players as (
    select * from {{ ref('int_players_conformed') }}
),
qualified as (
    select player_id, first_deposit_ts, is_qualified from {{ ref('int_player_qualified_ftd') }}
),
attribution as (
    select player_id, affiliate_id, acquisition_country from {{ ref('int_player_affiliate_attribution') }}
)

select
    p.player_id,
    p.email,
    p.city,
    p.created_at                               as registered_at,
    coalesce(q.is_qualified, false)            as is_qualified_ftd,
    q.first_deposit_ts,
    a.affiliate_id                             as acquisition_affiliate_id,
    a.acquisition_country
from players p
left join qualified   q using (player_id)
left join attribution a using (player_id)
