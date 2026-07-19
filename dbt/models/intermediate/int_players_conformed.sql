-- Silver: the conformed player. Business rule = normalize email casing (lowercase).
-- This is NORMALIZATION, not dedup: 600 emails are distinct before and after (ADR-0006).
with players as (
    select * from {{ ref('stg_players') }}
)

select
    player_id,
    lower(email) as email,   -- conform: 22% arrived uppercase; lowercase for joins/dedup safety
    city,
    created_at,
    _ingested_at,
    _source_file
from players
