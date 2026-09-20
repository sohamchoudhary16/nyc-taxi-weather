"""Bronze: land TLC yellow-taxi parquet + the zone lookup, unmodified.

Bronze is append-only and byte-faithful. No cleaning happens here. If a
transform is wrong we want to re-derive silver, not re-download the source.
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
import urllib.request
from pathlib import Path

from taxi import config

log = logging.getLogger(__name__)


def download(url: str, dest: Path, *, force: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        log.info("cached, skipping: %s", dest.name)
        return dest
    log.info("downloading %s", url)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as f:  # noqa: S310
        shutil.copyfileobj(resp, f)
    tmp.replace(dest)
    log.info("wrote %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--months", default=",".join(config.TRIP_MONTHS))
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    month_re = re.compile(r"^\d{4}-\d{2}$")
    for month in args.months.split(","):
        month = month.strip()
        if not month_re.match(month):
            log.error("invalid month format %r, expected YYYY-MM", month)
            return 1
        download(
            config.TRIP_URL.format(month=month),
            config.RAW_DIR / "trips" / f"yellow_tripdata_{month}.parquet",
            force=args.force,
        )
    download(
        config.ZONE_LOOKUP_URL,
        config.RAW_DIR / "reference" / "taxi_zone_lookup.csv",
        force=args.force,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
