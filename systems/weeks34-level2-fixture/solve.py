"""Control solution for certification: seasonal harmonics plus the model forecast, fitted per cell.

`variant.json` beside this file selects another valid method or switches on one
deliberate defect. With no variant file this is a known-valid forecast.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent


def seasonal_terms(issue_time):
    angle = 2 * np.pi * (issue_time.dt.dayofyear.values + 14) / 365.25
    return np.column_stack([np.ones(len(angle)), np.sin(angle), np.cos(angle), np.sin(2 * angle), np.cos(2 * angle)])


def forecast(training, features, variant):
    method = variant.get("method", "bias")
    raw = features.raw_cfsv2.values.astype("float64")
    if variant.get("uses_later_forecasts"):
        padded = np.pad(raw, ((2, 2), (0, 0)), mode="edge")
        raw = np.mean([padded[k:k + len(raw)] for k in range(5)], axis=0)     # centred 5-issue mean: looks two issues ahead
    if method == "raw":
        return np.maximum(raw, 0)
    terms, target = seasonal_terms(training.issue_time), training.precipitation.values.astype("float64")
    new_terms = seasonal_terms(features.issue_time)
    if method == "climatology":
        return np.maximum(new_terms @ np.linalg.lstsq(terms, target, rcond=None)[0], 0)
    out = np.empty(raw.shape)
    for cell in range(raw.shape[1]):
        design = np.column_stack([terms, training.raw_cfsv2.values[:, cell].astype("float64")])
        beta = np.linalg.lstsq(design, target[:, cell], rcond=None)[0]
        out[:, cell] = np.column_stack([new_terms, raw[:, cell]]) @ beta
    return np.maximum(out, 0)


def solve(inputs, variant):
    inputs = Path(inputs)
    with xr.open_dataset(inputs / "training.nc") as file:
        training = file.load()
    results = {}
    for split in ("development", "final"):
        with xr.open_dataset(inputs / f"{split}-features.nc") as file:
            features = file.load()
        values = forecast(training, features, variant)
        dates = features.target_start if variant.get("mislabelled_dates") else features.issue_time
        issues = [str(value)[:10] for value in dates.values]
        if variant.get("multiplied_by_14"):
            values = values * 14
        if variant.get("negative_totals"):
            values = np.where(values < 4.0, -1.0, values)         # a fixed threshold, so the defect stays causal
        if variant.get("not_reproducible"):
            values = values + np.abs(np.random.default_rng().normal(0, 0.5, values.shape))
        if variant.get("missing_cases") and split == "final":
            values, issues = values[:-10], issues[:-10]
        results[f"{split}_mm"], results[f"{split}_issue"] = values.tolist(), issues
        results["location"] = features.location.values.tolist()
    return {"results": results, "choices": {"method": variant.get("method", "bias")}, "claims": variant.get("claims", {}),
            "run": {"argv": ["python", "solve.py", "--inputs", "{input_dir}", "--output", "{output_dir}"]}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    variant = json.loads((HERE / "variant.json").read_text()) if (HERE / "variant.json").is_file() else {}
    Path(args.output).mkdir(parents=True, exist_ok=True)
    (Path(args.output) / "answer.json").write_text(json.dumps(solve(args.inputs, variant), allow_nan=False) + "\n")
