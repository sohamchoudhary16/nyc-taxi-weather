# Data quality

**Source file:** `yellow_tripdata_2024-01.parquet`
**Total rows:** 2,964,624
**Pickup range:** 2002-12-31 22:59:39 → 2024-02-01 00:01:15
(file nominally covers January 2024, but contains timestamps spanning 21 years)

| Rule | Column(s) | Action | Notes |
|---|---|---|---|
| Pickup outside plausible range (< 2009 / ≥ 2030) | `tpep_pickup_datetime` | quarantine | min pickup is 2002-12-31 — over 21 years before the file's month |
| Pickup bleeds into next month | `tpep_pickup_datetime` | quarantine | max pickup is 2024-02-01 00:01:15 — past the end of January |
| Dropoff not after pickup | pickup / dropoff | quarantine | `dq_non_positive_duration` flag in `stg_trips` |
| Timestamp in DST gap | pickup | quarantine | Jan 2024 has no DST transition; expect 0 rows for this file |
| Timestamp in DST fall-back hour | pickup | keep, flag | Jan 2024 has no fall-back; expect 0 rows for this file |
| Zero distance, non-zero fare | distance / fare | keep, flag | `dq_zero_distance_paid` — likely dispatcher cancellations |
| Distance > 500 miles | distance | quarantine | `dq_implausible_distance` |
| Passenger count 0 or null | `passenger_count` | keep, flag | `dq_no_passengers` |
| Negative total (refund) | `total_amount` | **keep**, flag | `dq_negative_total` — genuine refunds, not errors |
| Unknown zone (264 / 265) | `PU/DOLocationID` | keep, flag | `dq_unknown_zone` — "Unknown" and "NV" in zone lookup |
| Exact duplicate row | composite key | quarantine | `dq_duplicate_row` via `row_number()` dedup |

## Why quarantine rather than filter
A dropped row is invisible. A quarantined row has a `failure_reason`, gets
counted in the DQ metrics table, and can be replayed after a rule is fixed.
Silently filtering is how you lose revenue you cannot reconcile.
