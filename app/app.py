"""Weather-Ready Divvy - System B: daily demand forecast from the weather.

Run:  streamlit run app/app.py
Reads data/processed/ (daily_rides_weather, station_rides) and the model in
model/forecast.py (fitted on all days at start-up, < 1 s).
"""
import os
import sys
from datetime import date

import altair as alt
import holidays
import numpy as np
import pandas as pd
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model"))
import forecast as fc  # noqa: E402

COLORS = alt.Scale(domain=["casual", "member"],
                   range=["#E8833A", "#3A6EA5"])
st.set_page_config(page_title="Weather-Ready Divvy", layout="wide")


@st.cache_data
def load():
    daily = fc.load()
    stations = pd.read_parquet(os.path.join(
        ROOT, "data", "processed", "station_rides.parquet"))
    return daily, stations


@st.cache_resource
def models():
    """Forecast models fitted on every day in the data."""
    return fc.fit(load()[0])


@st.cache_data
def holdout():
    return fc.holdout(load()[0])


daily, stations = load()
m = models()

# ------------------------------------------------------------- inputs ----
with st.sidebar:
    st.header("Forecast inputs")
    day = st.date_input("Date", date(2027, 6, 12),
                        min_value=date(2024, 9, 1),
                        max_value=date(2027, 12, 31))
    us_holiday = holidays.US(years=day.year).get(day)
    temp = st.slider("Average temperature (°F)", -10, 100, 72)
    precip = st.slider("Precipitation (in)", 0.0, 2.0, 0.0, 0.05)
    wind = st.slider("Average wind (mph)", 0, 30, 10)
    snow = st.slider("Snow on the ground (in)", 0.0, 12.0, 0.0, 0.5)
    holiday = st.checkbox(f"Holiday{f' ({us_holiday})' if us_holiday else ''}",
                          value=bool(us_holiday))
    st.caption("Model: one regression per rider type on Midway weather and "
               "the calendar, fitted on Sep 2024 - Sep 2026.")


def scenario(temps):
    """Input rows for the chosen day at one or more temperatures."""
    return pd.DataFrame({"date": pd.Timestamp(day), "tavg_f": temps,
                         "precip_in": precip, "snow_depth_in": snow,
                         "wind_mph": float(wind), "is_holiday": int(holiday)})


pred = fc.predict(m, scenario([float(temp)])).iloc[0]
base = fc.same_day_last_year(daily, pd.Series([pd.Timestamp(day)])).iloc[0]

# ----------------------------------------------------------- headline ----
weekday = pd.Timestamp(day).day_name()
rain = "rain" if precip >= 0.1 else "dry"
st.title("Weather-Ready Divvy: daily demand forecast")
st.write(f"**{weekday} {day:%b %d, %Y}** · {temp}°F · {rain} "
         f"({precip:.2f} in) · wind {wind} mph"
         + (" · holiday" if holiday else ""))

cols = st.columns(4)
for col, who in zip(cols, ["total", "casual", "member"]):
    delta = (None if np.isnan(base[who])
             else f"{pred[who] / base[who] - 1:+.0%} vs same day last year")
    col.metric(f"{who.title()} rides", f"{pred[who]:,.0f}", delta)
cols[3].metric("Casual share", f"{pred['casual'] / pred['total']:.0%}")
if np.isnan(base["total"]):
    st.caption("Same day last year (364 days earlier) is outside the data, "
               "so no baseline is shown.")

tab_temp, tab_stations, tab_test = st.tabs(
    ["Weather response", "Where to stage bikes", "Forecast accuracy"])

# ---------------------------------------------- casual vs member curve ----
with tab_temp:
    grid = np.arange(10, 96, 2.0)
    curve = fc.predict(m, scenario(grid))[["casual", "member"]]
    curve["tavg_f"] = grid
    curve = curve.melt("tavg_f", var_name="rider", value_name="rides")
    lines = alt.Chart(curve).mark_line(strokeWidth=3).encode(
        x=alt.X("tavg_f:Q", title="Average temperature (°F)"),
        y=alt.Y("rides:Q", title="Forecast rides"),
        color=alt.Color("rider:N", scale=COLORS, title=None))
    rule = alt.Chart(pd.DataFrame({"t": [temp]})).mark_rule(
        strokeDash=[4, 4], color="gray").encode(x="t:Q")
    st.altair_chart(lines + rule, width="stretch")
    ends = fc.predict(m, scenario([30.0, 80.0]))
    cold, warm = ends[["casual", "member"]].to_numpy()
    st.write(f"From 30°F to 80°F on this day, casual rides rise "
             f"**{warm[0] / cold[0]:.1f}x** and member rides "
             f"**{warm[1] / cold[1]:.1f}x**. Casual demand is the part that "
             "swings with the weather, so a fixed rebalancing schedule "
             "under-serves warm days and over-serves cold ones.")

# ------------------------------------------------- station staging list ----
with tab_stations:
    docked = stations[stations["is_public_rack"] == 0]
    share = docked.pivot_table(index=["start_station_name", "capacity",
                                      "community_area"],
                               columns="member_casual", values="rides",
                               aggfunc="sum", fill_value=0)
    share = share / share.sum()          # station share of each rider type
    exp = (share["casual"] * pred["casual"]
           + share["member"] * pred["member"]).rename("expected_starts")
    top = exp.reset_index().sort_values("expected_starts",
                                        ascending=False).head(15)
    top["starts_per_dock"] = top["expected_starts"] / top["capacity"]
    top = top.rename(columns={
        "start_station_name": "Station", "community_area": "Area",
        "capacity": "Docks", "expected_starts": "Expected starts",
        "starts_per_dock": "Starts per dock"})
    st.write("Busiest docked stations for this forecast: each station's "
             "past share of casual and member starts × the forecast.")
    st.dataframe(top[["Station", "Area", "Docks", "Expected starts",
                      "Starts per dock"]].round(1),
                 hide_index=True, width="stretch")
    st.caption("Assumes station shares stay at their Sep 2024 - Sep 2026 "
               "level. Dock counts are the 2026-11-26 GBFS snapshot.")

# ------------------------------------------------------ holdout test ----
with tab_test:
    metrics, rows = holdout()
    a, b, c = st.columns(3)
    t = metrics["total"]
    a.metric("Model error (MAPE)", f"{t['mape_model']:.1%}")
    b.metric("Same-day-last-year error", f"{t['mape_baseline']:.1%}")
    c.metric("Error reduction",
             f"{1 - t['mape_model'] / t['mape_baseline']:.0%}")
    long = rows.melt("date", ["total_actual", "total_model",
                              "total_baseline"],
                     var_name="series", value_name="rides")
    long["series"] = long["series"].str.replace("total_", "")
    st.altair_chart(alt.Chart(long).mark_line().encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("rides:Q", title="Total rides per day"),
        color=alt.Color("series:N", title=None, scale=alt.Scale(
            domain=["actual", "model", "baseline"],
            range=["black", "#3A6EA5", "#BBBBBB"]))),
        width="stretch")
    st.write(f"Trained on {metrics['train_days']} days before Jun 2026, "
             f"tested on {metrics['test_days']} unseen days "
             f"(Jun - Sep 2026). MAPE by rider type: casual "
             f"{metrics['casual']['mape_model']:.1%} vs "
             f"{metrics['casual']['mape_baseline']:.1%}, member "
             f"{metrics['member']['mape_model']:.1%} vs "
             f"{metrics['member']['mape_baseline']:.1%}.")
