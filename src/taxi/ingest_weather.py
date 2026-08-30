"""Bronze: hourly ERA5 reanalysis for NYC from the Open-Meteo archive API.

Data licensed CC BY 4.0 (open-meteo.com). Free for non-commercial use.
In production I would use NOAA ISD/LCD station observations for auditability
and keep reanalysis for backfill only -- see docs/adr/0003-weather-source.md.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

import pandas as pd

from taxi import config

log = logging.getLogger(__name__)


def month_bounds(month: str) -> tuple[str, str]:
    """Pad by one day each side so the UTC<->local shift can never clip an edge."""
    start = date.fromisoformat(f"{month}-01")
    nxt = date(start.year + (start.month == 12), (start.month % 12) + 1, 1)
    return str(start - timedelta(days=1)), str(nxt)


def fetch(start: str, end: str) -> pd.DataFrame:
    params = {
        "latitude": config.NYC_LAT,
        "longitude": config.NYC_LON,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(config.WEATHER_HOURLY),
        "timezone": "UTC",  # explicit, never implicit
    }
    url = f"{config.WEATHER_URL}?{urllib.parse.urlencode(params)}"
    log.info("fetching weather %s .. %s", start, end)
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310
        payload = json.load(r)
    df = pd.DataFrame(payload["hourly"])
    df = df.rename(columns={"time": "observed_at_raw"})
    df["source"] = "open-meteo-archive-era5"
    df["latitude"] = payload["latitude"]
    df["longitude"] = payload["longitude"]
    return df


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--months", default=",".join(config.TRIP_MONTHS))
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    out_dir = config.RAW_DIR / "weather"
    out_dir.mkdir(parents=True, exist_ok=True)
    for month in args.months.split(","):
        month = month.strip()
        df = fetch(*month_bounds(month))
        dest = out_dir / f"weather_{month}.parquet"
        df.to_parquet(dest, index=False)
        log.info("wrote %s rows -> %s", len(df), dest.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
