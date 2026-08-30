{{ config(materialized='table') }}

-- Weather arrives already UTC-normalised by src/taxi/load_duckdb.py, so this
-- model only conforms names, derives the join key, and adds derived flags.

select
    observed_at_utc                                        as observed_at_utc,
    {{ trunc_hour('observed_at_utc') }}                    as observed_hour_utc,
    cast(temperature_2m as double)                         as temperature_c,
    cast(apparent_temperature as double)                   as apparent_temperature_c,
    cast(precipitation as double)                          as precipitation_mm,
    cast(snowfall as double)                               as snowfall_cm,
    cast(wind_speed_10m as double)                         as wind_speed_kmh,
    cast(weather_code as int)                              as weather_code,
    coalesce(cast(precipitation as double), 0) >= 0.5      as is_wet_hour,
    coalesce(cast(snowfall as double), 0)      >  0        as is_snowing,
    case
        when coalesce(cast(precipitation as double), 0) = 0   then 'dry'
        when cast(precipitation as double) < 0.5              then 'trace'
        when cast(precipitation as double) < 2.5              then 'light'
        when cast(precipitation as double) < 7.6              then 'moderate'
        else 'heavy'
    end                                                    as precipitation_band
from {{ source('bronze', 'weather') }}
where observed_at_is_valid
