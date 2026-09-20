# ADR 0002: Quarantine, not filter

**Status:** accepted

## Context

The NYC TLC dataset contains rows that fail validity checks: negative durations,
timestamps from years outside the file's month, implausible distances, and
negative fares. The standard approach in many tutorials is to filter these out
with a `WHERE` clause before analysis.

## Decision

Invalid rows are **flagged with named boolean columns** (`dq_non_positive_duration`,
`dq_pickup_out_of_range`, etc.) and kept in the silver layer. An `is_valid`
column marks the conjunction of hard-fail rules. Gold models filter on
`is_valid`, but the original rows remain queryable in silver.

Soft flags (null passengers, negative fares, unknown zones) do **not** set
`is_valid = false`. They are kept for downstream analysts to filter by choice,
not by accident.

## Consequences

**Benefits:**

- **Auditability.** Every row is accounted for. A revenue reconciliation
  between bronze and gold can explain every dollar of difference by pointing
  at the quarantine reason.
- **Reversibility.** If a rule is wrong (e.g. we later learn that negative fares
  include legitimate adjustments, which they do), rows can be recovered without
  re-ingesting from source.
- **Observability.** DQ metrics per rule per run are a simple `GROUP BY` on the
  flag columns. A spike in quarantined rows is an early warning of upstream
  schema drift.

**Trade-offs:**

- Silver tables are larger (~0.03% overhead from quarantined rows).
- Downstream consumers must use gold or explicitly filter on `is_valid`. This
  is intentional: it forces a conscious decision about which rows to include.

## Alternatives considered

- **Great Expectations / Soda:** would add a dependency and a separate test
  framework. For this project's scale, dbt tests plus boolean columns achieve
  the same outcome with less tooling. In production with multiple teams
  contributing pipelines, a dedicated DQ framework becomes worthwhile.
- **Silent filtering:** rejected. A dropped row is invisible. A quarantined row
  has a reason code.
