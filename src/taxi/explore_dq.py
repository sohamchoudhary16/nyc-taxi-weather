"""Repeatable data-quality exploration.

Run once after `load_duckdb.py` to populate docs/data_quality.md with real
numbers from the actual dataset. Every finding in the report traces back to
a query in this file, so it is auditable and reproducible.

Usage:
    python -m taxi.explore_dq
    python -m taxi.explore_dq --output docs/data_quality.md
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from taxi import config

log = logging.getLogger(__name__)


@dataclass
class Finding:
    rule: str
    columns: str
    action: str
    count: int
    total: int

    @property
    def pct(self) -> str:
        if self.total == 0:
            return "0.00"
        return f"{100.0 * self.count / self.total:.2f}"


@dataclass
class DQReport:
    total_rows: int = 0
    weather_rows: int = 0
    weather_min: str = ""
    weather_max: str = ""
    trip_min: str = ""
    trip_max: str = ""
    in_month: int = 0
    findings: list[Finding] = field(default_factory=list)

    def add(self, rule: str, columns: str, action: str, count: int) -> None:
        self.findings.append(Finding(rule, columns, action, count, self.total_rows))
        log.info("  %-40s %8d  (%s%%)", rule, count, self.findings[-1].pct)


def run_checks(con: duckdb.DuckDBPyConnection) -> DQReport:
    """Run every DQ check and return a structured report."""
    r = DQReport()

    # --- Dataset shape ---
    r.total_rows = con.sql("SELECT count(*) FROM bronze.trips").fetchone()[0]
    log.info("Total trip rows: %d", r.total_rows)

    row = con.sql(
        "SELECT min(tpep_pickup_datetime), max(tpep_pickup_datetime) FROM bronze.trips"
    ).fetchone()
    r.trip_min, r.trip_max = str(row[0]), str(row[1])
    log.info("Pickup range: %s .. %s", r.trip_min, r.trip_max)

    row = con.sql(
        "SELECT count(*), min(observed_at_utc), max(observed_at_utc) FROM bronze.weather"
    ).fetchone()
    r.weather_rows = row[0]
    r.weather_min, r.weather_max = str(row[1]), str(row[2])
    log.info("Weather rows: %d  (%s .. %s)", r.weather_rows, r.weather_min, r.weather_max)

    # --- Timestamp checks ---
    row = con.sql("""
        SELECT
            count(*) FILTER (WHERE tpep_pickup_datetime < '2024-01-01')  as before_month,
            count(*) FILTER (WHERE tpep_pickup_datetime >= '2024-02-01') as after_month,
            count(*) FILTER (
                WHERE tpep_pickup_datetime >= '2024-01-01'
                  AND tpep_pickup_datetime <  '2024-02-01'
            ) as in_month
        FROM bronze.trips
    """).fetchone()
    r.in_month = row[2]
    r.add("Pickup before file month (< 2024-01-01)", "tpep_pickup_datetime", "quarantine", row[0])
    r.add("Pickup after file month (>= 2024-02-01)", "tpep_pickup_datetime", "quarantine", row[1])

    # --- Duration checks ---
    count = con.sql("""
        SELECT count(*) FROM bronze.trips
        WHERE tpep_dropoff_datetime <= tpep_pickup_datetime
    """).fetchone()[0]
    r.add("Dropoff not after pickup (duration <= 0)", "pickup/dropoff", "quarantine", count)

    count = con.sql("""
        SELECT count(*) FROM bronze.trips
        WHERE date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime) > 86400
    """).fetchone()[0]
    r.add("Duration exceeds 24 hours", "pickup/dropoff", "quarantine", count)

    # --- Passenger checks ---
    count = con.sql("""
        SELECT count(*) FROM bronze.trips
        WHERE passenger_count IS NULL OR passenger_count = 0
    """).fetchone()[0]
    r.add("Passenger count 0 or null", "passenger_count", "flag (keep)", count)

    count = con.sql("""
        SELECT count(*) FROM bronze.trips WHERE passenger_count > 6
    """).fetchone()[0]
    r.add("Passenger count > 6 (yellow cab max)", "passenger_count", "flag (keep)", count)

    # --- Distance checks ---
    count = con.sql("""
        SELECT count(*) FROM bronze.trips
        WHERE trip_distance = 0 AND fare_amount > 0
    """).fetchone()[0]
    r.add("Zero distance with non-zero fare", "trip_distance/fare", "flag (keep)", count)

    count = con.sql("""
        SELECT count(*) FROM bronze.trips WHERE trip_distance > 500
    """).fetchone()[0]
    r.add("Distance > 500 miles (implausible)", "trip_distance", "quarantine", count)

    # --- Fare checks ---
    count = con.sql("""
        SELECT count(*) FROM bronze.trips WHERE fare_amount < 0
    """).fetchone()[0]
    r.add("Negative fare (likely refund)", "fare_amount", "flag (keep)", count)

    count = con.sql("""
        SELECT count(*) FROM bronze.trips WHERE total_amount < 0
    """).fetchone()[0]
    r.add("Negative total amount", "total_amount", "flag (keep)", count)

    count = con.sql("""
        SELECT count(*) FROM bronze.trips WHERE total_amount > 1000
    """).fetchone()[0]
    r.add("Total amount > $1000", "total_amount", "flag (keep)", count)

    # --- Zone checks ---
    count = con.sql("""
        SELECT count(*) FROM bronze.trips
        WHERE PULocationID IN (264, 265) OR DOLocationID IN (264, 265)
    """).fetchone()[0]
    r.add("Unknown zone (264/265)", "PU/DOLocationID", "flag (keep)", count)

    # --- Fare reconciliation ---
    count = con.sql("""
        SELECT count(*) FROM bronze.trips
        WHERE abs(
            total_amount - (fare_amount + extra + mta_tax
                + coalesce(improvement_surcharge,0)
                + tip_amount + tolls_amount
                + coalesce(congestion_surcharge,0)
                + coalesce(Airport_fee,0))
        ) > 0.01
        AND total_amount > 0
    """).fetchone()[0]
    r.add("Total != sum of components (> $0.01 gap)", "fare columns", "flag (keep)", count)

    # --- Duplicate check ---
    count = con.sql("""
        WITH ranked AS (
            SELECT row_number() OVER (
                PARTITION BY VendorID, tpep_pickup_datetime, tpep_dropoff_datetime,
                             PULocationID, DOLocationID, total_amount
                ORDER BY trip_distance DESC
            ) as rn
            FROM bronze.trips
        )
        SELECT count(*) FROM ranked WHERE rn > 1
    """).fetchone()[0]
    r.add("Exact duplicate rows", "composite key", "quarantine", count)

    # --- Extremes for the report ---
    log.info("\n--- Extremes ---")
    con.sql("""
        SELECT
            max(trip_distance)  as max_distance_mi,
            max(total_amount)   as max_total_usd,
            max(tip_amount)     as max_tip_usd,
            max(passenger_count) as max_passengers
        FROM bronze.trips
    """).show()

    con.sql("""
        SELECT passenger_count, count(*) as n
        FROM bronze.trips
        GROUP BY 1 ORDER BY 1
    """).show()

    con.sql("SUMMARIZE bronze.trips").show()

    return r


def render_markdown(r: DQReport) -> str:
    """Produce the docs/data_quality.md content from observed numbers."""
    lines = [
        "# Data Quality Report",
        "",
        "Generated by `python -m taxi.explore_dq`. Every number below comes from",
        "a reproducible query in `src/taxi/explore_dq.py`.",
        "",
        "## Dataset overview",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total trip rows | {r.total_rows:,} |",
        f"| Pickup range | {r.trip_min} .. {r.trip_max} |",
        f"| Rows within expected month | {r.in_month:,} |",
        f"| Weather rows | {r.weather_rows:,} |",
        f"| Weather range | {r.weather_min} .. {r.weather_max} |",
        "",
        "## Findings",
        "",
        "Rows are **flagged and quarantined, never silently dropped.** Negative fares",
        "are legitimate refunds — dropping them loses revenue that cannot later be",
        "reconciled. Each quarantined row carries a `failure_reason` so it can be",
        "counted, investigated, and replayed if a rule is corrected.",
        "",
        "| Rule | Column(s) | Action | Count | % |",
        "|---|---|---|---|---|",
    ]
    for f in r.findings:
        lines.append(f"| {f.rule} | {f.columns} | {f.action} | {f.count:,} | {f.pct}% |")

    lines += [
        "",
        "## Why quarantine rather than filter",
        "",
        "A dropped row is invisible. A quarantined row has a `failure_reason`, gets",
        "counted in the DQ metrics table, and can be replayed after a rule is fixed.",
        "Silently filtering is how you lose revenue you cannot reconcile.",
        "",
        "## Approach",
        "",
        "Each DQ rule is expressed as a named boolean column in `stg_trips.sql`",
        "(e.g. `dq_non_positive_duration`, `dq_pickup_out_of_range`). The `is_valid`",
        "flag is the conjunction of the hard-fail rules; soft flags (zero passengers,",
        "negative fares) are kept for downstream filtering decisions.",
        "",
        "In production I would emit a DQ metrics table per pipeline run (rows in,",
        "rows passed, rows quarantined by rule) and alert on drift — a sudden spike",
        "in quarantined rows usually means a schema change upstream, not a data",
        "quality improvement.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("docs/data_quality.md"),
        help="Where to write the markdown report",
    )
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    report = run_checks(con)
    con.close()

    md = render_markdown(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    log.info("\nReport written to %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
