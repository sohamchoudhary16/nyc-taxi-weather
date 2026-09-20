import pandas as pd
import pytest

from taxi import timestamps as ts

NY = "America/New_York"


def _norm(values, tz=NY):
    return ts.normalise(pd.Series(values), tz)


def test_naive_local_time_is_offset_correctly():
    # 2024-01-15 09:00 in New York (EST, UTC-5) is 14:00 UTC.
    r = _norm(["2024-01-15 09:00:00"])
    assert r.utc.iloc[0] == pd.Timestamp("2024-01-15 14:00:00", tz="UTC")
    assert r.local.iloc[0] == pd.Timestamp("2024-01-15 09:00:00")
    assert bool(r.is_valid.iloc[0])


def test_summer_offset_differs_from_winter():
    # July is EDT (UTC-4), not EST. A fixed -5 offset would be an hour out.
    r = _norm(["2024-07-15 09:00:00"])
    assert r.utc.iloc[0] == pd.Timestamp("2024-07-15 13:00:00", tz="UTC")


def test_dst_gap_is_flagged_not_silently_shifted():
    # 02:30 on 2024-03-10 does not exist in New York.
    r = _norm(["2024-03-10 02:30:00"])
    assert r.reason.iloc[0] == ts.NONEXISTENT
    assert not bool(r.is_valid.iloc[0])
    assert pd.isna(r.utc.iloc[0])


def test_dst_fallback_is_valid_but_flagged():
    # 01:30 on 2024-11-03 happens twice. Resolve to the first (EDT) instance.
    r = _norm(["2024-11-03 01:30:00"])
    assert r.reason.iloc[0] == ts.OK_AMBIGUOUS
    assert bool(r.is_valid.iloc[0])
    assert r.utc.iloc[0] == pd.Timestamp("2024-11-03 05:30:00", tz="UTC")


def test_round_trip_is_stable_across_a_full_year():
    local = pd.date_range("2024-01-01", "2024-12-31", freq="7h")
    r = _norm(list(local.strftime("%Y-%m-%d %H:%M:%S")))
    valid = r.is_valid
    assert (r.local[valid] == pd.Series(local)[valid]).all()


def test_out_of_range_rows_are_quarantined():
    r = _norm(["2002-01-01 00:00:00", "2090-06-01 00:00:00", "2024-06-01 00:00:00"])
    assert list(r.reason) == [ts.OUT_OF_RANGE, ts.OUT_OF_RANGE, ts.OK]
    assert list(r.is_valid) == [False, False, True]


def test_garbage_and_nulls_do_not_raise():
    r = _norm(["not a date", None, "2024-06-01 00:00:00"])
    assert list(r.reason) == [ts.UNPARSEABLE, ts.NULL_INPUT, ts.OK]


def test_aware_input_is_converted_not_relocalised():
    r = _norm(["2024-01-15T14:00:00+00:00"], tz=NY)
    assert r.utc.iloc[0] == pd.Timestamp("2024-01-15 14:00:00", tz="UTC")
    assert r.local.iloc[0] == pd.Timestamp("2024-01-15 09:00:00")


def test_utc_source_is_left_alone():
    r = _norm(["2024-01-15 14:00:00"], tz="UTC")
    assert r.utc.iloc[0] == pd.Timestamp("2024-01-15 14:00:00", tz="UTC")


def test_add_normalised_is_non_destructive():
    df = pd.DataFrame({"pickup": ["2024-01-15 09:00:00"], "fare": [12.5]})
    out = ts.add_normalised(df, "pickup", NY)
    assert list(df.columns) == ["pickup", "fare"]
    assert "pickup_utc" in out.columns and "pickup_reason" in out.columns


@pytest.mark.parametrize(
    "raw",
    ["2024-01-15 09:00:00", "2024-01-15T09:00:00", "01/15/2024 09:00:00 AM"],
)
def test_mixed_input_formats_land_on_the_same_instant(raw):
    assert _norm([raw]).utc.iloc[0] == pd.Timestamp("2024-01-15 14:00:00", tz="UTC")


def test_empty_series_returns_empty_results():
    r = ts.normalise(pd.Series([], dtype="object"), NY)
    assert len(r.utc) == 0
    assert len(r.local) == 0
    assert len(r.is_valid) == 0
    assert len(r.reason) == 0


def test_all_null_series():
    r = _norm([None, None, None])
    assert list(r.reason) == [ts.NULL_INPUT, ts.NULL_INPUT, ts.NULL_INPUT]
    assert not r.is_valid.any()
    assert r.utc.isna().all()


def test_boundary_at_min_ts_is_valid():
    r = ts.normalise(
        pd.Series(["2009-01-01 00:00:00"]),
        "UTC",
        min_ts=pd.Timestamp("2009-01-01", tz="UTC"),
        max_ts=pd.Timestamp("2030-01-01", tz="UTC"),
    )
    assert r.reason.iloc[0] == ts.OK
    assert bool(r.is_valid.iloc[0])


def test_boundary_at_max_ts_is_quarantined():
    r = ts.normalise(
        pd.Series(["2030-01-01 00:00:00"]),
        "UTC",
        min_ts=pd.Timestamp("2009-01-01", tz="UTC"),
        max_ts=pd.Timestamp("2030-01-01", tz="UTC"),
    )
    assert r.reason.iloc[0] == ts.OUT_OF_RANGE
    assert not bool(r.is_valid.iloc[0])


def test_custom_min_max_narrows_window():
    r = ts.normalise(
        pd.Series(["2024-01-15 12:00:00", "2024-03-01 12:00:00"]),
        "UTC",
        min_ts=pd.Timestamp("2024-01-01", tz="UTC"),
        max_ts=pd.Timestamp("2024-02-01", tz="UTC"),
    )
    assert r.reason.iloc[0] == ts.OK
    assert bool(r.is_valid.iloc[0])
    assert r.reason.iloc[1] == ts.OUT_OF_RANGE
    assert not bool(r.is_valid.iloc[1])
