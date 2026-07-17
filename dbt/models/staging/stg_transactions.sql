with source as (
    select * from {{ source('raw', 'transactions') }}
),

renamed as (
    select
        transaction_id,
        player_id,
        `type` as transaction_type,
        safe_cast(amount as numeric) as amount,        -- autodetect typed it FLOAT; fix to NUMERIC (money, ADR-0006)
        -- BigQuery autodetect already typed this as TIMESTAMP; safe_cast is robust either way (UTC).
        safe_cast(`timestamp` as timestamp) as txn_ts,
        _ingested_at,
        _source_file
    from source
)

select * from renamed
