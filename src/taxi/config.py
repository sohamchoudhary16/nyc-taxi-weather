"""Single source of truth for paths, endpoints and the timezone contract."""
from __future__ import annotations

import os
from pathlib import Path

# Override with TAXI_DATA_DIR=E:/data if you keep the repo and the data apart.
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("TAXI_DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
DUCKDB_PATH = Path(os.getenv("TAXI_DUCKDB_PATH", DATA_DIR / "warehouse.duckdb"))

# --- Trips -----------------------------------------------------------------
# One month is deliberate: ~3M rows, ~50MB parquet. Enough to be real,
# small enough to iterate in seconds on a laptop.
TRIP_MONTHS = os.getenv("TAXI_MONTHS", "2024-01").split(",")
TRIP_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"
ZONE_LOOKUP_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"

# TLC publishes naive wall-clock time. Stated once, here, and nowhere else.
TRIP_SOURCE_TZ = "America/New_York"

# --- Weather ---------------------------------------------------------------
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
NYC_LAT, NYC_LON = 40.7128, -74.0060
WEATHER_HOURLY = [
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "snowfall",
    "wind_speed_10m",
    "weather_code",
]
# We ask Open-Meteo for UTC explicitly rather than accepting a default,
# then convert in one place. See src/taxi/timestamps.py.
WEATHER_SOURCE_TZ = "UTC"
