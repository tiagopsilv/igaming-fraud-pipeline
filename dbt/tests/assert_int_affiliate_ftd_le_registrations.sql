{{ config(severity='warn') }}
-- Business rule (funnel logic): a row's FTD count cannot exceed its registrations.
-- Warns on the synthetic sample (violated by design); would error on production data.
select affiliate_id, player_id, ftd, registrations
from {{ ref('stg_affiliate_cpa_ftd') }}
where ftd > registrations
