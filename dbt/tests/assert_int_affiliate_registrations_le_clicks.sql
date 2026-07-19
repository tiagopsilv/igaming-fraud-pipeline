{{ config(severity='warn') }}
-- Business rule (funnel logic): registrations cannot exceed clicks.
-- Warns on the synthetic sample; would error on production data.
select affiliate_id, player_id, registrations, clicks
from {{ ref('stg_affiliate_cpa_ftd') }}
where registrations > clicks
