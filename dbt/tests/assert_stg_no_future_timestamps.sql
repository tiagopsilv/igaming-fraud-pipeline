-- Bronze DQ (ADR-0010): event timestamps must not be in the future. Fails if any row is returned.
select
    'stg_sessions' as model,
    session_id as id,
    session_ts as ts
from {{ ref('stg_sessions') }}
where session_ts > current_timestamp()

union all

select
    'stg_transactions' as model,
    transaction_id as id,
    txn_ts as ts
from {{ ref('stg_transactions') }}
where txn_ts > current_timestamp()
