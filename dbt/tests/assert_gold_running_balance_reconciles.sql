-- Gold ledger integrity: the stored running_balance in fct_transactions must equal the balance
-- recomputed from the signed amounts in time order. Any drift means the fact and the ledger logic
-- disagree - a real bug. Expect 0 rows.
select
    transaction_id,
    running_balance,
    recomputed
from (
    select
        transaction_id,
        running_balance,
        sum(signed_amount) over (partition by player_id order by txn_ts, transaction_id) as recomputed
    from {{ ref('fct_transactions') }}
)
where running_balance != recomputed
