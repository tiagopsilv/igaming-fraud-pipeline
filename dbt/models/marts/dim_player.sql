-- Gold dimension: the player (SCD Type 1, ADR-0003). One row per player, current
-- attributes only - no history, because the source has no updated_at to drive an SCD-2
-- (ADR-0008). Conformed identity from Silver plus the acquisition context (the affiliate
-- and country that acquired the QUALIFIED player) and the qualified-FTD flag. Acquisition
-- country lives here, not on dim_affiliate, because it varies per acquired player (ADR-0006).
with players as (
    select * from {{ ref('int_players_conformed') }}
),

qualified as (
    select
        player_id,
        first_deposit_ts,
        is_qualified
    from {{ ref('int_player_qualified_ftd') }}
),

attribution as (
    select
        player_id,
        affiliate_id,
        acquisition_country
    from {{ ref('int_player_affiliate_attribution') }}
),

fin as (
    select
        player_id,
        n_deposits
    from {{ ref('int_player_financials') }}
)

select
    p.player_id,
    p.email,
    p.city,
    p.created_at as registered_at,
    coalesce(q.is_qualified, false) as is_qualified_ftd,
    q.first_deposit_ts,
    a.affiliate_id as acquisition_affiliate_id,
    a.acquisition_country,
    -- one-and-done: deposited exactly once, never returned (glossary). Computed in Gold,
    -- not DAX, so it is a reusable, tested flag on the player row.
    coalesce(f.n_deposits, 0) = 1 as is_one_and_done
from players as p
left join qualified as q using (player_id)
left join attribution as a using (player_id)
left join fin as f using (player_id)
