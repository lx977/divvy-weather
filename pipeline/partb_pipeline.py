"""Part B ETL: Divvy trips (Sep 2024 - Sep 2026) + Chicago Midway weather.

Each step is one OpenLineage job (see lineage.py):

  clean_trips      partb_data/divvy/*.zip         -> work/trips_clean/
  clean_weather    partb_data/chi_climate/*.csv   -> work/weather_daily
  aggregate_trips  work/trips_clean/              -> work/daily_rides,
                                                     work/hourly_rides,
                                                     work/station_rides,
                                                     work/trip_quality
  join_weather     work/daily_rides + weather     -> work/daily_rides_weather

The reporting step (charts) runs in partb_analysis.ipynb.

Usage:  python partb_pipeline.py            # all steps
        python partb_pipeline.py clean_trips
"""
import glob
import json
import os
import re
import sys
import zipfile

import pandas as pd

from lineage import lineage_run

HERE = os.path.dirname(os.path.abspath(__file__))
HW1 = os.path.dirname(HERE)
DIVVY_DIR = os.path.join(HW1, "partb_data", "divvy")
WEATHER_CSV = os.path.join(HW1, "partb_data", "chi_climate",
                           "USW00014819.csv")
WORK = os.path.join(HERE, "work")
TRIPS_DIR = os.path.join(WORK, "trips_clean")

START, END = "2024-09-01", "2026-09-30"   # study window (inclusive)
MIN_MINUTES, MAX_MINUTES = 1, 24 * 60     # Divvy: < 60 s = false start

# dataset names as they appear in the lineage graph
DS = {
    "divvy_raw": "partb_data/divvy (monthly trip zips)",
    "weather_raw": "partb_data/chi_climate/USW00014819.csv",
    "trips_clean": "partb/work/trips_clean",
    "weather_daily": "partb/work/weather_daily",
    "daily_rides": "partb/work/daily_rides",
    "hourly_rides": "partb/work/hourly_rides",
    "station_rides": "partb/work/station_rides",
    "trip_quality": "partb/work/trip_quality",
    "daily_rides_weather": "partb/work/daily_rides_weather",
}


def path(key):
    """Local parquet path for a work dataset."""
    return os.path.join(WORK, key + ".parquet")


# ------------------------------------------------------------ trips ----
def _read_zip(zip_path):
    """Read the trip CSV inside a monthly zip (ignores __MACOSX files).

    Note: Divvy's 202601 zip contains a file *named* 202501-...csv,
    so the month is taken from the zip name and checked against the data.
    """
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist()
                   if m.endswith(".csv") and not m.startswith("__MACOSX")]
        with zf.open(members[0]) as fh:
            return pd.read_csv(fh, low_memory=False), members[0]


def clean_month(zip_path):
    """Clean one month of trips; returns (clean_df, quality_dict)."""
    month = re.search(r"(\d{6})-divvy", zip_path).group(1)
    raw, inner = _read_zip(zip_path)
    q = {"month": month, "inner_file": inner, "rows_raw": len(raw)}

    df = raw.drop_duplicates("ride_id")
    q["duplicates"] = len(raw) - len(df)
    df = df.assign(
        started_at=pd.to_datetime(df["started_at"], format="mixed"),
        ended_at=pd.to_datetime(df["ended_at"], format="mixed"))
    df["duration_min"] = (df["ended_at"] - df["started_at"]
                          ).dt.total_seconds() / 60
    q["too_short"] = int((df["duration_min"] < MIN_MINUTES).sum())
    q["too_long_or_negative"] = int(
        ((df["duration_min"] > MAX_MINUTES) | df["duration_min"].isna()
         ).sum())
    df = df[df["duration_min"].between(MIN_MINUTES, MAX_MINUTES)]

    # month label check (catches mislabeled files)
    q["label_matches_data"] = bool(
        df["started_at"].dt.strftime("%Y%m").mode()[0] == month)
    q["missing_start_station"] = int(df["start_station_name"].isna().sum())

    df = df.assign(
        date=df["started_at"].dt.normalize(),
        hour=df["started_at"].dt.hour.astype("int8"),
        weekday=df["started_at"].dt.day_name(),
        rideable_type=df["rideable_type"].astype("category"),
        member_casual=df["member_casual"].astype("category"),
    )[["ride_id", "date", "started_at", "hour", "weekday", "rideable_type",
       "member_casual", "duration_min", "start_station_name",
       "end_station_name"]]
    q["rows_clean"] = len(df)
    return df, q


def clean_trips(force=False):
    """Clean every monthly zip into work/trips_clean/<month>.parquet."""
    os.makedirs(TRIPS_DIR, exist_ok=True)
    zips = sorted(glob.glob(os.path.join(DIVVY_DIR, "*-divvy-tripdata.zip")))
    with lineage_run(
            "clean_trips",
            "Read monthly Divvy zips; drop duplicate ride_ids, rides "
            "< 1 min or > 24 h; parse timestamps; add date/hour/weekday "
            "and duration.",
            [DS["divvy_raw"]], [DS["trips_clean"]]) as ctx:
        sample = None
        for zp in zips:
            month = re.search(r"(\d{6})-divvy", zp).group(1)
            out = os.path.join(TRIPS_DIR, f"{month}.parquet")
            qfile = os.path.join(TRIPS_DIR, f"{month}.quality.json")
            if os.path.exists(out) and os.path.exists(qfile) and not force:
                print(f"{month}: cached")
                continue
            df, q = clean_month(zp)
            df.to_parquet(out, index=False)
            with open(qfile, "w", encoding="utf-8") as fh:
                json.dump(q, fh)
            print(f"{month}: {q['rows_raw']:>9,} raw -> "
                  f"{q['rows_clean']:>9,} clean")
            sample = df
        if sample is None:
            sample = pd.read_parquet(sorted(glob.glob(
                os.path.join(TRIPS_DIR, "*.parquet")))[0])
        ctx["schemas"][DS["trips_clean"]] = sample.head(0)
        rows = 0
        for qf in glob.glob(os.path.join(TRIPS_DIR, "*.quality.json")):
            with open(qf, encoding="utf-8") as fh:
                rows += json.load(fh)["rows_clean"]
        ctx["row_counts"][DS["trips_clean"]] = rows


# ---------------------------------------------------------- weather ----
WT_NAMES = {"WT01": "fog", "WT02": "heavy_fog", "WT03": "thunder",
            "WT04": "ice_pellets", "WT05": "hail", "WT06": "glaze",
            "WT07": "dust", "WT08": "haze", "WT09": "blowing_snow",
            "WT10": "tornado"}


def clean_weather():
    """GHCN-Daily Midway -> tidy daily weather in US units."""
    with lineage_run(
            "clean_weather",
            "Filter Midway GHCN-Daily to the study window; drop values "
            "with a QC flag; convert tenths of C / mm / m/s to F / in / "
            "mph; fill TAVG from (TMAX+TMIN)/2; weather-type flags to 0/1; "
            "rain / snow-on-ground flags; temperature band.",
            [DS["weather_raw"]], [DS["weather_daily"]]) as ctx:
        raw = pd.read_csv(WEATHER_CSV, dtype=str)
        ctx["input_schemas"][DS["weather_raw"]] = raw.head(0)
        w = raw[(raw["DATE"] >= START) & (raw["DATE"] <= END)].copy()

        def value(col):
            vals = pd.to_numeric(w[col].str.strip(), errors="coerce")
            attr = w.get(col + "_ATTRIBUTES")
            if attr is not None:  # 2nd attribute = quality flag
                qflag = attr.fillna(",,").str.split(",").str[1]
                vals = vals.where(qflag.fillna("") == "")
            return vals

        out = pd.DataFrame({"date": pd.to_datetime(w["DATE"])})
        out["tmax_f"] = value("TMAX") / 10 * 9 / 5 + 32
        out["tmin_f"] = value("TMIN") / 10 * 9 / 5 + 32
        out["tavg_f"] = (value("TAVG") / 10 * 9 / 5 + 32).fillna(
            (out["tmax_f"] + out["tmin_f"]) / 2)
        out["precip_in"] = value("PRCP") / 10 / 25.4
        out["snow_in"] = value("SNOW") / 25.4
        out["snow_depth_in"] = value("SNWD") / 25.4
        out["wind_mph"] = value("AWND") / 10 * 2.23694
        for code, name in WT_NAMES.items():
            if code in w:
                out[name] = w[code].notna().astype("int8").to_numpy()
        out["rain_day"] = (out["precip_in"] >= 0.1).astype("int8")
        # Midway stopped reporting SNOW (snowfall) in this window, and
        # TAVG is missing too (filled above), so snow is measured as
        # "snow on the ground" from SNWD.
        out["snow_on_ground"] = (out["snow_depth_in"] > 0).astype("int8")
        out["temp_band"] = pd.cut(
            out["tavg_f"], [-100, 32, 50, 65, 80, 150],
            labels=["<32F", "32-50F", "50-65F", "65-80F", "80F+"]
        ).astype(str)
        out.to_parquet(path("weather_daily"), index=False)
        ctx["schemas"][DS["weather_daily"]] = out
        print("weather days:", len(out))


# ------------------------------------------------------- aggregates ----
def aggregate_trips():
    """Monthly parquet -> daily / hourly / station / quality tables."""
    outs = ["daily_rides", "hourly_rides", "station_rides", "trip_quality"]
    with lineage_run(
            "aggregate_trips",
            "Aggregate clean trips to the study window: rides and "
            "duration per day x rider type x bike type, per weekday x "
            "hour, per start station; plus the cleaning quality log.",
            [DS["trips_clean"]], [DS[o] for o in outs]) as ctx:
        daily, hourly, station, quality = [], [], [], []
        for f in sorted(glob.glob(os.path.join(TRIPS_DIR, "*.parquet"))):
            t = pd.read_parquet(f)
            t = t[(t["date"] >= START) & (t["date"] <= END)]
            keys = {"observed": True}
            daily.append(t.groupby(["date", "member_casual",
                                    "rideable_type"], **keys)
                         .agg(rides=("ride_id", "size"),
                              total_min=("duration_min", "sum")))
            hourly.append(t.groupby(["weekday", "hour", "member_casual"],
                                    **keys).size().rename("rides"))
            station.append(t.groupby(["start_station_name",
                                      "member_casual"], **keys)
                           .size().rename("rides"))
            with open(f.replace(".parquet", ".quality.json"),
                      encoding="utf-8") as fh:
                quality.append(json.load(fh))

        def combine(parts):
            return pd.concat(parts).groupby(level=list(
                range(parts[0].index.nlevels)), observed=True).sum()

        tables = {
            "daily_rides": combine(daily).reset_index(),
            "hourly_rides": combine(hourly).reset_index(),
            "station_rides": combine(station).reset_index(),
            "trip_quality": pd.DataFrame(quality),
        }
        tables["daily_rides"]["avg_min"] = (
            tables["daily_rides"]["total_min"] / tables["daily_rides"]
            ["rides"])
        for name, df in tables.items():
            for c in df.select_dtypes("category"):
                df[c] = df[c].astype(str)
            df.to_parquet(path(name), index=False)
            ctx["schemas"][DS[name]] = df
            print(name, df.shape)


def join_weather():
    """Daily rides (wide by rider type) joined with daily weather."""
    with lineage_run(
            "join_weather",
            "Pivot daily rides by rider type and left-join Midway weather "
            "on date -> the reporting table.",
            [DS["daily_rides"], DS["weather_daily"]],
            [DS["daily_rides_weather"]]) as ctx:
        d = pd.read_parquet(path("daily_rides"))
        w = pd.read_parquet(path("weather_daily"))
        wide = d.pivot_table(index="date", columns="member_casual",
                             values="rides", aggfunc="sum").add_suffix(
                                 "_rides")
        wide["total_rides"] = wide.sum(axis=1)
        wide["avg_min"] = (d.groupby("date")["total_min"].sum()
                           / d.groupby("date")["rides"].sum())
        out = wide.reset_index().merge(w, on="date", how="left")
        out["weekday"] = out["date"].dt.day_name()
        out["is_weekend"] = out["date"].dt.dayofweek.ge(5).astype("int8")
        out["month"] = out["date"].dt.to_period("M").astype(str)
        out.columns.name = None
        out.to_parquet(path("daily_rides_weather"), index=False)
        ctx["schemas"][DS["daily_rides_weather"]] = out
        print("daily_rides_weather", out.shape,
              "| days without weather:", int(out["tavg_f"].isna().sum()))


STEPS = {"clean_trips": clean_trips, "clean_weather": clean_weather,
         "aggregate_trips": aggregate_trips, "join_weather": join_weather}

if __name__ == "__main__":
    os.makedirs(WORK, exist_ok=True)
    for step in (sys.argv[1:] or list(STEPS)):
        print(f"--- {step} ---")
        STEPS[step]()
