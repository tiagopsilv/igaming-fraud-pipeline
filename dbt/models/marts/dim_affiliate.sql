-- Gold dimension: the affiliate (ADR-0007). One row per affiliate_id with descriptive
-- attributes only. The funnel volumes (clicks/registrations/ftd) are NOT put here: their
-- grain is conflated (ADR-0006), so they belong in agg_affiliate_performance, computed
-- with the grain handled explicitly. Country is per acquired player, not an affiliate
-- attribute, so the dimension summarizes it (how many countries, the primary one).
with rows_ as (
    select
        affiliate_id,
        player_id,
        country
    from {{ ref('stg_affiliate_cpa_ftd') }}
),

primary_country as (
    select
        affiliate_id,
        country as primary_country
    from (
        select
            affiliate_id,
            country,
            row_number() over (partition by affiliate_id order by count(*) desc, country) as rn
        from rows_
        group by affiliate_id, country
    ) as ranked
    where rn = 1
)

select
    r.affiliate_id,
    count(distinct r.player_id) as n_players_claimed,
    count(distinct r.country) as n_acquisition_countries,
    pc.primary_country
from rows_ as r
left join primary_country as pc using (affiliate_id)
group by r.affiliate_id, pc.primary_country
