"""Canonical timestamp normalisation.

The NYC TLC trip files store *naive local wall-clock time* for America/New_York.
The Open-Meteo archive serves UTC unless told otherwise. Joining them without
an explicit timezone contract silently shifts every record by 4-5 hours.

This module defines the one place in the codebase where a timestamp becomes
canonical. Every source declares its own timezone; everything downstream is
stored as UTC plus a retained local-time column for business reporting
("revenue on Tuesday" means Tuesday in New York, not Tuesday in UTC).

Design decisions:
  * Never raise on bad input. Return a reason code so the row can be
    quarantined and counted, not silently dropped.
  * DST spring-forward produces local times that do not exist. Those are
    invalid data, not something to paper over.
  * DST fall-back produces local times that occur twice. Those are valid;
    we resolve deterministically to the first (DST) occurrence and flag it,
    so the ambiguity is visible in the DQ metrics rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

import pandas as pd

# Reason codes. Kept as constants so dbt tests and dashboards can reference
# them without string drift.
OK = "ok"
OK_AMBIGUOUS = "ok_ambiguous_dst_fallback"
UNPARSEABLE = "unparseable"
NONEXISTENT = "nonexistent_local_time_dst_gap"
OUT_OF_RANGE = "out_of_plausible_range"
NULL_INPUT = "null"

DEFAULT_MIN = pd.Timestamp("2009-01-01", tz="UTC")
DEFAULT_MAX = pd.Timestamp("2030-01-01", tz="UTC")


@dataclass(frozen=True)
class NormalisedTimestamps:
    """Column-wise result. Attach these to the frame; do not filter here."""

    utc: pd.Series  # tz-aware UTC, NaT where invalid
    local: pd.Series  # naive wall-clock in source_tz, NaT where invalid
    is_valid: pd.Series  # bool
    reason: pd.Series  # str, one of the codes above

    def to_frame(self, prefix: str) -> pd.DataFrame:
        return pd.DataFrame(
            {
                f"{prefix}_utc": self.utc,
                f"{prefix}_local": self.local,
                f"{prefix}_is_valid": self.is_valid,
                f"{prefix}_reason": self.reason,
            }
        )


def normalise(
    values: pd.Series,
    source_tz: str,
    *,
    min_ts: pd.Timestamp = DEFAULT_MIN,
    max_ts: pd.Timestamp = DEFAULT_MAX,
) -> NormalisedTimestamps:
    """Coerce a series of timestamps to canonical UTC.

    Args:
        values: strings, datetimes, or a mix. Naive values are interpreted as
            wall-clock time in ``source_tz``. Aware values are converted.
        source_tz: IANA name, e.g. "America/New_York" or "UTC". Required and
            explicit by design -- an implicit default is how the 5-hour bug
            gets in.
        min_ts / max_ts: plausibility window. TLC files genuinely contain
            records dated 2002 and 2090.
    """
    tz = ZoneInfo(source_tz)
    parsed = pd.to_datetime(values, errors="coerce", format="mixed")

    reason = pd.Series(OK, index=parsed.index, dtype="object")
    reason[values.isna()] = NULL_INPUT
    reason[parsed.isna() & values.notna()] = UNPARSEABLE

    if isinstance(parsed.dtype, pd.DatetimeTZDtype):
        utc = parsed.dt.tz_convert("UTC")
    else:
        # Two passes: the strict pass tells us which local times are
        # nonexistent or ambiguous; the lenient pass gives us usable values
        # for the ambiguous ones.
        strict = parsed.dt.tz_localize(tz, nonexistent="NaT", ambiguous="NaT")
        lenient = parsed.dt.tz_localize(tz, nonexistent="NaT", ambiguous=True)

        gap = parsed.notna() & lenient.isna()
        ambiguous = parsed.notna() & strict.isna() & lenient.notna()

        reason[gap] = NONEXISTENT
        reason[ambiguous] = OK_AMBIGUOUS
        utc = lenient.dt.tz_convert("UTC")

    out_of_range = utc.notna() & ((utc < min_ts) | (utc >= max_ts))
    reason[out_of_range] = OUT_OF_RANGE
    utc = utc.mask(out_of_range)

    is_valid = reason.isin([OK, OK_AMBIGUOUS]) & utc.notna()
    utc = utc.where(is_valid)
    local = utc.dt.tz_convert(tz).dt.tz_localize(None)

    return NormalisedTimestamps(utc=utc, local=local, is_valid=is_valid, reason=reason)


def add_normalised(
    df: pd.DataFrame, column: str, source_tz: str, *, prefix: str | None = None
) -> pd.DataFrame:
    """Non-destructive: returns a copy with four extra columns."""
    result = normalise(df[column], source_tz)
    return pd.concat([df, result.to_frame(prefix or column)], axis=1)
