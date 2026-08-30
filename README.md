# NYC Taxi × Weather — Data Engineering Case

> **Status: scaffold.** Replace this block with your own findings as you go.
> The structure below is deliberate: a reviewer should get the decisions, the
> numbers, and a working `make all` inside the first minute.

## TL;DR

*(One paragraph: what you built, the headline finding with a real number, and
the single most interesting problem you hit.)*

## Run it

```bash
python -m venv .venv && source .venv/bin/activate   # WSL / macOS / Linux
make setup
make all          # ingest → load → dbt build → tests → charts   (~5 min cold)
```

No cloud account required. `make databricks` runs the *identical* dbt models
against Databricks Free Edition to show the code is portable.

## Architecture

See [`docs/architecture.md`](docs/architecture.md). Decisions and their
trade-offs are recorded in [`docs/adr/`](docs/adr/).

## The timezone contract

TLC publishes **naive America/New_York wall-clock time**. Open-Meteo serves
**UTC**. Joining them without an explicit contract shifts every record by 4–5
hours and produces a confidently wrong answer.

The contract is declared in exactly two places and nowhere else:

| Path | Definition |
|---|---|
| Python | `src/taxi/timestamps.py` |
| SQL | `dbt/macros/cross_engine.sql` (`local_to_utc` / `utc_to_local`) |

DST is handled explicitly: the spring-forward gap yields local times that do
not exist (invalid → quarantined), and the fall-back hour occurs twice (valid,
resolved to the first instance, flagged in the DQ metrics).
`tests/test_timestamps.py` covers both transitions.

## Data quality

Rows are **flagged and quarantined, never silently dropped** — negative fares
are legitimate refunds, and dropping them loses revenue you cannot later
reconcile. See [`docs/data_quality.md`](docs/data_quality.md) for the rule set
and the observed counts.

## Analysis

*(Your finding. Aim for something with a decision attached — e.g. which zones
become supply-constrained in wet hours — not "it rains, fewer trips".)*

## What I would do differently at scale

*(Short, honest, specific. This section is read closely.)*
