"""Illustrative value of the pilot (deck slide 9). Every number that is
not from our data is an ASSUMPTION below, with its source; change them
and re-run. Results are a low / base / high range, not a forecast of
Divvy's books.

Pilot: weather-triggered rebalancing at the 20 docked stations with the
most casual starts, on warm weekend/holiday days (avg temp >= 70F).

  extra rides  = casual rides at pilot stations on those days x uplift
  revenue      = extra rides x revenue per casual ride
  cost         = extra truck-hours on those days x cost per truck-hour

The headline is the break-even: how many extra casual rides the pilot must
add to cover its base-case cost. It needs no borrowed elasticity and the
pilot measures it directly (pilot vs control stations).

Run:  python model/roi.py   -> model/roi.json
"""
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
YEAR = ("2025-10-01", "2026-09-30")      # last 12 months of data

ASSUMPTIONS = {
    # Divvy single-ride prices, 2026 (divvybikes.com/pricing, help center)
    "unlock_usd": 1.00, "classic_per_min_usd": 0.20,
    "ebike_per_min_usd": 0.44,
    # Day-pass and discounted riders pay less than the single-ride price
    "price_realisation": {"low": 0.5, "base": 0.7, "high": 0.9},
    # Extra casual rides at pilot stations on target days from better bike
    # availability. Scenario values: public trip data never records riders
    # who found an empty dock. Kabra, Belavina & Girotra (2020, Management
    # Science 66(9), Paris Velib') show availability drives ridership via
    # lost sales; their exact elasticity is not used here.
    "ride_uplift": {"low": 0.024, "base": 0.06, "high": 0.12},
    # Extra rebalancing: one truck + driver per target day
    "truck_hours_per_day": {"low": 10, "base": 8, "high": 6},
    "truck_hour_usd": 75,                 # driver + vehicle, assumption
    "pilot_stations": 20, "warm_f": 70,
}


def main():
    a = ASSUMPTIONS
    daily = pd.read_parquet(os.path.join(PROC, "daily_rides_weather.parquet"))
    rides = pd.read_parquet(os.path.join(PROC, "daily_rides.parquet"))
    st = pd.read_parquet(os.path.join(PROC, "station_rides.parquet"))
    # pilot stations: share of ALL casual rides (incl. dockless), full window
    cas = st[(st["member_casual"] == "casual") & (st["is_public_rack"] == 0)]
    top = cas.nlargest(a["pilot_stations"], "rides")
    share = top["rides"].sum() / daily["casual_rides"].sum()
    daily = daily[daily["date"].between(*YEAR)]
    rides = rides[rides["date"].between(*YEAR)]

    target = daily[(daily["tavg_f"] >= a["warm_f"])
                   & ((daily["is_weekend"] == 1) | (daily["is_holiday"] == 1))]
    base_rides = target["casual_rides"].sum() * share

    # single-ride price of an average casual ride (bike mix and minutes)
    c = rides[rides["member_casual"] == "casual"].groupby(
        "rideable_type")[["rides", "total_min"]].sum()
    per_min = {"classic_bike": a["classic_per_min_usd"],
               "electric_bike": a["ebike_per_min_usd"]}
    price = (a["unlock_usd"] + sum(c.loc[b, "total_min"] * per_min[b]
                                   for b in c.index) / c["rides"].sum())

    out = {"target_days": len(target),
           "pilot_stations": top["start_station_name"].tolist(),
           "pilot_share_of_casual_rides": round(share, 4),
           "casual_rides_at_pilot_on_target_days": round(base_rides),
           "single_ride_price_usd": round(price, 2), "scenarios": {}}
    for s in ["low", "base", "high"]:
        extra = base_rides * a["ride_uplift"][s]
        revenue = extra * price * a["price_realisation"][s]
        cost = len(target) * a["truck_hours_per_day"][s] * a["truck_hour_usd"]
        out["scenarios"][s] = {"extra_rides": round(extra),
                               "revenue_usd": round(revenue),
                               "cost_usd": round(cost),
                               "net_usd": round(revenue - cost),
                               "roi": round(revenue / cost - 1, 2)}
    # extra rides at which base-case revenue covers base-case cost
    be = (len(target) * a["truck_hours_per_day"]["base"] * a["truck_hour_usd"]
          / (price * a["price_realisation"]["base"]))
    out["break_even_extra_rides"] = round(be)
    out["break_even_uplift"] = round(be / base_rides, 4)
    out["assumptions"] = a
    with open(os.path.join(ROOT, "model", "roi.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "assumptions"},
                     indent=2))


if __name__ == "__main__":
    main()
