-- Every valid trip must find exactly one weather hour.
-- Combined with the `unique` test on stg_weather.observed_hour_utc, this is
-- what would have caught a UTC/local mismatch or a DST fall-back duplicate:
-- a 5-hour offset leaves the month edges unmatched, and a duplicated 01:00
-- on the fall-back date fans the join out.
select t.pickup_hour_utc, count(*) as unmatched_trips
from {{ ref('stg_trips') }} t
left join {{ ref('stg_weather') }} w
       on t.pickup_hour_utc = w.observed_hour_utc
where t.is_valid
  and t.pickup_hour_utc >= (select min(observed_hour_utc) from {{ ref('stg_weather') }})
  and t.pickup_hour_utc <= (select max(observed_hour_utc) from {{ ref('stg_weather') }})
  and w.observed_hour_utc is null
group by 1
