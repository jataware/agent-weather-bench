"""Implementation B of the seasonal rainfall calibration reference.

Shares no code with reference.py: it reads the files with netCDF4, builds totals
and area means in scalar loops, takes quantiles by sorting, and scores each case
from cumulative probabilities written out by hand.
"""
import math
from pathlib import Path

import netCDF4
import numpy as np

DAYS = {"actual": (31, 30, 31), "thirty_days": (30, 30, 30), "rates_not_converted": (1, 1, 1)}


def _years(variable):
    unit, _, origin = variable.units.partition(" since ")
    base_year, base_month = int(origin.strip()[:4]), int(origin.strip()[5:7])
    if unit.strip() not in ("days", "hours"):
        raise ValueError("Unexpected time unit")
    return [d.year for d in netCDF4.num2date(variable[:], variable.units, only_use_cftime_datetimes=False)]


def _quantile(values, q):
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(math.floor(position))
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _category(value, low, high):
    return 0 if value < low else 2 if value > high else 1


def _rps(p, category):
    first, second = p[0], p[0] + p[1]
    return (first - (1.0 if category <= 0 else 0.0)) ** 2 + (second - (1.0 if category <= 1 else 0.0)) ** 2


def answer(inputs, params, conventions, given=None):
    inputs = Path(inputs)
    with netCDF4.Dataset(inputs / "forecast-training.nc") as nc:
        rate = nc["precip"]
        order = [rate.dimensions.index(name) for name in ("init_time", "member", "lead_time", "lat", "lon")]
        rates = np.transpose(np.asarray(rate[:], dtype="float64"), order)
        years, lats, lons = _years(nc["init_time"]), [float(v) for v in nc["lat"][:]], [float(v) for v in nc["lon"][:]]
    with netCDF4.Dataset(inputs / "observations-training.nc") as nc:
        rain = nc["precip"]
        order = [rain.dimensions.index(name) for name in ("time", "lat", "lon")]
        native = np.transpose(np.asarray(rain[:], dtype="float64"), order)
        months, fine_lat, fine_lon = _years(nc["time"]), [float(v) for v in nc["lat"][:]], [float(v) for v in nc["lon"][:]]
    days = DAYS[conventions["month_lengths"]]
    members = rates.shape[1]
    forecast = np.zeros((len(years), len(lats), len(lons)))
    observed = np.zeros_like(forecast)
    for y, year in enumerate(years):
        times = [t for t, value in enumerate(months) if value == year]
        for i, lat in enumerate(lats):
            rows = [r for r, value in enumerate(fine_lat) if lat - 0.5 <= value < lat + 0.5]
            for j, lon in enumerate(lons):
                forecast[y, i, j] = sum(rates[y, m, k, i, j] * days[k] for m in range(members) for k in range(3)) / members
                cols = [c for c, value in enumerate(fine_lon) if lon - 0.5 <= value < lon + 0.5]
                numerator = denominator = 0.0
                for r in rows:
                    weight = math.cos(math.radians(fine_lat[r])) if conventions["observation_weighting"] == "cos_latitude" else 1.0
                    for c in cols:
                        numerator += weight * sum(native[t, r, c] for t in times)
                        denominator += weight
                observed[y, i, j] = numerator / denominator
    seen = np.zeros_like(observed)
    for y in range(len(years)):
        for i in range(len(lats)):
            for j in range(len(lons)):
                basis = [observed[k, i, j] for k in range(len(years)) if k != y or conventions["category_thresholds"] != "leave_one_out"]
                seen[y, i, j] = _category(observed[y, i, j], _quantile(basis, 1 / 3), _quantile(basis, 2 / 3))
    out = {"forecast_mean_mm": forecast, "observed_total_mm": observed, "observed_category": seen}
    if given is not None:
        p = np.asarray(given["hindcast_probability"], dtype="float64")
        total = reference = 0.0
        for y in range(len(years)):
            for i in range(len(lats)):
                for j in range(len(lons)):
                    others = [observed[k, i, j] for k in range(len(years)) if k != y]
                    basis = others if conventions["category_thresholds"] == "leave_one_out" else others + [observed[y, i, j]]
                    low, high = _quantile(basis, 1 / 3), _quantile(basis, 2 / 3)
                    category = _category(observed[y, i, j], low, high)
                    total += _rps([p[y, 0, i, j], p[y, 1, i, j], p[y, 2, i, j]], category)
                    if conventions["climatology_reference"] == "equal_thirds":
                        climate = [1 / 3, 1 / 3, 1 / 3]
                    else:
                        counts = [0, 0, 0]
                        for value in others:
                            counts[_category(value, low, high)] += 1
                        climate = [count / len(others) for count in counts]
                    reference += _rps(climate, category)
        out["hindcast_rpss"] = np.array(1 - total / reference)
    return out
