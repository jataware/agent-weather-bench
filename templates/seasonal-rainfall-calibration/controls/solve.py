"""Control solution for certification: per-cell linear regression of observed on forecast totals.

`variant.json` beside this file selects another valid method or switches on one
deliberate defect. With no variant file this is a known-conformant solution.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent
DAYS = {"actual": (31, 30, 31), "thirty_days": (30, 30, 30), "rates_not_converted": (1, 1, 1)}


def tercile_probabilities(mean, spread, low, high):
    below = 0.5 * (1 + math.erf((low - mean) / (spread * math.sqrt(2))))
    above = 1 - 0.5 * (1 + math.erf((high - mean) / (spread * math.sqrt(2))))
    return [below, 1 - below - above, above]


def calibrate(forecast, observed):
    """Fit observed = a + b * forecast at one cell; return the predictor and its residual spread."""
    slope, intercept = np.polyfit(forecast, observed, 1)
    residual = observed - (intercept + slope * forecast)
    return slope, intercept, max(float(np.sqrt((residual ** 2).sum() / max(len(forecast) - 2, 1))), 1e-6)


def leave_one_out(forecast, observed, year, include_held_out=False):
    """Probabilities for one year from a fit and category boundaries that exclude it."""
    keep = np.ones(len(forecast), bool) if include_held_out else np.arange(len(forecast)) != year
    slope, intercept, spread = calibrate(forecast[keep], observed[keep])
    low, high = np.quantile(observed[keep], [1 / 3, 2 / 3])
    return tercile_probabilities(intercept + slope * forecast[year], spread, low, high)


def category(value, low, high):
    return 0 if value < low else 2 if value > high else 1


def observed_categories(observed, variant):
    out = np.empty(observed.shape)
    for y in range(observed.shape[0]):
        for i in range(observed.shape[1]):
            for j in range(observed.shape[2]):
                basis = observed[:, i, j] if variant.get("full_sample_thresholds") else np.delete(observed[:, i, j], y)
                out[y, i, j] = category(observed[y, i, j], *np.quantile(basis, [1 / 3, 2 / 3]))
    return out


def skill_score(probability, observed, variant):
    scores, reference = [], []
    years = observed.shape[0]
    for y in range(years):
        for i in range(observed.shape[1]):
            for j in range(observed.shape[2]):
                others = np.delete(observed[:, i, j], y)
                basis = observed[:, i, j] if variant.get("full_sample_thresholds") else others
                low, high = np.quantile(basis, [1 / 3, 2 / 3])
                seen = category(observed[y, i, j], low, high)
                step = np.array([seen <= 0, seen <= 1], dtype=float)
                scores.append(((np.cumsum(probability[y, :, i, j])[:2] - step) ** 2).sum())
                if variant.get("training_frequencies"):
                    counts = np.bincount([category(v, low, high) for v in others], minlength=3) / len(others)
                else:
                    counts = np.full(3, 1 / 3)
                reference.append(((np.cumsum(counts)[:2] - step) ** 2).sum())
    return float(1 - np.mean(scores) / np.mean(reference))


def solve(inputs, variant):
    inputs = Path(inputs)
    with xr.open_dataset(inputs / "forecast-training.nc") as file:
        training = file.load()
    with xr.open_dataset(inputs / "observations-training.nc") as file:
        native = file.load()
    with xr.open_dataset(inputs / "forecast-new.nc") as file:
        new = file.load()
    days = xr.DataArray(list(DAYS[variant.get("month_lengths", "actual")]), dims="lead_time", coords={"lead_time": training.lead_time})
    forecast = (training.precip.astype("float64") * days).sum("lead_time").mean("member").transpose("init_time", "lat", "lon").values
    years = training.init_time.dt.year.values
    seasonal = native.precip.astype("float64").groupby(native.time.dt.year).sum("time")
    observed = np.empty_like(forecast)
    for i, lat in enumerate(training.lat.values):
        for j, lon in enumerate(training.lon.values):
            cell = seasonal.sel(lat=slice(lat - 0.5, lat + 0.5 - 1e-9), lon=slice(lon - 0.5, lon + 0.5 - 1e-9))
            weights = xr.ones_like(cell.lat) if variant.get("unweighted_observations") else np.cos(np.deg2rad(cell.lat))
            observed[:, i, j] = cell.weighted(weights).mean(("lat", "lon")).sel(year=years).values
    new_mean = new.forecast.astype("float64").mean("member").transpose("year", "lat", "lon").values
    if variant.get("pooled_new_batch"):
        new_mean = new_mean - new_mean.mean(axis=0, keepdims=True) + forecast.mean(axis=0, keepdims=True)
    hindcast = np.empty((len(years), 3) + forecast.shape[1:])
    outlook = np.empty((new_mean.shape[0], 3) + forecast.shape[1:])
    for i in range(forecast.shape[1]):
        for j in range(forecast.shape[2]):
            for y in range(len(years)):
                hindcast[y, :, i, j] = leave_one_out(forecast[:, i, j], observed[:, i, j], y, variant.get("not_cross_validated", False))
            slope, intercept, spread = calibrate(forecast[:, i, j], observed[:, i, j])
            low, high = np.quantile(observed[:, i, j], [1 / 3, 2 / 3])
            for n in range(new_mean.shape[0]):
                outlook[n, :, i, j] = tercile_probabilities(intercept + slope * new_mean[n, i, j], spread, low, high)
    if variant.get("climatological_forecast"):
        hindcast[:], outlook[:] = 1 / 3, 1 / 3
    if variant.get("invalid_probabilities"):
        hindcast[:, 2], outlook[:, 2] = hindcast[:, 2] + 0.2, outlook[:, 2] + 0.2
    method = {"calibration": {"what": "Linear regression of observed on ensemble-mean forecast totals at each cell, with a Gaussian residual.",
                              "where": {"file": "solve.py", "symbol": "def calibrate"}},
              "cross_validation": {"what": "Each year's probabilities come from a fit and category boundaries computed without that year.",
                                   "where": {"file": "solve.py", "symbol": "def leave_one_out"}}}
    if variant.get("no_method_statement"):
        method = {}
    if variant.get("false_method_pointer"):
        method["calibration"]["where"] = {"file": "solve.py", "symbol": "def " + "bayesian" + "_model_average"}   # no such function
    return {"results": {"year": years.tolist(), "new_year": new.year.values.tolist(), "latitude": training.lat.values.tolist(),
                        "longitude": training.lon.values.tolist(), "forecast_mean_mm": forecast.tolist(), "observed_total_mm": observed.tolist(),
                        "observed_category": observed_categories(observed, variant).tolist(),
                        "hindcast_probability": hindcast.tolist(), "hindcast_rpss": skill_score(hindcast, observed, variant),
                        "forecast_probability": outlook.tolist()},
            "choices": {"calibration": "linear regression with Gaussian residual", "observation mean": "plain" if variant.get("unweighted_observations") else "cosine-latitude"},
            "claims": {}, "method": method,
            "run": {"argv": ["python", "solve.py", "--inputs", "{input_dir}", "--output", "{output_dir}"]}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    variant = json.loads((HERE / "variant.json").read_text()) if (HERE / "variant.json").is_file() else {}
    Path(args.output).mkdir(parents=True, exist_ok=True)
    (Path(args.output) / "answer.json").write_text(json.dumps(solve(args.inputs, variant), allow_nan=False) + "\n")
