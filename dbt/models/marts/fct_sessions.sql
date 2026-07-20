-- Gold fact: one row per session (ip/device per access) - the input to the IP/device
-- fraud drill-down in Power BI.
--
-- Load strategy (ADR-0008): INCREMENTAL INSERT_OVERWRITE by day. Sessions are a high-volume
-- append-only event with no updates, so overwriting whole day-partitions is cheaper and
-- self-healing (a re-run of a day replaces it cleanly - no dedup needed). A 3-day window
-- absorbs late-arriving sessions.
{{
  config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by={'field': 'session_date', 'data_type': 'date'},
    cluster_by=['player_id'],
    on_schema_change='append_new_columns'
  )
}}

select
    session_id,
    player_id,
    ip,
    device,
    session_ts,
    date(session_ts) as session_date
from {{ ref('stg_sessions') }}

{% if is_incremental() %}
    where date(session_ts) >= date_sub((select max(session_date) from {{ this }}), interval 3 day)
{% endif %}
