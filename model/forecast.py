"""Daily demand forecast from the weather (H1) - used by the Streamlit app.

One linear regression per rider type (casual, member) on log(1 + rides);
total = casual + member. Features:
  weather  tavg_f, tavg_f^2, precip_in, rain_day, snow_depth_in, wind_mph
  calendar weekday, month, is_holiday, trend (years since the first day)
snow_depth_in is NaN from April to October (Midway only reports snow depth
Nov-Mar), so it is imputed as 0.

Baseline: "same day last year" = rides 364 days earlier (same weekday).
Holdout: train before 2026-06-01, test 2026-06-01 to 2026-09-30.

Run:  python model/forecast.py   -> model/metrics.json,
                                    data/exports/forecast_holdout.csv
"""
import json
import os

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "processed", "daily_rides_weather.parquet")
TEST_START, TEST_END = "2026-06-01", "2026-09-30"
RIDERS = ["casual", "member"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
        "Sunday"]
ORIGIN = pd.Timestamp("2024-09-01")          # trend = 0 on the first day


def load():
    """The daily reporting table (one row per day)."""
    return pd.read_parquet(DATA)


def features(df):
    """Model matrix from columns date, tavg_f, precip_in, snow_depth_in,
    wind_mph, is_holiday (rain_day is derived from precip_in)."""
    date = pd.to_datetime(df["date"])
    x = pd.DataFrame({
        "tavg_f": df["tavg_f"], "tavg_f2": df["tavg_f"] ** 2,
        "precip_in": df["precip_in"],
        "rain_day": (df["precip_in"] >= 0.1).astype(int),
        "snow_depth_in": df["snow_depth_in"].fillna(0),
        "wind_mph": df["wind_mph"],
        "is_holiday": df["is_holiday"].astype(int),
        "trend": (date - ORIGIN).dt.days / 365.25,
    }, index=df.index)
    for d in DAYS[1:]:                                  # Monday = reference
        x[f"wd_{d[:3]}"] = (date.dt.day_name() == d).astype(int)
    for m in range(2, 13):                              # January = reference
        x[f"m_{m:02d}"] = (date.dt.month == m).astype(int)
    return x


def fit(df):
    """{rider type: fitted LinearRegression} on log(1 + rides)."""
    x = features(df)
    return {r: LinearRegression().fit(x, np.log1p(df[f"{r}_rides"]))
            for r in RIDERS}


def predict(models, df):
    """Predicted casual, member and total rides for each row of df."""
    x = features(df)
    p = pd.DataFrame({r: np.expm1(m.predict(x)) for r, m in models.items()},
                     index=df.index)
    p["total"] = p[RIDERS].sum(axis=1)
    return p


def same_day_last_year(hist, dates):
    """Baseline: casual / member / total rides 364 days before each date
    (NaN where that day is outside the data)."""
    h = hist.set_index("date")[[f"{r}_rides" for r in RIDERS]]
    h.columns = RIDERS
    h["total"] = h.sum(axis=1)
    return h.reindex(pd.to_datetime(dates) - pd.Timedelta(days=364)
                     ).set_axis(dates.index)


def mape(actual, pred):
    """Mean absolute percentage error."""
    return float((abs(pred - actual) / actual).mean())


def holdout(df=None):
    """Train before TEST_START, score Jun-Sep 2026 against the baseline.

    Returns (metrics dict, per-day predictions frame)."""
    df = load() if df is None else df
    train = df[df["date"] < TEST_START]
    test = df[df["date"].between(TEST_START, TEST_END)]
    pred = predict(fit(train), test)
    base = same_day_last_year(df, test["date"])
    rows = test[["date"]].copy()
    metrics = {"train_days": len(train), "test_days": len(test),
               "test_window": [TEST_START, TEST_END]}
    for r in RIDERS + ["total"]:
        actual = test["total_rides" if r == "total" else f"{r}_rides"]
        rows[f"{r}_actual"] = actual
        rows[f"{r}_model"] = pred[r].round()
        rows[f"{r}_baseline"] = base[r]
        metrics[r] = {"mape_model": round(mape(actual, pred[r]), 4),
                      "mape_baseline": round(mape(actual, base[r]), 4)}
    return metrics, rows


if __name__ == "__main__":
    metrics, rows = holdout()
    with open(os.path.join(ROOT, "model", "metrics.json"), "w",
              encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    rows.to_csv(os.path.join(ROOT, "data", "exports",
                             "forecast_holdout.csv"), index=False)
    print(json.dumps(metrics, indent=2))
