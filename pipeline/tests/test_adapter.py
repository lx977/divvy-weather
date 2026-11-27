"""The adapter maps every Divvy file format to the same columns.

Fixtures are the first 500 rides of two real Divvy files:
  Divvy_Trips_2019_Q2.zip    quarterly, "01 - Rental Details ..." headers
  202409-divvy-tripdata.zip  current monthly format (has e-scooters)

Run:  python pipeline/tests/test_adapter.py   (or: pytest pipeline/tests)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))
import pipeline as pl  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
CLEAN_COLS = ["ride_id", "date", "started_at", "hour", "weekday",
              "rideable_type", "member_casual", "duration_min",
              "start_station_id", "start_station_name", "end_station_id",
              "end_station_name", "start_lat", "start_lng", "end_lat",
              "end_lng"]


def check(zip_name, label, months):
    """Same clean columns and valid values for one fixture."""
    zp = os.path.join(FIX, zip_name)
    assert pl.file_label(zp) == label
    assert pl.label_months(label) == months
    raw, _ = pl.read_zip(zp)
    assert list(pl.standardize(raw).columns) == pl.STANDARD
    df, q = pl.clean_file(zp)
    assert list(df.columns) == CLEAN_COLS
    assert set(df["member_casual"]) <= {"member", "casual"}
    assert df["duration_min"].between(1, 1440).all()
    assert q["label_matches_data"]
    assert q["rows_clean"] == len(df) > 0
    return df, q


def test_legacy_2019_q2():
    df, _ = check("Divvy_Trips_2019_Q2.zip", "2019_Q2",
                  ["201904", "201905", "201906"])
    assert set(df["rideable_type"]) == {"classic_bike"}
    assert df["start_station_id"].notna().all()
    assert not df["start_station_id"].str.endswith(".0").any()
    assert df["start_lat"].isna().all()      # no coordinates before 2020


def test_current_202409():
    df, q = check("202409-divvy-tripdata.zip", "202409", ["202409"])
    assert q["scooters_dropped"] > 0
    assert "electric_scooter" not in set(df["rideable_type"])
    assert df["start_lat"].notna().all()


if __name__ == "__main__":
    test_legacy_2019_q2()
    test_current_202409()
    print("adapter tests passed")
