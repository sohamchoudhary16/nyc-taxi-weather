# ADR 0003 — ERA5 reanalysis over NOAA station observations

**Status:** accepted (with a production caveat)

## Context

The analysis requires hourly weather data for NYC to join with taxi trip
records. Two main source families exist:

1. **Station observations** — NOAA ISD/LCD, from physical weather stations
   (e.g. Central Park, JFK, LaGuardia). Ground truth, auditable, but
   station-specific and can have gaps.
2. **Reanalysis** — ERA5 via Open-Meteo Archive API. Modelled data on a
   regular grid, gap-free, hourly, globally consistent. CC BY 4.0 licensed,
   no API key required.

## Decision

Use **ERA5 reanalysis via the Open-Meteo Archive API** for this project.

## Rationale

- **No signup, no API key, no cost.** The Open-Meteo Archive API is free for
  non-commercial use, returns JSON, and supports arbitrary date ranges with
  a single HTTP call. This keeps the ingestion script simple and reproducible.
- **Gap-free.** Station data can have missing hours (sensor outage, maintenance).
  ERA5 is model output on a regular grid — every hour is present by
  construction.
- **Sufficient for the analysis question.** The goal is to measure the
  relationship between precipitation and taxi demand at the city level.
  ERA5 at ~0.25° resolution is more than adequate for this granularity.
- **The timezone is unambiguous.** Open-Meteo returns UTC when asked
  explicitly (`timezone=UTC`). NOAA ISD uses UTC as well, but LCD (Local
  Climatological Data) uses local time with DST conventions that vary by
  station, introducing the same class of bug this project was built to avoid.

## Production caveat

In a production system I would use **NOAA station observations as the primary
source** and ERA5 as backfill:

- Station observations are ground truth. If a fare dispute hinges on "was it
  raining at pickup time," the answer should come from a calibrated instrument,
  not a model.
- Multiple NYC stations (Central Park, JFK, LaGuardia) allow cross-validation
  and zone-level weather assignment rather than a single city-wide value.
- NOAA data is public domain (no license restrictions for commercial use).

The pipeline's structure (separate ingestion, explicit timezone contract,
hour-key join) would not change — only the data source and a minor schema
mapping.
