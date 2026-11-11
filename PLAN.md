# Weather-Ready Divvy: project plan

Final project for Data Visualization Strategies & Techniques. We have three weeks for the final presentation, live demo and repo.

## What we're building

A 15-minute executive briefing for Divvy operations, backed by two apps: a Tableau dashboard for monitoring and a Streamlit app that forecasts daily demand from the weather. The question is when and where Divvy should add bikes, staff and rebalancing ahead of the weather.

Hypotheses:

- H2 (headline): casual riders react far more to weather than members, so a fixed rebalancing schedule misses on both good and bad days. Early numbers support it: from the coldest to the warmest days, casual rides rise about 14x and member rides about 4x.
- H1 (test): a daily forecast that uses weather beats a "same day last year" baseline on forecast error (MAPE).

KPIs:

1. Daily rides, casual vs. member
2. Weather sensitivity: % change in rides per 10°F and on rain days, by rider type (H2)
3. Forecast error: MAPE of our model vs. the baseline (H1)
4. Station stress: rides per dock per day
5. Dockless share: % of rides with no start station (nice to have; the data already exists)

## Scope

We have three weeks, so the scope is fixed. Anything not listed under "must have" is cut first if we fall behind.

| | Items |
|---|---|
| Must have | Divvy trips + Midway weather (done), holiday flags, station capacity join, KPIs 1 to 4, a regression forecast, the Tableau dashboard, the Streamlit app, a 10 to 12 slide deck |
| Nice to have | Community-area map, a LightGBM model for the appendix, KPI 5 |
| Out (listed as future work) | Divvy data before Sep 2024, pricing and ROI data, Census, CTA ridership |

If Week 1 runs late, the community-area map goes first, and Tableau maps by station instead.

## Data

| Source | What it gives us | Coverage | Status |
|---|---|---|---|
| Divvy trip data | 12.5M raw trips (12.2M after cleaning): times, bike and rider type, stations, coordinates | Sep 2024 to Sep 2026, 25 monthly files | Cleaned |
| NOAA GHCN-Daily, Chicago Midway (USW00014819) | Daily temperature, precipitation, snow depth, wind | 1997 to 2026 | Cleaned and joined by date |
| Divvy GBFS station list, checked against the City of Chicago station dataset | Station ID, location, dock capacity | Current snapshot | Week 1 |
| US federal holidays (`holidays` Python package) | Holiday flag per date | Any year | Week 1 |
| Chicago community areas | 77 area boundaries | Static | Week 1, nice to have |

Known data problems, already handled or flagged:

- Divvy's `202601` zip contains a CSV named `202501`. Unzipping every file into one folder would overwrite January 2025 with January 2026. The pipeline reads each zip directly and checks the month.
- 19.9% of rides have no start station, mostly dockless e-bikes. Their coordinates are rounded to 0.01°. We keep them for counts but leave them out of station rankings.
- 2.6% of raw rows are dropped: rides under 1 minute (false starts), over 24 hours, or with negative duration.
- Midway doesn't report average temperature or snowfall in this period. We use (max + min) / 2 and snow depth instead.
- Dock capacity is today's snapshot, applied to past rides. Station names also change over time. Both go on the audit slide.

## Where things stand

What Lin has done so far:

- Cleaned all 25 monthly Divvy files with a reproducible Python pipeline. It produces daily, hourly, station and data-quality tables, and records lineage with OpenLineage.
- Joined the daily rides to Midway weather.
- Ran the first EDA. Rides were up 11% year over year (Oct 2025 to Sep 2026), temperature correlates 0.88 with daily rides, rain cuts rides 17 to 48% at the same temperature, members commute on weekdays, and casual riders peak on weekend afternoons.
- Built the 5-slide Week 4 scope deck.

What Lin does next:

1. Create the team GitHub repo with DVC for data. 
2. Update the pipeline: read the date window from a config file, add an adapter step so older Divvy files can be added later, and keep station IDs and start/end coordinates.
3. Add holiday flags and the station capacity table. Save a dated copy of the GBFS file so runs are reproducible.
4. Match trips to stations by ID first, then by name, then by nearest coordinates, and report the match rate.
5. Build the KPI tables and export CSVs for Tableau.
6. If time allows, add community areas.

## Work split

| Person | Owns | Deck slides |
|---|---|---|
| Lin | Data and pipeline: repo, cleaning, joins, KPI tables, data hand-off | 3 (sources and audit), 4 (cleaning and transformations), 5 (EDA signals) |
| Teammate A | Tableau dashboard (System A): KPI bullet graphs, month-by-year chart, casual vs. member comparison, weather and date filters, station map | 7 (monitoring dashboard) |
| Teammate B | Streamlit app and forecast (System B): regression model, baseline, holdout test, user inputs for temperature, rain, day of week and holiday; LightGBM for the appendix if time allows | 6 (tech stack), 8 (decision engine), 11 to 12 (appendix) |
| Teammate C | Story, deck and QA: storyline, slide design, value and ROI estimates, roadmap and decision gate, demo script, testing both apps, rehearsal | 1, 2, 9, 10, plus final assembly |

Teammates A and B don't need to wait for the final tables. The HW1 tables are good enough to start sketching charts and a first model, and the column names won't change.

## Timeline

| Week | Dates | Lin | Teammate A (Tableau) | Teammate B (Streamlit) | Teammate C (deck) | Done when |
|---|---|---|---|---|---|---|
| 1 | Nov 17 to 23 | Repo, pipeline changes, holiday and capacity joins, station matching. Starter tables are already in the repo; final KPI tables by Mon Nov 23 | Dashboard layout and first charts from the HW1 daily table | First regression model and same-day-last-year baseline on the HW1 daily table | Storyline and slide outline built from the Week 4 deck | Final KPI tables are in the repo and both apps load them |
| 2 | Nov 24 to 30 | Support both apps, fix data issues, write slides 3 to 5 | Full dashboard on the final tables | Final model, holdout results (train before Jun 2026, test Jun to Sep 2026), working app | Draft of all slides, value and ROI numbers | Both apps work end to end; the full draft deck exists |
| 3 | Dec 1 to 7 | Final data checks, README, repo cleanup | Polish, screenshots for the deck | Polish, backup screenshots of each app screen | Final deck, demo script, two rehearsals | Repo and deck submitted; demo rehearsed |


## Data hand-off

The apps read small, aggregated tables. Neither app touches the 12M raw trips.

| Table | One row per | Main columns | Used by |
|---|---|---|---|
| `daily_rides_weather` | day | `date`, `member_rides`, `casual_rides`, `total_rides`, `avg_min`, `tavg_f`, `tmax_f`, `tmin_f`, `precip_in`, `snow_depth_in`, `wind_mph`, `rain_day`, `temp_band`, `weekday`, `is_weekend`, `month`, plus `is_holiday` (new) | Tableau, Streamlit, model |
| `hourly_rides` | weekday × hour × rider type | `weekday`, `hour`, `member_casual`, `rides` | Tableau |
| `station_rides` | station × rider type | station ID and name, coordinates, `capacity`, `rides`, rides per dock per day (new) | Tableau, Streamlit |
| `trip_quality` | monthly file | raw rows, dropped rows, missing start station, month-label check | Deck (audit slide) |

Tableau reads the CSV exports in `data/exports/`. Streamlit reads the parquet files in `data/processed/`.

## Repo layout

```
divvy-weather/
├── PLAN.md
├── README.md            # how to run everything
├── config.yaml          # date window, paths
├── pipeline/            # ingest, clean, join, KPI tables
├── notebooks/           # EDA
├── data/
│   ├── raw/             # Divvy zips, NOAA CSV, GBFS snapshot (tracked with DVC)
│   ├── processed/       # parquet tables (tracked with DVC)
│   └── exports/         # CSVs for Tableau
├── model/               # forecast training and evaluation
├── app/                 # Streamlit app (run: streamlit run app/app.py)
├── tableau/             # packaged workbook (.twbx)
└── deck/                # .pptx
```

## Deliverables and grading

| Deliverable | Rubric area (points) | Owner |
|---|---|---|
| Problem, hypotheses, KPIs | Problem formulation (10) | Lin, C |
| Source audit and data traps | Discovery and provenance (20) | Lin |
| Documented pipeline and cleaned data | Data preparation (20) | Lin |
| Architecture and tool choices | Analytics architecture (20) | B, with Lin |
| Recommendations and ROI | Value creation (10) | C |
| Tableau workbook, Streamlit app, live briefing | Demo and delivery (20) | A, B, C |

## Risks

| Risk | Plan |
|---|---|
| Station matching takes longer than planned | Fall back to matching by name, report the match rate, and keep going |
| Week 1 slips | Cut the community-area map first, then KPI 5 |
| Tableau Desktop license or version differences | Save the workbook as a packaged `.twbx` with data included, and agree on one Tableau version |
| The live demo fails | Run both apps locally on the presenting laptop, and keep screenshots of every app screen in the appendix |


