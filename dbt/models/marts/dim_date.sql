-- Gold dimension: the date spine (ADR-0007). A conformed calendar so every fact can be
-- sliced by day/month/quarter in Power BI. Built data-driven from the real event range
-- (transactions + sessions), so it covers exactly the data on hand with no empty tail.
with bounds as (
    select
        date(min(ts)) as d0,
        date(max(ts)) as d1
    from (
        select txn_ts as ts from {{ ref('stg_transactions') }}
        union all
        select session_ts as ts from {{ ref('stg_sessions') }}
    )
)

select
    d as date_day,
    extract(year from d) as year,
    extract(quarter from d) as quarter,
    extract(month from d) as month,
    extract(day from d) as day,
    extract(dayofweek from d) as day_of_week,   -- 1=Sunday
    format_date('%A', d) as day_name,
    format_date('%Y-%m', d) as year_month,
    (extract(dayofweek from d) in (1, 7)) as is_weekend
from bounds
cross join unnest(generate_date_array(bounds.d0, bounds.d1)) as d
