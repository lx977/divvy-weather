# Weather-Ready Divvy

Final project for Data Visualization Strategies & Techniques: Divvy bike-share demand and Chicago weather. See `PLAN.md` for scope, roles and timeline.

## What's here

| Folder | Contents |
|---|---|
| `data/exports/` | Starter tables (CSV) for Tableau and Streamlit: daily rides with weather, rides by weekday and hour, rides by station, data-quality log per monthly file |
| `deck/` | Week 4 scope deck |
| `pipeline/` | Cleaning pipeline from HW1 (`partb_pipeline.py`, `lineage.py`) |
| `notebooks/` | HW1 EDA notebook and its charts |

## Notes

- The starter tables come from the HW1 pipeline. The station table has station names and ride counts only; station IDs, coordinates and dock capacity are added in the Week 1 update. The daily table will also gain an `is_holiday` column. Other column names stay the same.
- The pipeline still uses the HW1 folder layout and expects the raw Divvy zips and NOAA file next to it. Lin is updating it to read paths and dates from `config.yaml`.
- Raw data (about 460 MB) is not in this repo. Divvy trips come from [divvybikes.com/system-data](https://divvybikes.com/system-data), and the weather file is NOAA GHCN-Daily station USW00014819 (Chicago Midway).
