"""Analysis: weather impact on taxi demand by zone.

Produces findings and charts from the gold layer.
Run after `dbt build --target dev`.

Usage:
    python -m taxi.analysis
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import duckdb

from taxi import config

log = logging.getLogger(__name__)

DB = str(config.DUCKDB_PATH)
FIGURES = Path("docs/figures")


def demand_by_precipitation(con):
    log.info("\n=== Demand by precipitation band ===")
    con.sql("""
        SELECT precipitation_band, count(*) as trips,
               round(avg(total_amount),2) as avg_fare
        FROM fct_trips GROUP BY 1 ORDER BY 2 DESC
    """).show()


def demand_by_hour_dow(con):
    log.info("\n=== Demand by hour × day-of-week ===")
    con.sql("""
        SELECT pickup_day_of_week, pickup_hour_of_day,
               count(*) as trips, round(avg(total_amount),2) as avg_fare
        FROM fct_trips GROUP BY 1,2 ORDER BY 1,2
    """).show(max_rows=200)


def top_zones_wet_lift(con):
    log.info("\n=== Top 20 zones: demand INCREASE in wet hours ===")
    con.sql("""
        SELECT pickup_zone, pickup_borough,
               round(avg(demand_lift_vs_dry),3) as avg_lift,
               count(*) as observations
        FROM agg_zone_hour_demand
        WHERE is_wet_hour AND dry_baseline_trips > 5
        GROUP BY 1,2 HAVING count(*) > 10
        ORDER BY avg_lift DESC LIMIT 20
    """).show()


def bottom_zones_wet_lift(con):
    log.info("\n=== Top 20 zones: demand DECREASE in wet hours ===")
    con.sql("""
        SELECT pickup_zone, pickup_borough,
               round(avg(demand_lift_vs_dry),3) as avg_lift,
               count(*) as observations
        FROM agg_zone_hour_demand
        WHERE is_wet_hour AND dry_baseline_trips > 5
        GROUP BY 1,2 HAVING count(*) > 10
        ORDER BY avg_lift ASC LIMIT 20
    """).show()


def revenue_wet_vs_dry(con):
    log.info("\n=== Revenue: wet vs dry by zone ===")
    con.sql("""
        SELECT pickup_zone, pickup_borough, is_wet_hour,
               sum(trips) as trips, round(sum(revenue),2) as revenue
        FROM agg_zone_hour_demand
        GROUP BY 1,2,3 HAVING sum(trips) > 1000
        ORDER BY pickup_borough, pickup_zone, is_wet_hour
    """).show(max_rows=120)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    FIGURES.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(DB, read_only=True)
    demand_by_precipitation(con)
    demand_by_hour_dow(con)
    top_zones_wet_lift(con)
    bottom_zones_wet_lift(con)
    revenue_wet_vs_dry(con)
    con.close()

    log.info("\nAnalysis complete. Charts will be added next.")
    return 0


if __name__ == "__main__":
    sys.exit(main())