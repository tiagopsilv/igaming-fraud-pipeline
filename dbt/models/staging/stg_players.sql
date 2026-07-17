with source as (
    select * from {{ source('raw', 'players') }}
),

renamed as (
    select
        player_id,
        email,
        city,
        safe_cast(created_at as date) as created_at,   -- date-only (ADR-0006)
        _ingested_at,
        _source_file
    from source
)

select * from renamed
