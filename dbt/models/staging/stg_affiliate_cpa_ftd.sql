with source as (
    select * from {{ source('raw', 'affiliate_cpa_ftd') }}
),

renamed as (
    select
        affiliate_id,
        player_id,
        country,
        safe_cast(clicks as int64) as clicks,
        safe_cast(registrations as int64) as registrations,
        safe_cast(ftd as int64) as ftd,
        safe_cast(cpa_value as numeric) as cpa_value,  -- money (CPA paid), never FLOAT (ADR-0006)
        _ingested_at,
        _source_file
    from source
)

select * from renamed
