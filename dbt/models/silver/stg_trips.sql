{{ config(materialized='table') }}

-- Silver: conformed, typed, timezone-normalised, deduplicated.
-- Rows are NOT filtered here. Validity is expressed as flags so that
-- silver_trips_quarantine can count and explain every rejection.

with src as (
    select
        cast(VendorID as int)                     as vendor_id,
        tpep_pickup_datetime                      as pickup_local_raw,
        tpep_dropoff_datetime                     as dropoff_local_raw,
        cast(passenger_count as int)              as passenger_count,
        cast(trip_distance as double)             as trip_distance_miles,
        cast(PULocationID as int)                 as pickup_zone_id,
        cast(DOLocationID as int)                 as dropoff_zone_id,
        cast(fare_amount as double)               as fare_amount,
        cast(tip_amount as double)                as tip_amount,
        cast(total_amount as double)              as total_amount,
        cast(payment_type as int)                 as payment_type
    from {{ source('bronze', 'trips') }}
),

timed as (
    select
        *,
        {{ local_to_utc('pickup_local_raw',  var('trip_source_tz')) }} as pickup_utc,
        {{ local_to_utc('dropoff_local_raw', var('trip_source_tz')) }} as dropoff_utc
    from src
),

flagged as (
    select
        *,
        date_diff('second', pickup_utc, dropoff_utc) as duration_seconds,

        -- Each rule is a named boolean so DQ reporting is a simple pivot.
        pickup_utc  is null                                       as dq_pickup_unparseable,
        dropoff_utc is null                                       as dq_dropoff_unparseable,
        dropoff_utc <= pickup_utc                                 as dq_non_positive_duration,
        date_diff('second', pickup_utc, dropoff_utc) > 86400     as dq_duration_exceeds_24h,
        pickup_utc < timestamptz '{{ var("min_valid_ts") }} 00:00:00+00'
          or pickup_utc >= timestamptz '{{ var("max_valid_ts") }} 00:00:00+00'
                                                                  as dq_pickup_out_of_range,
        trip_distance_miles <= 0 and fare_amount > 0              as dq_zero_distance_paid,
        trip_distance_miles > 500                                 as dq_implausible_distance,
        coalesce(passenger_count, 0) = 0                          as dq_no_passengers,
        total_amount < 0                                          as dq_negative_total,
        pickup_zone_id in (264, 265)
          or dropoff_zone_id in (264, 265)                        as dq_unknown_zone
    from timed
),

deduped as (
    select *,
        row_number() over (
            partition by vendor_id, pickup_utc, dropoff_utc,
                         pickup_zone_id, dropoff_zone_id, total_amount
            order by trip_distance_miles desc
        ) as _dupe_rank
    from flagged
)

select
    *,
    _dupe_rank > 1 as dq_duplicate_row,
    not (
        dq_pickup_unparseable or dq_dropoff_unparseable
        or dq_non_positive_duration or dq_duration_exceeds_24h
        or dq_pickup_out_of_range
        or dq_implausible_distance or (_dupe_rank > 1)
    ) as is_valid,
    {{ utc_to_local('pickup_utc', var('reporting_tz')) }} as pickup_local,
    {{ trunc_hour('pickup_utc') }}                        as pickup_hour_utc
from deduped
