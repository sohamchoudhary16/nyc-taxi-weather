{{ config(materialized='table') }}

-- The join. Hour-truncated UTC on both sides: because both columns were
-- normalised through the same timezone contract, DST transitions cannot
-- silently drop or duplicate rows here. See tests/assert_one_weather_row.sql.

select
    t.vendor_id,
    t.pickup_utc,
    t.pickup_local,
    t.pickup_hour_utc,
    t.duration_seconds,
    t.trip_distance_miles,
    t.passenger_count,
    t.fare_amount,
    t.tip_amount,
    t.total_amount,

    pu.Zone            as pickup_zone,
    pu.Borough         as pickup_borough,
    do_.Zone           as dropoff_zone,
    do_.Borough        as dropoff_borough,

    w.temperature_c,
    w.precipitation_mm,
    w.precipitation_band,
    w.is_wet_hour,
    w.is_snowing,
    w.wind_speed_kmh,

    {{ extract_hour('t.pickup_local') }}  as pickup_hour_of_day,
    {{ extract_dow('t.pickup_local') }} as pickup_day_of_week,
    cast(t.pickup_local as date)       as pickup_date_local

from {{ ref('stg_trips') }} t
left join {{ ref('stg_weather') }} w
       on t.pickup_hour_utc = w.observed_hour_utc
left join {{ source('bronze', 'taxi_zones') }} pu  on t.pickup_zone_id  = pu.LocationID
left join {{ source('bronze', 'taxi_zones') }} do_ on t.dropoff_zone_id = do_.LocationID
where t.is_valid
