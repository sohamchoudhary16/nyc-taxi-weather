{{ config(materialized='table') }}

-- The analysis mart: observed demand per zone-hour against a same-zone,
-- same-hour-of-week baseline, so a "rain effect" is not just a rush-hour
-- effect wearing a raincoat.

with observed as (
    select
        pickup_zone,
        pickup_borough,
        pickup_date_local,
        pickup_hour_of_day,
        pickup_day_of_week,
        max(precipitation_band) as precipitation_band,
        {{ bool_or_agg('is_wet_hour') }}    as is_wet_hour,
        avg(temperature_c)      as temperature_c,
        count(*)                as trips,
        sum(total_amount)       as revenue,
        avg(duration_seconds)   as avg_duration_seconds,
        avg(case when duration_seconds > 0
                 then trip_distance_miles / (duration_seconds / 3600.0) end) as avg_speed_mph
    from {{ ref('fct_trips') }}
    where pickup_zone is not null
    group by 1, 2, 3, 4, 5
),

baseline as (
    select
        pickup_zone,
        pickup_day_of_week,
        pickup_hour_of_day,
        {{ safe_filter('avg', 'trips', 'not is_wet_hour') }} as dry_baseline_trips
    from observed
    group by 1, 2, 3
)

select
    o.*,
    b.dry_baseline_trips,
    case when b.dry_baseline_trips > 0
         then (o.trips - b.dry_baseline_trips) / b.dry_baseline_trips end as demand_lift_vs_dry
from observed o
left join baseline b using (pickup_zone, pickup_day_of_week, pickup_hour_of_day)
