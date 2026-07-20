-- Silver: per-player ACTIVITY rollup - a reusable building block for the Gold
-- fraud signals (IP velocity, multi-accounting, dormant reactivation).
with sessions as (
    select * from {{ ref('stg_sessions') }}
)

select
    player_id,
    count(*) as session_count,
    count(distinct ip) as distinct_ips,
    count(distinct device) as distinct_devices,
    min(session_ts) as first_session_ts,
    max(session_ts) as last_session_ts,
    timestamp_diff(max(session_ts), min(session_ts), day) as active_span_days
from sessions
group by player_id
