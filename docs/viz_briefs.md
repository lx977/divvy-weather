# Visualization briefs

Each of you picks one brief and designs your own visualization for it. The instructor wants **novel** visuals, so these give you a question, the data and a few guardrails, not a design. Surprise us.

All three end up as sheets in one Tableau workbook (System A, `tableau/divvy_weather.twbx`). Whoever finishes first also puts the dashboard frame together (see the end of this file). Each visual also gets a slide in the deck, so export a PNG at 1920 px wide.

## Shared guardrails

- **Audience:** Divvy's operations leadership. A reader should get the point in 10 seconds without you there to explain it.
- **One question per visual.** Put the answer in the title as a sentence, e.g. "Casual riders double when it warms 10°F; members barely move." Don't use a label like "Rides by temperature."
- **Shared colours** (the deck palette): casual `#E4572E` (coral), member `#2A7F8E` (teal), everything else grey (`#8FA9AE`, `#5C6B70`). Use amber `#F2B134` only to highlight something.
- **Tufte rules:** no 3D, no pie or donut charts, no dual axes unless both are normalised, light gridlines or none, and label directly instead of using legends where you can.
- **Source line:** put one in small grey type, e.g. "Divvy trips Sep 2024–Sep 2026, NOAA Midway; dock counts from the GBFS snapshot of 2026-11-26."
- **Don't repeat what we already have:** the monthly stacked bar, the temperature scatter, the weekday × hour heatmap, the rain bar chart and the top-stations bars are in `notebooks/figures/`. Go beyond them.
- **Data:** CSVs in `data/exports/` (Tableau), with columns explained in the README. Don't edit them; if you need something new, ask Lin and it goes into the pipeline.

---

## Brief 1: Weather and demand (H2, the headline)

**Question:** How differently do casual riders and members respond to the weather, and what does that mean for a fixed rebalancing schedule?

**Data:** `daily_rides_weather.csv` (one row per day: `casual_rides`, `member_rides`, `tavg_f`, `precip_in`, `rain_day`, `snow_depth_in`, `wind_mph`, `is_weekend`, `is_holiday`, `temp_band`). `weather_sensitivity.csv` has the modelled effects: casual +64% per 10°F vs member +33%, and rain −35% vs −26%.

**Ideas to start from (or ignore):** a calendar heatmap of casual share, where the weather shows up as texture. A "weather fingerprint" of small multiples by temperature × rain. A slope or ratio view of casual vs member indexed to a mild dry day. A horizon chart across two years.

**Lands on:** slide 8 (decision engine) and a dashboard sheet.

---

## Brief 2: Where the system strains

**Question:** Where and when do docks come under the most pressure, and does it follow tourists, commuters or neither?

**Data:** `station_rides.csv` (per station × rider type: `rides`, `end_rides`, `capacity`, `rides_per_dock_per_day`, `lat`, `lng`, `community_area`, `is_public_rack`). `area_rides.csv` (per community area × rider type: `rides`, `station_rides`, `dockless_rides`). Boundaries are in `data/raw/Boundaries_Community_Areas.geojson`; join on `community_area`, written in title case, and add "Outside Chicago" for rides outside the city.

**Caveats to show somewhere:** capacity is today's snapshot, applied to the past. Dockless coordinates are rounded to about 1 km. Public racks have no stress value.

**Ideas to start from (or ignore):** a map of community areas with stress and dockless share as two encodings. A station "pressure" beeswarm grouped by area. Capacity vs rides per dock, with the lakefront highlighted. A small map per rider type.

**Lands on:** slide 7 (monitoring) and a dashboard sheet.

---

## Brief 3: When does the forecast miss, and does it matter?

**Question:** Where does our forecast beat "same day last year", where does it fail, and what would those misses cost operations?

**Data:** `model/forecast_holdout.csv` (Jun–Sep 2026, per day: `*_actual`, `*_model`, `*_baseline` for casual, member and total). Join to `daily_rides_weather.csv` on `date` to explain misses by weather or holiday. Headline: error of 14.0% for the model vs 21.9% for the baseline.

**Ideas to start from (or ignore):** an error strip or waterfall that splits the baseline's error into the part weather explains and the part it doesn't. Residuals by weather condition. A "miss calendar" marking days where staffing would have been wrong by more than 20%.

**Lands on:** slide 9 (value and risk) and a dashboard sheet.

---

## Dashboard frame (whoever finishes first)

One dashboard that combines the three sheets. Across the top, a KPI strip as bullet graphs against last year:

1. Daily rides, casual vs member
2. Weather sensitivity (`weather_sensitivity.csv`)
3. Forecast error, model vs baseline
4. Median station stress (`rides_per_dock_per_day`, docked stations only)
5. Dockless share (`dockless_share`)

Add shared filters: date range, rider type, temperature band, rain/dry. Then save as a packaged workbook (`.twbx`) in `tableau/` and agree on one Tableau version.
