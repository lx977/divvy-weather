"""Appendix: does a gradient-boosted model beat the linear forecast?

Same features, target (log 1 + rides per rider type) and Jun-Sep 2026
holdout as forecast.py; LightGBM with small, fixed settings (no tuning on
the test set). Writes model/metrics_lgbm.json.

Run:  python model/lgbm_appendix.py
"""
import json
import os

import lightgbm as lgb
import numpy as np

import forecast as fc

PARAMS = {"n_estimators": 400, "learning_rate": 0.03, "num_leaves": 15,
          "min_child_samples": 10, "subsample": 0.8, "subsample_freq": 1,
          "colsample_bytree": 0.8, "random_state": 0, "verbose": -1}


def main():
    df = fc.load()
    train = df[df["date"] < fc.TEST_START]
    test = df[df["date"].between(fc.TEST_START, fc.TEST_END)]
    xtr, xte = fc.features(train), fc.features(test)
    lin = fc.predict(fc.fit(train), test)
    out = {}
    total = 0
    for r in fc.RIDERS:
        m = lgb.LGBMRegressor(**PARAMS).fit(xtr, np.log1p(train[f"{r}_rides"]))
        p = np.expm1(m.predict(xte))
        total = total + p
        out[r] = {"mape_lgbm": round(fc.mape(test[f"{r}_rides"], p), 4),
                  "mape_linear": round(fc.mape(test[f"{r}_rides"], lin[r]),
                                       4)}
    out["total"] = {
        "mape_lgbm": round(fc.mape(test["total_rides"], total), 4),
        "mape_linear": round(fc.mape(test["total_rides"], lin["total"]), 4)}
    with open(os.path.join(fc.ROOT, "model", "metrics_lgbm.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
