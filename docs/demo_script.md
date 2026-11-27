# 15-minute briefing and demo script

Deck: `deck/Weather_Ready_Divvy_Final.pptx` (speaker notes on every slide). Before you start, open both apps on the presenting laptop: Tableau with `tableau/divvy_weather.twbx`, and Streamlit with `streamlit run app/app.py`. Keep backup screenshots in the appendix in case a demo fails.

| Time | Slide | Point to land |
|---|---|---|
| 0:00 | 1 Title | Hook: same bikes, two kinds of demand. Members ride in any weather; casual riders only when it's warm and dry. |
| 1:00 | 2 Decision, KPIs | The decision is when and where to add bikes, trucks and staff. Five KPIs; both hypotheses supported. |
| 2:30 | 3 Provenance | Landmines: station IDs re-keyed in Jun 2025, the mislabelled 202601 file, Sep 2024 scooters, 19.6% dockless. |
| 4:00 | 4 Hygiene | One command rebuilds everything. 12.53M → 12.07M rows; 99.6% of station trips matched to a dock. |
| 5:00 | 5 Signals | Two charts, two numbers: +64% vs +33% per +10°F; rain hits casual riders harder at every temperature. |
| 6:30 | 6 Stack | Why this stack: reproducible, right-sized, two tools for two jobs. |
| 7:30 | 7 Monitor | **Tableau demo (2 min)**, see below. |
| 9:30 | 8 Engine | **Streamlit demo (3 min)**, see below. H1: 14.0% vs 21.9% error. |
| 12:30 | 9 Value | Pays back if the pilot adds about 3,800 casual rides (+5.4%) on warm weekends, measured against control stations. |
| 13:30 | 10 Gate | The ask: a May–Sep 2027 pilot at 20 lakefront stations, about $19k of truck time. Then stop and take questions. |

## Tableau demo (System A, 2 min)

1. Open the dashboard with no filters and read the KPI strip from left to right.
2. Set the temperature band to 80°F+ and the day type to weekend. The lakefront community areas light up.
3. Click one hot area to show its station detail and rides per dock per day.
4. Point out the caveat on screen: capacity is today's snapshot.

## Streamlit demo (System B, 3 min)

1. Defaults: Saturday, Jun 12, 2027 at 72°F and dry. Read the casual, member and total metrics and the change against the same day last year.
2. Slide the temperature from 60 to 85°F. Casual rides swing far more than member rides (Weather response tab).
3. Add 0.5 in of rain. Casual rides drop the most.
4. Open the "Where to stage bikes" tab to see expected starts per dock at the top stations.
5. Open the "Forecast accuracy" tab: 122 unseen days, error 14.0% vs 21.9%.

## Likely questions

- **Why not a more complex model?** LightGBM scored the same (14.0%) and can't be explained to operations (appendix A).
- **How do you know riders were lost at empty docks?** We don't, because public data can't show them. That's why the pilot logs dock status first (appendix B).
- **The test used actual weather, but you'd only have a forecast?** Re-scored with forecast-like error (±3°F, 15% wrong rain calls): 17.3%, still below 21.9% (appendix A).
- **It barely pays?** About $19k buys a measured answer before any system-wide spend; the upside case is +$40k, and trucks freed on cold days aren't counted yet.
- **Capacity changes over time?** Yes. Capacity is a dated snapshot, and the pipeline can refresh it (`python pipeline/pipeline.py fetch_gbfs`).
