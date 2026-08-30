select * from {{ ref('fct_trips') }} where pickup_utc > current_timestamp
