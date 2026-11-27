"""Stress test: holdout error when the model only has a weather FORECAST.

forecast.py scores the Jun-Sep 2026 holdout with the weather that actually
happened. In operations Divvy would feed tomorrow's forecast, which is
wrong by a few degrees and sometimes calls rain on a dry day (or the
reverse). We add that error to the test-day weather and re-score:

  temperature  + Normal(0, sigma), sigma = MAE / 0.798 (MAE of a normal);
               day-1 NWS max/min temperature MAE is roughly 2-4F
               (NWS Central Region verification, Moline IL)
  rain         a share of days get the wrong rain/dry call (our assumption:
               15%); a wrongly "wet" day gets 0.25 in, a wrongly dry one 0

Mean over 200 random draws per scenario (seed 0).
Run:  python model/forecast_noise.py   -> model/metrics_noise.json
"""
import json
import os

import numpy as np

import forecast as fc

SCENARIOS = [(0, 0.0), (2, 0.0), (3, 0.0), (4, 0.0), (3, 0.15), (4, 0.15)]
DRAWS = 200


def main():
    df = fc.load()
    train = df[df["date"] < fc.TEST_START]
    test = df[df["date"].between(fc.TEST_START, fc.TEST_END)]
    models, rng = fc.fit(train), np.random.default_rng(0)
    base = fc.mape(test["total_rides"],
                   fc.same_day_last_year(df, test["date"])["total"])
    rows = []
    for mae, flip in SCENARIOS:
        errs = []
        for _ in range(DRAWS):
            x = test.copy()
            x["tavg_f"] += rng.normal(0, mae / 0.798, len(x))
            wrong = rng.random(len(x)) < flip
            wet = x["precip_in"] >= 0.1
            x.loc[wrong & wet, "precip_in"] = 0.0
            x.loc[wrong & ~wet, "precip_in"] = 0.25
            errs.append(fc.mape(test["total_rides"],
                                fc.predict(models, x)["total"]))
        rows.append({"temp_mae_f": mae, "rain_call_wrong": flip,
                     "mape_model": round(float(np.mean(errs)), 4),
                     "mape_baseline": round(base, 4)})
        print(rows[-1])
    with open(os.path.join(fc.ROOT, "model", "metrics_noise.json"), "w",
              encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)


if __name__ == "__main__":
    main()
