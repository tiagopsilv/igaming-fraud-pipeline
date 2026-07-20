-- Gold fact: one row per transaction, carrying the wallet running balance from the Silver
-- ledger (ADR-0012) - so Power BI can plot exposure over time, not just totals.
--
-- Load strategy (ADR-0008): INCREMENTAL MERGE on transaction_id - money is idempotent, a
-- re-run must never double-count. The running_balance is computed upstream in the FULL
-- int_player_ledger (the window needs each player's whole history), so the fact only loads
-- already-correct rows. A 3-day lookback re-merges late-arriving transactions; merge on the
-- key dedupes, which is what makes the second run safe (the B12 idempotency proof).
-- NOTE ON SCAN PRUNING: in production (where txn_date tracks wall-clock) you would add
-- incremental_predicates bounding DBT_INTERNAL_DEST to the last few partitions, so the MERGE
-- only scans recent days. This sample's timestamps predate today, so a current_date() predicate
-- would prune away every real partition and the merge would re-insert instead of match. The merge
-- therefore matches on the full key here; partition_by still prunes at query time in the dashboard.
{{
  config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='transaction_id',
    partition_by={'field': 'txn_date', 'data_type': 'date'},
    cluster_by=['player_id'],
    on_schema_change='append_new_columns'
  )
}}

select
    transaction_id,
    player_id,
    txn_ts,
    date(txn_ts)       as txn_date,
    transaction_type,
    amount,
    signed_amount,
    running_balance
from {{ ref('int_player_ledger') }}

{% if is_incremental() %}
where txn_ts >= timestamp_sub((select max(txn_ts) from {{ this }}), interval 3 day)
{% endif %}
