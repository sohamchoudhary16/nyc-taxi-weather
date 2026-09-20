"""Generate a minimal synthetic dataset for CI.

CI must not depend on external downloads or cloud credentials. This module
creates a tiny DuckDB with realistic-enough bronze tables for `dbt build`
to compile and pass all tests.

Usage:
    PYTHONPATH=src python -m taxi.fixtures
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

import duckdb
import pandas as pd

from taxi import config
from taxi.timestamps import add_normalised


def main() -> int:
    config.DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DUCKDB_PATH))
    con.execute("SET TimeZone='UTC'")
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    # -- Synthetic trips (20 rows, spans one day) --------------------------
    base = datetime(2024, 1, 15, 8, 0, 0)
    trips = pd.DataFrame({
        "VendorID": [1, 2] * 10,
        "tpep_pickup_datetime": [
            base + timedelta(minutes=i * 30) for i in range(20)
        ],
        "tpep_dropoff_datetime": [
            base + timedelta(minutes=i * 30 + 15) for i in range(20)
        ],
        "passenger_count": [1, 2, 3, 1, 2] * 4,
        "trip_distance": [1.5, 3.2, 0.8, 5.1, 2.0] * 4,
        "PULocationID": [161, 237, 236, 132, 48] * 4,
        "DOLocationID": [237, 161, 48, 236, 132] * 4,
        "fare_amount": [8.0, 15.5, 5.0, 22.0, 10.0] * 4,
        "extra": [0.5] * 20,
        "mta_tax": [0.5] * 20,
        "tip_amount": [2.0, 3.0, 1.0, 4.0, 2.0] * 4,
        "tolls_amount": [0.0] * 20,
        "improvement_surcharge": [0.3] * 20,
        "total_amount": [11.3, 19.8, 6.8, 27.3, 13.3] * 4,
        "congestion_surcharge": [2.5] * 20,
        "Airport_fee": [0.0] * 20,
        "payment_type": [1, 1, 2, 1, 1] * 4,
    })
    con.register("trips_df", trips)
    con.execute(
        "CREATE OR REPLACE TABLE bronze.trips AS SELECT * FROM trips_df"
    )

    # -- Synthetic zones ---------------------------------------------------
    zones = pd.DataFrame({
        "LocationID": [161, 237, 236, 132, 48, 264, 265],
        "Borough": [
            "Manhattan", "Manhattan", "Manhattan",
            "Queens", "Manhattan", "Unknown", "Unknown",
        ],
        "Zone": [
            "Midtown Center", "Upper East Side South", "Upper East Side North",
            "JFK Airport", "Clinton East", "Unknown", "N/A",
        ],
        "service_zone": [
            "Yellow Zone", "Yellow Zone", "Yellow Zone",
            "Airports", "Yellow Zone", "N/A", "N/A",
        ],
    })
    con.register("zones_df", zones)
    con.execute(
        "CREATE OR REPLACE TABLE bronze.taxi_zones AS SELECT * FROM zones_df"
    )

    # -- Synthetic weather (48 hours covering the trip day) ----------------
    hours = pd.date_range("2024-01-15", periods=48, freq="h", tz="UTC")
    weather = pd.DataFrame({
        "observed_at_raw": hours.strftime("%Y-%m-%dT%H:%M"),
        "temperature_2m": [2.0 + (i % 10) * 0.5 for i in range(48)],
        "apparent_temperature": [0.0 + (i % 10) * 0.4 for i in range(48)],
        "precipitation": [0.0] * 24 + [1.5] * 24,
        "rain": [0.0] * 24 + [1.2] * 24,
        "snowfall": [0.0] * 48,
        "wind_speed_10m": [10.0 + i * 0.2 for i in range(48)],
        "weather_code": [0] * 24 + [61] * 24,
        "source": ["fixture"] * 48,
        "latitude": [40.7128] * 48,
        "longitude": [-74.006] * 48,
    })
    weather = add_normalised(
        weather, "observed_at_raw", "UTC", prefix="observed_at"
    )
    con.register("weather_df", weather)
    con.execute(
        "CREATE OR REPLACE TABLE bronze.weather AS SELECT * FROM weather_df"
    )

    con.close()
    print(f"Fixtures written to {config.DUCKDB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
