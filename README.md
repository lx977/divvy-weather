# Weather-Ready Divvy

Final project for Data Visualization Strategies & Techniques: Divvy bike-share demand and Chicago weather. See `PLAN.md` for scope, roles and timeline.

## What's here

| Folder | Contents |
|---|---|
| `data/exports/` | Hand-off tables (CSV) for Tableau |
| `data/processed/` | The same tables as parquet for Streamlit, plus `daily_rides` (day × rider type × bike type) |
| `data/raw/` | Dated GBFS station snapshot (`gbfs_station_information_2026-11-26.json`). Raw trip and weather files stay outside git, see below |
| `pipeline/` | `pipeline.py` (ingest, clean, join, KPI tables), `lineage.py` (OpenLineage events, `lineage_events.jsonl`), `tests/` (format adapter test) |
| `notebooks/` | EDA notebook and its charts |
| `deck/` | Week 4 scope deck |
| `config.yaml`, `dvc.yaml` | Study window, cleaning rules, paths; pipeline stages for `dvc repro` |

## Hand-off tables

The apps read these small aggregated tables only; none of them touch the 12M trips. Columns from the starter tables keep their names; new columns are appended.

| Table | One row per | Columns |
|---|---|---|
| `daily_rides_weather` | day (760) | `date`, `casual_rides`, `member_rides`, `total_rides`, `avg_min`, Midway weather (`tmax_f`, `tmin_f`, `tavg_f`, `precip_in`, `snow_in`, `snow_depth_in`, `wind_mph`, weather-type flags), `rain_day`, `snow_on_ground`, `temp_band`, `weekday`, `is_weekend`, `month`, **`is_holiday`, `holiday_name`** |
| `hourly_rides` | weekday × hour × rider type | `weekday`, `hour`, `member_casual`, `rides` |
| `station_rides` | station × rider type | `start_station_name`, `member_casual`, `rides` (starts), **`station_id`, `short_name`, `lat`, `lng`, `capacity`, `is_public_rack`, `end_rides`, `active_days`, `rides_per_dock_per_day`, `match_method`** |
| `trip_quality` | raw file | `month`, `inner_file`, `rows_raw`, `duplicates`, `too_short`, `too_long_or_negative`, `label_matches_data`, `missing_start_station`, `rows_clean`, **`scooters_dropped`** |
| `station_match` (new) | trip station (ID + name) | raw ID, name, trips, first/last date, median coordinates, matched GBFS station, `match_method`, `match_dist_m` |

Definitions:

- `rides_per_dock_per_day` (KPI 4) = (start + end rides) ÷ `capacity` ÷ `active_days`. `active_days` counts the days from the station's first ride to its last in the window. The value is per rider-type row, so add the two rows to get the station total. It is empty for public racks and unmatched stations.
- `is_holiday`: US federal holidays from the `holidays` package, on their observed dates (24 days in the window).
- `station_rides` covers rides with a station only. Dockless rides count in the daily and hourly tables.

## Run the pipeline

```bash
pip install -r requirements.txt
cp config.local.example.yaml config.local.yaml   # then edit the two raw paths
dvc repro                                        # or: python pipeline/pipeline.py
python pipeline/tests/test_adapter.py            # format adapter check
```

Teammates don't need to run anything to use the tables: they are committed in `data/exports/` and `data/processed/`.

**Raw data (about 480 MB, not in git).** Divvy trip zips come from [divvybikes.com/system-data](https://divvybikes.com/system-data), and the weather file is NOAA GHCN-Daily station USW00014819 (Chicago Midway). Put them anywhere and point `config.local.yaml` at them (the file is git-ignored, so the paths stay on your laptop). Paths can be relative to the repo root, e.g. Lin's copy is `../../MLOps/HW1/partb_data/divvy`. `dvc.yaml` reads the same two files, so `dvc repro` uses your paths too. `dvc.lock` records the raw paths (relative) and file hashes of the last full run.

**Steps** (each one is a DVC stage and an OpenLineage job): `clean_trips` → `clean_weather` → `match_stations` → `aggregate_trips` → `join_weather` → `export`. `python pipeline/pipeline.py fetch_gbfs` saves a new dated GBFS snapshot. It isn't part of `dvc repro` because it needs the network; to use the new file, point `stations.gbfs_snapshot` in `config.yaml` at it.

## Data notes (for the audit slide)

- **Format adapter.** Every Divvy file format is mapped to the current 13 columns before cleaning, including 2013–2019 quarterly files (`trip_id`/`usertype` headers, and the `01 - Rental Details ...` headers in 2018 Q1 and 2019 Q2). Pre-2020 files have no bike type and no coordinates. The test runs on 500-row samples of `Divvy_Trips_2019_Q2` and `202409`.
- **Mislabeled file.** Divvy's `202601` zip contains a CSV named `202501`. Each zip is read directly, and its month is checked against the data (`label_matches_data`).
- **Dropped rows.** 2.6% of raw rows are dropped for duration (under 1 minute, over 24 hours, or negative). Another 1.2% (144,337) are e-scooters, which appear only in Sep 2024 and are dropped as a different product.
- **Dockless rides.** 19.6% of clean rides have no start station, mostly dockless e-bikes. Their coordinates are rounded to 0.01°.
- **Station IDs changed in Jun 2025.** Before that, IDs look like `516`, `13061` or `TA1308000012`. From Jun 2025 they look like `CHI00220`, which matches GBFS `short_name`. Names change too: the same ID can carry two names (e.g. `CHI01747` was "Streeter Dr & Grand Ave" and is now "Navy Pier"). Sep 2024 has 38 IDs with more than one name.
- **Station matching.** Each trip station (ID + name) is matched to the GBFS snapshot in three passes:
  1. Trip ID = GBFS `short_name`
  2. Station name (the current GBFS name, or an older name that an ID-matched station used)
  3. Nearest docked station within 150 m

  Matched by trip ends: 70.1% by ID, 28.6% by name, 0.9% by coordinates; **99.6% matched overall**, 0.4% unmatched (stations that have since been removed). Before Jun 2025, 98.1% match by name; from Jun 2025, 96.5% match by ID. The coordinate pass can fold a removed neighbouring dock into a current one (e.g. "St. Clair St & Erie St 1" → "… 2"), and `station_match.match_dist_m` shows each distance.
- **Public racks.** GBFS lists 901 public racks and e-bike corrals. They have no `short_name` and 1–4 spots, so they get `is_public_rack = 1` and no stress value.
- **Dock capacity is a 2026-11-26 snapshot** applied to past rides, and station names change over time.
- **Weather.** Midway doesn't report `TAVG` or `SNOW` in this period, so `tavg_f` = (max + min) / 2 and snow is measured as snow depth (`snow_on_ground`).
