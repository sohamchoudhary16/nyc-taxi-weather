# NYC Taxi × Weather: Data Engineering Case

## TL;DR

An end-to-end data pipeline joining 2.96M NYC yellow taxi trips (January 2024)
with hourly weather data to answer: **which zones become supply-constrained in
wet weather?** Transit hubs (West Chelsea/Hudson Yards +15.5%, JFK Airport
+8.6%, Penn Station +6.9%) see increased demand in rain, while tourist and
residential zones see drops (Seaport −27.3%, Financial District −15.3%). The
hardest technical problem was not the analysis but the silent timezone bug
between TLC's naive local timestamps and Open-Meteo's UTC data, which would
shift every record by 4–5 hours if joined naively.

## Run it

```bash
conda create -n nyc-taxi python=3.11 -y && conda activate nyc-taxi
pip install -r requirements.txt
cd dbt && dbt deps && cd ..
make all
```

No cloud account required. `make databricks` runs the identical dbt models
against Databricks Free Edition to demonstrate portability.

## Architecture

See [`docs/architecture.md`](docs/architecture.md), structured around four
workloads with different SLAs (receipts, fraud, metrics, taxi placement),
not one monolithic pipeline. Decisions and trade-offs are recorded in
[`docs/adr/`](docs/adr/).

## The timezone contract

TLC publishes **naive America/New_York wall-clock time**. Open-Meteo serves
**UTC**. Joining them without an explicit contract silently shifts every record
by 4–5 hours.

The contract is declared in exactly two places:

| Path | Definition |
|---|---|
| `src/taxi/timestamps.py` | Python normalisation with DST handling |
| `dbt/macros/cross_engine.sql` | SQL macros (`local_to_utc` / `utc_to_local`) |

DST is handled explicitly: spring-forward gaps → quarantined, fall-back
ambiguity → resolved to first occurrence, flagged. 13 unit tests cover both
transitions.

## Data quality

Of 2,964,624 rows, **924 (0.03%) are quarantined** as invalid. An additional
~10% carry soft flags (null passengers, zero-distance fares, refunds) that are
kept for downstream use. The largest anomaly (a 25.69% fare reconciliation
gap) was traced to a known TLC inconsistency, not a pipeline bug.

Rows are **flagged and quarantined, never silently dropped.** See
[`docs/data_quality.md`](docs/data_quality.md).

## Analysis

**Headline finding:** transit hubs see the strongest demand increase in wet
hours. Passengers who would otherwise walk switch to taxis at stations when it
rains.

| Zone | Demand lift in wet hours |
|---|---|
| West Chelsea/Hudson Yards | +15.5% |
| JFK Airport | +8.6% |
| Penn Station/Madison Sq West | +6.9% |

**Operational recommendation:** reposition vehicles toward transit hubs during
wet hours. Average speed also drops in rain, so each taxi completes fewer
trips per hour, so the supply gap is larger than the demand lift alone suggests.

**Caveat:** January only, correlational not causal. A full year would separate
seasonal from weather effects.

## What I would do differently at scale

- **Add months** to validate the pattern across seasons
- **Replace ERA5 with NOAA station observations** for auditability (see ADR 0003)
- **Implement fraud detection** as a streaming proof-of-concept before investing in ML
- **Cost model the telemetry pipeline.** At 190M events/day, the sampling rate
  and retention tier is a tens-of-thousands-per-month decision
- **Integration tests** with a fixture dataset in CI, not just unit tests