-- Bronze DQ (ADR-0010): money must be strictly positive. Fails if any row is returned.
-- A NULL amount is a cast failure, caught separately by the not_null test.
select
    transaction_id,
    amount
from {{ ref('stg_transactions') }}
where
    amount is not null
    and amount <= 0
