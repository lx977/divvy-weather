"""Weather-Ready Divvy pipeline: Divvy trips + Chicago Midway weather +
Divvy station capacity -> small hand-off tables for Tableau and Streamlit.

Settings come from config.yaml; raw-data paths from config.local.yaml
(git-ignored; copy config.local.example.yaml). Every step is one
OpenLineage job (lineage.py) and one DVC stage (dvc.yaml).

  step            reads                         writes
  clean_trips     raw Divvy zips (any format)   interim/trips_clean/
  clean_weather   raw NOAA CSV                  interim/weather_daily
  fetch_gbfs      GBFS feed (manual, network)   raw/gbfs_..._<date>.json
  match_stations  trips_clean + GBFS snapshot   processed/station_match
  aggregate_trips trips_clean + station_match   processed/daily_rides,
                  + community areas             hourly_rides, station_rides,
                                                area_rides, trip_quality
  join_weather    daily_rides + weather         processed/daily_rides_weather
                  + US holidays
  weather_sensitivity  daily_rides_weather      processed/weather_sensitivity
  export          processed hand-off tables     exports/*.csv

Usage:  python pipeline/pipeline.py              # all steps but fetch_gbfs
        python pipeline/pipeline.py clean_trips --force
        python pipeline/pipeline.py fetch_gbfs   # new dated GBFS snapshot
"""
import glob
import json
import os
import re
import sys
import urllib.request
import zipfile
from datetime import date

import holidays
import numpy as np
import pandas as pd
import yaml
from shapely import STRtree, points
from shapely.geometry import shape

from lineage import lineage_run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config():
    """config.yaml, plus the raw-data paths from config.local.yaml."""
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    local = os.path.join(ROOT, "config.local.yaml")
    if os.path.exists(local):
        with open(local, encoding="utf-8") as fh:
            cfg.update(yaml.safe_load(fh))
    return cfg


def raw_path(key):
    """Raw-data path from config.local.yaml (required for raw steps)."""
    if "raw" not in CFG:
        sys.exit("config.local.yaml missing. Run:\n"
                 "  cp config.local.example.yaml config.local.yaml\n"
                 "and point it at your raw Divvy zips and NOAA CSV.")
    return p(CFG["raw"][key])


CFG = load_config()
START, END = CFG["window"]["start"], CFG["window"]["end"]
CLEAN = CFG["cleaning"]


def p(*parts):
    """Path relative to the repo root (absolute paths pass through)."""
    return os.path.normpath(os.path.join(ROOT, *parts))


INTERIM, PROCESSED, EXPORTS = (p(CFG["paths"][k]) for k in
                               ("interim", "processed", "exports"))
TRIPS_DIR = os.path.join(INTERIM, "trips_clean")
HANDOFF = ["daily_rides_weather", "hourly_rides", "station_rides",
           "trip_quality", "station_match", "area_rides",
           "weather_sensitivity"]                    # exported to CSV


def out(name):
    """Parquet path: hand-off tables in processed/, the rest in interim/."""
    folder = PROCESSED if name in HANDOFF + ["daily_rides"] else INTERIM
    return os.path.join(folder, name + ".parquet")


def ds(name):
    """Dataset name as shown in the lineage graph (repo-relative)."""
    return os.path.relpath(out(name), ROOT).replace(".parquet", "")


DS_DIVVY, DS_NOAA = "raw/divvy (trip zips)", "raw/noaa/USW00014819.csv"
DS_TRIPS = "data/interim/trips_clean"
DS_GBFS = CFG["stations"]["gbfs_snapshot"]
DS_AREAS = CFG["community_areas"]


# ------------------------------------------------------- trip adapter ----
# Every Divvy file format is renamed to the current (2020+) schema.
STANDARD = ["ride_id", "rideable_type", "started_at", "ended_at",
            "start_station_name", "start_station_id", "end_station_name",
            "end_station_id", "start_lat", "start_lng", "end_lat", "end_lng",
            "member_casual"]
# 2013-2019 quarterly files; 2018 Q1 and 2019 Q2 use "01 - ..." headers
LEGACY_NAMES = {
    "trip_id": "ride_id", "01 - Rental Details Rental ID": "ride_id",
    "start_time": "started_at", "starttime": "started_at",
    "01 - Rental Details Local Start Time": "started_at",
    "end_time": "ended_at", "stoptime": "ended_at",
    "01 - Rental Details Local End Time": "ended_at",
    "from_station_id": "start_station_id",
    "03 - Rental Start Station ID": "start_station_id",
    "from_station_name": "start_station_name",
    "03 - Rental Start Station Name": "start_station_name",
    "to_station_id": "end_station_id",
    "02 - Rental End Station ID": "end_station_id",
    "to_station_name": "end_station_name",
    "02 - Rental End Station Name": "end_station_name",
    "usertype": "member_casual", "User Type": "member_casual",
}
USERTYPE = {"Subscriber": "member", "Customer": "casual",
            "Dependent": "casual"}


def standardize(raw):
    """Map any Divvy trip table to STANDARD columns.

    Pre-2020 files have no bike type (fleet was all classic pedal bikes)
    and no coordinates (left empty), and call rider type Subscriber /
    Customer. Columns outside STANDARD (gender, birth year...) are dropped.
    """
    df = raw.rename(columns=LEGACY_NAMES)
    if "rideable_type" not in df:
        df["rideable_type"] = "classic_bike"
    df["member_casual"] = df["member_casual"].replace(USERTYPE)
    for c in STANDARD:
        if c not in df:
            df[c] = np.nan
    df = df[STANDARD].copy()
    for c in ["start_lat", "start_lng", "end_lat", "end_lng"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["start_station_id", "end_station_id"]:   # "516" not "516.0"
        df[c] = df[c].str.replace(r"\.0$", "", regex=True)
    return df


def file_label(zip_path):
    """'202409' (monthly) or '2019_Q2' (quarterly) from the zip name."""
    name = os.path.basename(zip_path)
    m = re.search(r"(\d{6})-divvy", name) or re.search(r"(\d{4}_Q\d)", name)
    return m.group(1)


def label_months(label):
    """Months (YYYYMM) a file label is supposed to cover."""
    if "_Q" in label:
        y, q = label.split("_Q")
        return [f"{y}{m:02d}" for m in range(3 * int(q) - 2, 3 * int(q) + 1)]
    return [label]


def read_zip(zip_path):
    """Read the trip CSV inside a zip (ignores __MACOSX), as strings.

    The month comes from the zip name, not the CSV: Divvy's 202601 zip
    contains a CSV named 202501-..., so the label is checked against the
    data instead (label_matches_data).
    """
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist()
                   if m.endswith(".csv") and not m.startswith("__MACOSX")]
        with zf.open(members[0]) as fh:
            return pd.read_csv(fh, dtype=str), members[0]


def clean_file(zip_path):
    """Clean one trip zip; returns (clean_df, quality_dict)."""
    label = file_label(zip_path)
    raw, inner = read_zip(zip_path)
    q = {"month": label, "inner_file": inner, "rows_raw": len(raw)}
    df = standardize(raw).drop_duplicates("ride_id")
    q["duplicates"] = len(raw) - len(df)
    scooter = df["rideable_type"].isin(CLEAN["drop_rideable_types"])
    q["scooters_dropped"] = int(scooter.sum())
    df = df[~scooter]
    df["started_at"] = pd.to_datetime(df["started_at"], format="mixed")
    df["ended_at"] = pd.to_datetime(df["ended_at"], format="mixed")
    df["duration_min"] = (df["ended_at"] - df["started_at"]
                          ).dt.total_seconds() / 60
    q["too_short"] = int((df["duration_min"] < CLEAN["min_minutes"]).sum())
    q["too_long_or_negative"] = int(
        ((df["duration_min"] > CLEAN["max_minutes"])
         | df["duration_min"].isna()).sum())
    df = df[df["duration_min"].between(CLEAN["min_minutes"],
                                       CLEAN["max_minutes"])]
    q["label_matches_data"] = bool(
        df["started_at"].dt.strftime("%Y%m").mode()[0] in label_months(label))
    q["missing_start_station"] = int(df["start_station_name"].isna().sum())
    df = df.assign(
        date=df["started_at"].dt.normalize(),
        hour=df["started_at"].dt.hour.astype("int8"),
        weekday=df["started_at"].dt.day_name(),
        rideable_type=df["rideable_type"].astype("category"),
        member_casual=df["member_casual"].astype("category"),
    )[["ride_id", "date", "started_at", "hour", "weekday", "rideable_type",
       "member_casual", "duration_min", "start_station_id",
       "start_station_name", "end_station_id", "end_station_name",
       "start_lat", "start_lng", "end_lat", "end_lng"]]
    q["rows_clean"] = len(df)
    return df, q


def raw_zips():
    """Trip zips whose label overlaps the study window."""
    lo, hi = START[:7].replace("-", ""), END[:7].replace("-", "")
    zips = glob.glob(os.path.join(raw_path("divvy_dir"), "*.zip"))
    return sorted(z for z in zips
                  if any(lo <= m <= hi for m in label_months(file_label(z))))


def trip_files():
    """Cleaned trip parquet files (one per raw zip)."""
    return sorted(glob.glob(os.path.join(TRIPS_DIR, "*.parquet")))


def read_trips(f, cols=None):
    """One cleaned trip file, cut to the study window."""
    t = pd.read_parquet(f, columns=cols)
    return t[t["date"].between(START, END)]


def clean_trips(force=False):
    """Clean every raw zip into interim/trips_clean/<label>.parquet."""
    os.makedirs(TRIPS_DIR, exist_ok=True)
    with lineage_run(
            "clean_trips",
            "Read each Divvy zip directly; map any file format to the "
            "standard columns; drop duplicate ride_ids, e-scooters, rides "
            "< 1 min or > 24 h; parse timestamps; add date/hour/weekday and "
            "duration; keep station IDs, names and coordinates.",
            [DS_DIVVY], [DS_TRIPS]) as ctx:
        rows = 0
        for zp in raw_zips():
            label = file_label(zp)
            parquet = os.path.join(TRIPS_DIR, f"{label}.parquet")
            qfile = parquet.replace(".parquet", ".quality.json")
            if os.path.exists(qfile) and not force:
                print(f"{label}: cached")
            else:
                df, q = clean_file(zp)
                df.to_parquet(parquet, index=False)
                with open(qfile, "w", encoding="utf-8") as fh:
                    json.dump(q, fh)
                print(f"{label}: {q['rows_raw']:>9,} raw -> "
                      f"{q['rows_clean']:>9,} clean")
            with open(qfile, encoding="utf-8") as fh:
                rows += json.load(fh)["rows_clean"]
        ctx["schemas"][DS_TRIPS] = pd.read_parquet(trip_files()[0]).head(0)
        ctx["row_counts"][DS_TRIPS] = rows


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
            [DS_NOAA], [ds("weather_daily")]) as ctx:
        raw = pd.read_csv(raw_path("noaa_csv"), dtype=str)
        ctx["input_schemas"][DS_NOAA] = raw.head(0)
        w = raw[(raw["DATE"] >= START) & (raw["DATE"] <= END)].copy()

        def value(col):
            vals = pd.to_numeric(w[col].str.strip(), errors="coerce")
            attr = w.get(col + "_ATTRIBUTES")
            if attr is not None:  # 2nd attribute = quality flag
                qflag = attr.fillna(",,").str.split(",").str[1]
                vals = vals.where(qflag.fillna("") == "")
            return vals

        o = pd.DataFrame({"date": pd.to_datetime(w["DATE"])})
        o["tmax_f"] = value("TMAX") / 10 * 9 / 5 + 32
        o["tmin_f"] = value("TMIN") / 10 * 9 / 5 + 32
        o["tavg_f"] = (value("TAVG") / 10 * 9 / 5 + 32).fillna(
            (o["tmax_f"] + o["tmin_f"]) / 2)
        o["precip_in"] = value("PRCP") / 10 / 25.4
        o["snow_in"] = value("SNOW") / 25.4
        o["snow_depth_in"] = value("SNWD") / 25.4
        o["wind_mph"] = value("AWND") / 10 * 2.23694
        for code, name in WT_NAMES.items():
            if code in w:
                o[name] = w[code].notna().astype("int8").to_numpy()
        o["rain_day"] = (o["precip_in"] >= 0.1).astype("int8")
        # Midway stopped reporting SNOW (snowfall) in this window, and
        # TAVG is missing too (filled above), so snow is measured as
        # "snow on the ground" from SNWD.
        o["snow_on_ground"] = (o["snow_depth_in"] > 0).astype("int8")
        o["temp_band"] = pd.cut(
            o["tavg_f"], [-100, 32, 50, 65, 80, 150],
            labels=["<32F", "32-50F", "50-65F", "65-80F", "80F+"]
        ).astype(str)
        o.to_parquet(out("weather_daily"), index=False)
        ctx["schemas"][ds("weather_daily")] = o
        print("weather days:", len(o))


# --------------------------------------------------------- stations ----
def fetch_gbfs():
    """Save today's GBFS station_information as a dated snapshot.

    Not part of the default run or DVC (it needs the network and changes
    daily). Point config.yaml stations.gbfs_snapshot at the new file to use it.
    """
    with urllib.request.urlopen(CFG["stations"]["gbfs_url"]) as r:
        feeds = json.load(r)["data"]
    url = next(f["url"] for lang in feeds.values() for f in lang["feeds"]
               if f["name"] == "station_information")
    dest = p("data", "raw", f"gbfs_station_information_{date.today()}.json")
    with urllib.request.urlopen(url) as r, open(dest, "wb") as fh:
        fh.write(r.read())
    print("saved", os.path.relpath(dest, ROOT), "from", url)


def load_gbfs():
    """GBFS snapshot -> one row per station (docks and public racks)."""
    with open(p(DS_GBFS), encoding="utf-8") as fh:
        st = pd.DataFrame(json.load(fh)["data"]["stations"])
    st = st.rename(columns={"name": "gbfs_name", "lon": "lng"})
    # Public racks / e-bike corrals have no short_name and 1-4 "docks".
    st["is_public_rack"] = st["short_name"].isna().astype("int8")
    return st[["station_id", "short_name", "gbfs_name", "lat", "lng",
               "capacity", "is_public_rack"]]


def norm(name):
    """Station name key for matching: lower case, single spaces, no
    trailing '*' (Divvy marks e-bike charging stations with it)."""
    return (name.str.lower().str.replace(r"\s+", " ", regex=True)
            .str.strip().str.rstrip("*").str.strip())


def haversine_m(lat1, lng1, lat2, lng2):
    """Great-circle distance in metres (broadcasts)."""
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    a = (np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2)
         * np.sin((lng2 - lng1) / 2) ** 2)
    return 6_371_000 * 2 * np.arcsin(np.sqrt(a))


def raw_stations():
    """Every distinct (trip station ID, name) seen at a trip start or end,
    with trip count, first/last date and median coordinates."""
    parts = []
    for f in trip_files():
        t = read_trips(f)
        for end in ("start", "end"):
            s = t[[f"{end}_station_id", f"{end}_station_name", f"{end}_lat",
                   f"{end}_lng", "date"]].dropna(
                       subset=[f"{end}_station_name"])
            s.columns = ["raw_id", "raw_name", "lat", "lng", "date"]
            parts.append(s.groupby(["raw_id", "raw_name"], dropna=False).agg(
                trips=("date", "size"), first=("date", "min"),
                last=("date", "max"), lat=("lat", "median"),
                lng=("lng", "median")))
    a = pd.concat(parts).reset_index()
    a["wlat"], a["wlng"] = a["lat"] * a["trips"], a["lng"] * a["trips"]
    g = a.groupby(["raw_id", "raw_name"], dropna=False).agg(
        trips=("trips", "sum"), first_date=("first", "min"),
        last_date=("last", "max"), wlat=("wlat", "sum"),
        wlng=("wlng", "sum")).reset_index()
    g["raw_lat"], g["raw_lng"] = g["wlat"] / g["trips"], g["wlng"] / g["trips"]
    return g.drop(columns=["wlat", "wlng"])


def match_stations():
    """Match each trip station to a GBFS station: ID, then name, then the
    nearest docked station within max_match_m."""
    with lineage_run(
            "match_stations",
            "Match every trip station (ID, name) to the GBFS snapshot: "
            "1) trip ID = GBFS short_name, 2) normalised name (current GBFS "
            "name, else a past name of an ID-matched station), 3) nearest "
            "docked station within max_match_m of the median trip "
            "coordinates. Unmatched stations keep their trip name.",
            [DS_TRIPS, DS_GBFS], [ds("station_match")]) as ctx:
        st, r = load_gbfs(), raw_stations()
        r["station_id"], r["match_method"] = None, "unmatched"
        r["match_dist_m"] = np.nan

        def assign(mask, ids, method):
            r.loc[mask, "station_id"] = ids
            r.loc[mask, "match_method"] = method

        by_short = st.dropna(subset=["short_name"]).set_index(
            "short_name")["station_id"]
        ids = r["raw_id"].map(by_short)
        assign(ids.notna(), ids[ids.notna()], "id")

        # current GBFS names first, then older names that ID-matched trips
        # used (e.g. legacy "Kingsbury St & Kinzie St" -> today's "... 1")
        names = pd.concat([
            st.assign(k=norm(st["gbfs_name"]), w=np.inf),
            r[r["match_method"] == "id"].assign(k=lambda x: norm(
                x["raw_name"]), w=lambda x: x["trips"])])
        by_name = names.sort_values("w", ascending=False).drop_duplicates(
            "k").set_index("k")["station_id"]
        ids = norm(r["raw_name"]).map(by_name)
        todo = (r["match_method"] == "unmatched") & ids.notna()
        assign(todo, ids[todo], "name")

        # docked stations only, so a renamed dock isn't snapped to a rack
        dock = st[st["is_public_rack"] == 0]
        todo = (r["match_method"] == "unmatched") & r["raw_lat"].notna()
        if todo.any():
            d = haversine_m(r.loc[todo, "raw_lat"].to_numpy()[:, None],
                            r.loc[todo, "raw_lng"].to_numpy()[:, None],
                            dock["lat"].to_numpy(), dock["lng"].to_numpy())
            r.loc[todo, "match_dist_m"] = d.min(axis=1)
            near = todo & (r["match_dist_m"]
                           <= CFG["stations"]["max_match_m"])
            assign(near, dock["station_id"].to_numpy()[d.argmin(axis=1)][
                near[todo].to_numpy()], "coords")

        r = r.merge(st, on="station_id", how="left")
        # distance to nearest dock is kept for coords + unmatched (audit)
        r.loc[r["match_method"].isin(["id", "name"]), "match_dist_m"] = np.nan
        r["match_dist_m"] = r["match_dist_m"].round(1)
        r.to_parquet(out("station_match"), index=False)
        ctx["schemas"][ds("station_match")] = r

        share = r.groupby("match_method")["trips"].sum() / r["trips"].sum()
        era = np.where(r["raw_id"].str.startswith("CHI", na=False),
                       "CHI ids (Jun 2025+)", "legacy ids")
        by_era = r.pivot_table(index=era, columns="match_method",
                               values="trips", aggfunc="sum").fillna(0)
        print("station trip-ends matched by method:\n",
              share.map("{:.1%}".format).to_string())
        print(by_era.div(by_era.sum(1), axis=0).map("{:.1%}".format))


# -------------------------------------------------- community areas ----
def area_lookup():
    """Function (lat, lng arrays) -> community area name per point.

    Uses the City of Chicago's 77 community-area polygons; points outside
    them (Evanston, Oak Park...) get "Outside Chicago".
    """
    with open(p(DS_AREAS), encoding="utf-8") as fh:
        feats = json.load(fh)["features"]
    polys = [shape(f["geometry"]) for f in feats]
    names = np.array([f["properties"]["community"].title() for f in feats]
                     + ["Outside Chicago"], dtype=object)
    tree = STRtree(polys)

    def lookup(lat, lng):
        idx = np.full(len(lat), len(polys))            # default: outside
        ok = ~(np.isnan(lat) | np.isnan(lng))
        pt, poly = tree.query(points(np.c_[lng[ok], lat[ok]]),
                              predicate="within")
        idx[np.flatnonzero(ok)[pt]] = poly
        return np.where(ok, names[idx], None)
    return lookup


# ------------------------------------------------------- aggregates ----
def aggregate_trips():
    """Clean trips -> daily / hourly / station / quality tables."""
    outs = ["daily_rides", "hourly_rides", "station_rides", "area_rides",
            "trip_quality"]
    with lineage_run(
            "aggregate_trips",
            "Aggregate clean trips to the study window: rides and duration "
            "per day x rider type x bike type; per weekday x hour; per GBFS "
            "station (start and end rides, active days, rides per dock per "
            "day, community area); per community area (station rides by "
            "station location, dockless rides by their rounded start "
            "coordinates); plus the cleaning quality log.",
            [DS_TRIPS, ds("station_match"), DS_AREAS],
            [ds(o) for o in outs]) as ctx:
        m = pd.read_parquet(out("station_match"))
        # station key: GBFS id if matched, else the raw trip name
        m["key"] = m["station_id"].fillna("raw:" + m["raw_name"])
        key = m.set_index(["raw_id", "raw_name"])["key"]
        # one descriptive row per station key (GBFS fields, else trip data)
        best = (m.sort_values("trips", ascending=False)
                .drop_duplicates("key").set_index("key"))
        best["start_station_name"] = best["gbfs_name"].fillna(
            best["raw_name"])
        best["lat"] = best["lat"].fillna(best["raw_lat"])
        best["lng"] = best["lng"].fillna(best["raw_lng"])
        area_of = area_lookup()
        best["community_area"] = area_of(best["lat"].to_numpy(float),
                                         best["lng"].to_numpy(float))
        daily, hourly, starts, ends, span, quality = [], [], [], [], [], []
        areas = []
        for f in trip_files():
            t = read_trips(f)
            obs = {"observed": True}
            t["dockless"] = t["start_station_name"].isna()
            daily.append(t.groupby(["date", "member_casual",
                                    "rideable_type"], **obs)
                         .agg(rides=("ride_id", "size"),
                              total_min=("duration_min", "sum"),
                              dockless_rides=("dockless", "sum")))
            hourly.append(t.groupby(["weekday", "hour", "member_casual"],
                                    **obs).size().rename("rides"))
            for e, acc in (("start", starts), ("end", ends)):
                s = t.dropna(subset=[f"{e}_station_name"])
                k = key.reindex(pd.MultiIndex.from_frame(
                    s[[f"{e}_station_id", f"{e}_station_name"]])).to_numpy()
                s = s.assign(key=k)
                acc.append(s.groupby(["key", "member_casual"], **obs)
                           .size())
                span.append(s.groupby("key")["date"].agg(["min", "max"]))
                if e == "start":
                    areas.append(s.assign(area=s["key"].map(
                        best["community_area"]), dockless=False)
                        .groupby(["area", "member_casual", "dockless"],
                                 **obs).size())
            # dockless starts: coordinates are rounded to 0.01 degrees
            dl = t.loc[t["dockless"],
                       ["start_lat", "start_lng", "member_casual"]].round(2)
            pts = dl[["start_lat", "start_lng"]].drop_duplicates()
            pts["area"] = area_of(pts["start_lat"].to_numpy(float),
                                  pts["start_lng"].to_numpy(float))
            areas.append(dl.merge(pts, on=["start_lat", "start_lng"])
                         .assign(dockless=True)
                         .groupby(["area", "member_casual", "dockless"],
                                  **obs).size())
            with open(f.replace(".parquet", ".quality.json"),
                      encoding="utf-8") as fh:
                quality.append(json.load(fh))

        def combine(parts):
            return pd.concat(parts).groupby(level=list(
                range(parts[0].index.nlevels)), observed=True).sum()

        sp = pd.concat(span).groupby(level=0).agg({"min": "min",
                                                   "max": "max"})
        active = ((sp["max"] - sp["min"]).dt.days + 1).rename("active_days")
        st = (combine(starts).rename("rides").to_frame()
              .join(combine(ends).rename("end_rides"), how="outer")
              .fillna(0).astype(int).reset_index()
              .merge(active, left_on="key", right_index=True))
        st = st.join(best[["start_station_name", "station_id", "short_name",
                           "lat", "lng", "capacity", "is_public_rack",
                           "match_method", "community_area"]], on="key")
        docked = st["is_public_rack"].eq(0) & st["capacity"].gt(0)
        st["rides_per_dock_per_day"] = (
            (st["rides"] + st["end_rides"]) / st["capacity"]
            / st["active_days"]).where(docked).round(3)
        st = st[["start_station_name", "member_casual", "rides",
                 "station_id", "short_name", "lat", "lng", "capacity",
                 "is_public_rack", "end_rides", "active_days",
                 "rides_per_dock_per_day", "match_method",
                 "community_area"]]
        ar = (combine(areas).rename("rides").reset_index()
              .pivot_table(index=["area", "member_casual"],
                           columns="dockless", values="rides",
                           aggfunc="sum", fill_value=0, observed=True))
        ar = pd.DataFrame({"station_rides": ar.get(False, 0),
                           "dockless_rides": ar.get(True, 0)})
        ar["rides"] = ar["station_rides"] + ar["dockless_rides"]
        ar = ar.reset_index().rename(columns={"area": "community_area"})[
            ["community_area", "member_casual", "rides", "station_rides",
             "dockless_rides"]]

        tables = {
            "daily_rides": combine(daily).reset_index(),
            "hourly_rides": combine(hourly).reset_index(),
            "station_rides": st.sort_values(["start_station_name",
                                             "member_casual"]),
            "area_rides": ar.sort_values(["community_area",
                                          "member_casual"]),
            "trip_quality": pd.DataFrame(quality)[
                ["month", "inner_file", "rows_raw", "duplicates",
                 "too_short", "too_long_or_negative", "label_matches_data",
                 "missing_start_station", "rows_clean", "scooters_dropped"]],
        }
        tables["daily_rides"]["avg_min"] = (
            tables["daily_rides"]["total_min"]
            / tables["daily_rides"]["rides"])
        for name, df in tables.items():
            for c in df.select_dtypes("category"):
                df[c] = df[c].astype(str)
            df.to_parquet(out(name), index=False)
            ctx["schemas"][ds(name)] = df
            print(name, df.shape)


def join_weather():
    """Daily rides (wide by rider type) + daily weather + US holidays."""
    with lineage_run(
            "join_weather",
            "Pivot daily rides by rider type, left-join Midway weather on "
            "date, add calendar fields and US federal holidays (observed "
            "dates, python-holidays) -> the reporting table.",
            [ds("daily_rides"), ds("weather_daily")],
            [ds("daily_rides_weather")]) as ctx:
        d = pd.read_parquet(out("daily_rides"))
        w = pd.read_parquet(out("weather_daily"))
        wide = d.pivot_table(index="date", columns="member_casual",
                             values="rides", aggfunc="sum").add_suffix(
                                 "_rides")
        wide["total_rides"] = wide.sum(axis=1)
        wide["avg_min"] = (d.groupby("date")["total_min"].sum()
                           / d.groupby("date")["rides"].sum())
        dl = d.groupby("date")["dockless_rides"].sum()
        o = wide.reset_index().merge(w, on="date", how="left")
        o["weekday"] = o["date"].dt.day_name()
        o["is_weekend"] = o["date"].dt.dayofweek.ge(5).astype("int8")
        o["month"] = o["date"].dt.to_period("M").astype(str)
        us = holidays.US(years=range(o["date"].dt.year.min(),
                                     o["date"].dt.year.max() + 1))
        o["holiday_name"] = o["date"].dt.date.map(us.get)
        o["is_holiday"] = o["holiday_name"].notna().astype("int8")
        o = o[[c for c in o if c != "holiday_name"] + ["holiday_name"]]
        o["dockless_rides"] = o["date"].map(dl).astype(int)       # KPI 5
        o["dockless_share"] = (o["dockless_rides"] / o["total_rides"]
                               ).round(4)
        o.columns.name = None
        o.to_parquet(out("daily_rides_weather"), index=False)
        ctx["schemas"][ds("daily_rides_weather")] = o
        print("daily_rides_weather", o.shape,
              "| days without weather:", int(o["tavg_f"].isna().sum()),
              "| holidays:", int(o["is_holiday"].sum()))


def weather_sensitivity():
    """KPI 2: % change in daily rides per +10F and on rain days, by rider
    type, from log-linear OLS:
      log(rides) ~ tavg_f + rain_day + is_weekend + is_holiday + trend
    exp(10 * b_temp) - 1 and exp(b_rain) - 1 are the reported effects."""
    with lineage_run(
            "weather_sensitivity",
            "KPI 2: OLS of log daily rides on average temperature, rain "
            "day, weekend, holiday and a linear trend, per rider type.",
            [ds("daily_rides_weather")], [ds("weather_sensitivity")]) as ctx:
        d = pd.read_parquet(out("daily_rides_weather"))
        x = d[["tavg_f", "rain_day", "is_weekend", "is_holiday"]].astype(
            float).assign(trend=(d["date"] - d["date"].min()).dt.days / 365,
                          const=1.0)
        rows = []
        for who in ["casual", "member", "total"]:
            y = np.log(d[f"{who}_rides"].to_numpy(float))
            b, *_ = np.linalg.lstsq(x.to_numpy(), y, rcond=None)
            r2 = 1 - ((y - x.to_numpy() @ b) ** 2).sum() / (
                (y - y.mean()) ** 2).sum()
            rows.append({"rider_type": who,
                         "pct_per_10f": round(np.exp(10 * b[0]) - 1, 4),
                         "pct_rain_day": round(np.exp(b[1]) - 1, 4),
                         "pct_weekend": round(np.exp(b[2]) - 1, 4),
                         "pct_holiday": round(np.exp(b[3]) - 1, 4),
                         "pct_per_year_trend": round(np.exp(b[4]) - 1, 4),
                         "r2": round(r2, 3), "n_days": len(y)})
        o = pd.DataFrame(rows)
        o.to_parquet(out("weather_sensitivity"), index=False)
        ctx["schemas"][ds("weather_sensitivity")] = o
        print(o.to_string(index=False))


def export():
    """Hand-off parquet -> CSV for Tableau (same columns)."""
    with lineage_run("export", "Write the hand-off tables as CSV for "
                     "Tableau.", [ds(n) for n in HANDOFF],
                     [f"data/exports/{n}.csv" for n in HANDOFF]):
        os.makedirs(EXPORTS, exist_ok=True)
        for n in HANDOFF:
            pd.read_parquet(out(n)).to_csv(
                os.path.join(EXPORTS, n + ".csv"), index=False)
        print("exported", len(HANDOFF), "CSVs")


STEPS = {"clean_trips": clean_trips, "clean_weather": clean_weather,
         "match_stations": match_stations,
         "aggregate_trips": aggregate_trips, "join_weather": join_weather,
         "weather_sensitivity": weather_sensitivity, "export": export}

if __name__ == "__main__":
    for folder in (INTERIM, PROCESSED, EXPORTS):
        os.makedirs(folder, exist_ok=True)
    args = [a for a in sys.argv[1:] if a != "--force"]
    for step in args or list(STEPS):
        print(f"--- {step} ---")
        if step == "fetch_gbfs":
            fetch_gbfs()
        elif step == "clean_trips":
            clean_trips(force="--force" in sys.argv)
        else:
            STEPS[step]()
