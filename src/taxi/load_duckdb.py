"""Register the raw files as bronze tables in DuckDB, applying the timestamp
contract and nothing else. Everything after this point is dbt SQL.
"""
from __future__ import annotations

import logging
import sys

import duckdb
import pandas as pd

from taxi import config
from taxi.timestamps import add_normalised

log = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config.DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DUCKDB_PATH))
    con.execute("SET TimeZone='UTC'")
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    trips_glob = str(config.RAW_DIR / "trips" / "*.parquet")
    con.execute(
        f"CREATE OR REPLACE TABLE bronze.trips AS "
        f"SELECT *, '{{}}' AS _ingested_from FROM read_parquet('{trips_glob}', union_by_name=true)"
    )
    log.info("bronze.trips: %s rows", con.sql("SELECT count(*) FROM bronze.trips").fetchone()[0])

    zones = str(config.RAW_DIR / "reference" / "taxi_zone_lookup.csv")
    con.execute(f"CREATE OR REPLACE TABLE bronze.taxi_zones AS SELECT * FROM read_csv_auto('{zones}')")

    weather_glob = str(config.RAW_DIR / "weather" / "*.parquet")
    wx = con.sql(f"SELECT * FROM read_parquet('{weather_glob}')").df()
    wx = add_normalised(wx, "observed_at_raw", config.WEATHER_SOURCE_TZ, prefix="observed_at")
    con.register("wx_df", wx)
    con.execute("CREATE OR REPLACE TABLE bronze.weather AS SELECT * FROM wx_df")
    log.info("bronze.weather: %s rows", len(wx))

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
