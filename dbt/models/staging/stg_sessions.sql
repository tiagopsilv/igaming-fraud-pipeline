with source as (
    select * from {{ source('raw', 'sessions') }}
),

renamed as (
    select
        session_id,
        player_id,
        ip,
        device,
        -- BigQuery autodetect already typed this as TIMESTAMP; safe_cast is safe either way (UTC).
        safe_cast(`timestamp` as timestamp) as session_ts,
        _ingested_at,
        _source_file
    from source
)

select * from renamed
