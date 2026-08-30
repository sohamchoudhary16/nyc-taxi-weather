# ADR 0001 — DuckDB locally, Databricks in the cloud, one dbt project

**Status:** accepted

## Context
The brief asks for a production-ready, flexible solution but explicitly does
not want costly cloud compute. A reviewer should be able to run the project
without provisioning anything.

## Decision
Write all transformations as dbt models with two targets: `dbt-duckdb` for the
local path and `dbt-databricks` (Free Edition, serverless) for the cloud
mirror. Engine differences are confined to `macros/cross_engine.sql`.

## Consequences
* A reviewer can clone and `make all` with no account and no credentials.
* Cloud fluency is still demonstrated, and if the Free Edition quota is hit
  mid-demo, nothing is blocked.
* Cost: a small dialect-compatibility surface to maintain in the macros. In a
  real deployment I would pick one engine; portability here is a reviewer-
  experience decision, not an architectural recommendation.
