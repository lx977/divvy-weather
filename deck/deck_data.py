"""Collect every number the final deck shows into deck/deck_data.json, so
build_deck.js never hard-codes a result.

Run:  python deck/deck_data.py && node deck/build_deck.js
"""
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
ORDER = ["<32F", "32-50F", "50-65F", "65-80F", "80F+"]

# Share of station IDs in the new CHI##### format per monthly file (counted
# from the raw zips while auditing; the switch happens in Jun 2025).
CHI_SHARE = {"202409": 0, "202410": 0, "202411": 0, "202412": 0,
             "202501": 0, "202502": 0, "202503": 0, "202504": 0,
             "202505": 0, "202506": 100, "202507": 100, "202508": 99,
             "202509": 100, "202510": 100, "202511": 100, "202512": 100,
             "202601": 100, "202602": 100, "202603": 100, "202604": 100,
             "202605": 100, "202606": 100, "202607": 100, "202608": 100,
             "202609": 100}


def read(name):
    return pd.read_parquet(os.path.join(PROC, name + ".parquet"))


def load_json(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    d = read("daily_rides_weather")
    band = d.groupby("temp_band")[["casual_rides", "member_rides"]].mean()
    band = band.loc[ORDER].round()
    rain = d.pivot_table(index="temp_band", columns="rain_day",
                         values=["casual_rides", "member_rides"],
                         aggfunc="mean").loc[ORDER]
    drop = {w: (1 - rain[(f"{w}_rides", 1)] / rain[(f"{w}_rides", 0)])
            .round(4).tolist() for w in ["casual", "member"]}
    rain_days = d.groupby("temp_band")["rain_day"].sum().loc[ORDER]
    q = read("trip_quality").sum(numeric_only=True)
    m = read("station_match")
    era = m["raw_id"].str.startswith("CHI", na=False).map(
        {True: "chi", False: "legacy"})
    share = lambda g: (g.groupby("match_method")["trips"].sum()  # noqa: E731
                       / g["trips"].sum()).round(4).to_dict()
    st = read("station_rides")
    stress = st[st["is_public_rack"] == 0].groupby("station_id")[
        "rides_per_dock_per_day"].sum()
    h = pd.read_csv(os.path.join(ROOT, "model", "forecast_holdout.csv"))
    yr = lambda a, b: d.loc[d["date"].between(a, b),  # noqa: E731
                            "total_rides"].sum()
    out = {
        "days": len(d), "total_rides": int(d["total_rides"].sum()),
        "yoy": round(yr("2025-10-01", "2026-09-30")
                     / yr("2024-10-01", "2025-09-30") - 1, 4),
        "corr_temp": round(d["total_rides"].corr(d["tavg_f"]), 3),
        "band": {"labels": ORDER, "casual": band["casual_rides"].tolist(),
                 "member": band["member_rides"].tolist()},
        "band_ratio": {w: round(band[f"{w}_rides"].iloc[-1]
                                / band[f"{w}_rides"].iloc[0], 1)
                       for w in ["casual", "member"]},
        "rain_drop": drop,
        "rain_days": rain_days.astype(int).tolist(),
        "quality": {k: int(q[k]) for k in
                    ["rows_raw", "too_short", "too_long_or_negative",
                     "scooters_dropped", "rows_clean",
                     "missing_start_station"]},
        "match": share(m),
        "match_era": {k: share(g) for k, g in m.groupby(era)},
        "chi_share": CHI_SHARE,
        "median_stress": round(float(stress.median()), 2),
        "max_stress": round(float(stress.max()), 1),
        "last12_avg_daily": round(yr("2025-10-01", "2026-09-30") / 365),
        "last12_casual_share": round(
            d.loc[d["date"] >= "2025-10-01", "casual_rides"].sum()
            / yr("2025-10-01", "2026-09-30"), 3),
        "dockless_share": round(d["dockless_rides"].sum()
                                / d["total_rides"].sum(), 4),
        "sensitivity": read("weather_sensitivity").to_dict("records"),
        "holdout": h[["date", "total_actual", "total_model",
                      "total_baseline"]].to_dict("list"),
        "metrics": load_json("model", "metrics.json"),
        "lgbm": load_json("model", "metrics_lgbm.json"),
        "noise": load_json("model", "metrics_noise.json"),
        "roi": load_json("model", "roi.json"),
    }
    with open(os.path.join(ROOT, "deck", "deck_data.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("wrote deck/deck_data.json")


if __name__ == "__main__":
    main()
