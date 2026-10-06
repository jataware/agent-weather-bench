"""Controller hooks for the weeks 3-4 rainfall template (outcome mode).

There is no reference answer: any forecasting method is acceptable. The controller
builds the splits, checks that a submission is a valid forecast, and scores it
against withheld observations. Implementation A of the metric and of the
climatology baseline lives here; reference_independent.py is implementation B.
"""
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DAY = np.timedelta64(1, "D")
LEGACY = ROOT / "var/private/tasks/subseasonal-optimization"
RESPONSE_PERTURBATIONS = ("training_targets", "features")     # a forecast must depend on at least one of these

# training targets close before the first date; development issues run to the second; final issues to the third
SPLITS = {"final-2018-2021": ("2015-01-01", "2018-01-01", "2022-01-01"),
          "final-2015-2017": ("2012-01-01", "2015-01-01", "2018-01-01"),
          "final-2012-2014": ("2009-01-01", "2012-01-01", "2015-01-01"),
          "final-2009-2011": ("2006-01-01", "2009-01-01", "2012-01-01")}
CELLS = {"all-cells": None, "western-six": 247.5}             # None keeps all nine; a number keeps longitudes up to it


# ---- data ------------------------------------------------------------------------

def prepare(private, source_dir=None):
    private, record = Path(private), json.loads((HERE / "sources.json").read_text())["files"]["source-subset.nc"]
    target = private / "source-subset.nc"
    if not target.is_file():
        source = Path(source_dir or LEGACY / "controller") / "source-subset.nc"
        if not source.is_file():
            raise ValueError("source-subset.nc is missing. Pass the directory that holds it.")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    if hashlib.sha256(target.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("source-subset.nc does not match its recorded hash")
    with xr.open_dataset(target) as ds:
        return {"issues": int(ds.sizes["issue_time"]), "locations": int(ds.sizes["location"])}


def splits(private, params):
    """Controller view: (training, development, final), each with observations."""
    with xr.open_dataset(Path(private) / "source-subset.nc") as file:
        source = file.load()
    if params["longitude_limit"] is not None:
        source = source.sel(location=source.location[source.longitude <= params["longitude_limit"]])
    first, second, third = (np.datetime64(params[key]) for key in ("training_boundary", "development_boundary", "final_boundary"))
    closes = source.target_start + 14 * DAY
    training = source.sel(issue_time=closes < first)
    development = source.sel(issue_time=(source.issue_time >= first) & (closes < second))
    final = source.sel(issue_time=(source.issue_time >= second) & (source.issue_time < third))
    return training, development, final


def stage_inputs(private, params, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    training, development, final = splits(private, params)
    training.to_netcdf(destination / "training.nc")
    development.drop_vars("precipitation").to_netcdf(destination / "development-features.nc")
    final.drop_vars("precipitation").to_netcdf(destination / "final-features.nc")
    shutil.copyfile(HERE / "data-notes.txt", destination / "data-notes.txt")
    (destination / "instance.json").write_text(json.dumps(params, indent=2) + "\n")


def _rewrite(path, change):
    with xr.open_dataset(path) as file:
        ds = file.load()
    change(ds)
    temporary = path.with_name(path.name + ".tmp")
    ds.to_netcdf(temporary)
    temporary.replace(path)


def cut_date(inputs):
    """The middle issue of the final period: forecasts before it must not see features from it onward."""
    with xr.open_dataset(Path(inputs) / "final-features.nc") as ds:
        return ds.issue_time.values[ds.sizes["issue_time"] // 2]


def perturb_inputs(inputs, seed, kind):
    inputs, rng = Path(inputs), np.random.default_rng(seed)
    scale, offset = rng.uniform(1.4, 1.8), rng.uniform(2, 5)
    if kind == "training_targets":
        def change(ds):
            pattern = 1 + 0.3 * np.cos(np.arange(ds.sizes["location"]))
            ds["precipitation"] = (ds.precipitation * scale * pattern + offset).astype("float32").assign_attrs(ds.precipitation.attrs)
        _rewrite(inputs / "training.nc", change)
    elif kind in ("features", "features_after_cut"):
        cut = cut_date(inputs) if kind == "features_after_cut" else None
        for name in ("development-features.nc", "final-features.nc"):
            def change(ds):
                later = np.ones(ds.sizes["issue_time"], bool) if cut is None else ds.issue_time.values >= cut
                values = ds.raw_cfsv2.values.astype("float64")
                values[later] = values[later] * scale + offset
                ds["raw_cfsv2"] = (ds.raw_cfsv2.dims, values.astype("float32"), ds.raw_cfsv2.attrs)
            _rewrite(inputs / name, change)
    else:
        raise ValueError("Unknown perturbation: " + str(kind))


def expected_coordinates(inputs, params):
    """The exact issues and cells a submission must cover, in the order of the feature files."""
    frame = {}
    for split in ("development", "final"):
        with xr.open_dataset(Path(inputs) / f"{split}-features.nc") as ds:
            frame[f"{split}_issue"] = np.array([str(value)[:10] for value in ds.issue_time.values])
            frame["location"] = ds.location.values.astype(float)
    return frame


def before_cut(results, inputs, params):
    """The forecasts issued before the cut date, which later features must not move."""
    earlier = results["final_issue"] < str(cut_date(inputs))[:10]
    return {"development_mm": results["development_mm"], "final_mm": results["final_mm"][earlier]}


INVARIANCE_PROBES = {
    "no_future_information": {
        "perturb": "features_after_cut", "unchanged": before_cut,
        "passes": "Forecasts issued before the cut date do not move when later model forecasts change.",
        "fails": "Forecasts issued before the cut date move when later model forecasts change, so they use information from after their issue time."},
}


# ---- validity rules any forecast must obey -----------------------------------------

def _not_negative(results, params, inputs):
    low = float(min(results["development_mm"].min(), results["final_mm"].min()))
    return low >= 0, f"smallest forecast total is {low:.3g} mm"


def _magnitude(results, params, inputs):
    """Catches unit errors such as a daily rate, or a 14-day total multiplied by 14 again."""
    with xr.open_dataset(Path(inputs) / "training.nc") as ds:
        typical = float(ds.precipitation.mean())
    ratios = [float(results[name].mean()) / typical for name in ("development_mm", "final_mm")]
    ok = all(0.2 <= ratio <= 5 for ratio in ratios)
    return ok, "mean forecast is " + " and ".join(f"{ratio:.2f}" for ratio in ratios) + " times the mean observed 14-day total in training"


INVARIANTS = {"totals_not_negative": _not_negative, "magnitude_of_a_14_day_total": _magnitude}


# ---- scoring (implementation A) ----------------------------------------------------

def weighted_rmse(prediction, observed, latitude):
    weights = np.cos(np.deg2rad(np.asarray(latitude, dtype="float64")))
    error = np.asarray(prediction, dtype="float64") - np.asarray(observed, dtype="float64")
    return float(np.sqrt((error ** 2 * weights[None, :]).sum() / (error.shape[0] * weights.sum())))


def harmonics(issue_time):
    day = xr.DataArray(issue_time).dt.dayofyear.values
    angle = 2 * np.pi * (day + 14) / 365.25
    return np.column_stack([np.ones(len(day)), np.sin(angle), np.cos(angle), np.sin(2 * angle), np.cos(2 * angle)])


def climatology(training, issue_time):
    """Seasonal climatology: annual and semi-annual harmonics fitted to the training observations."""
    coefficients = np.linalg.lstsq(harmonics(training.issue_time.values), training.precipitation.values.astype("float64"), rcond=None)[0]
    return np.maximum(harmonics(issue_time) @ coefficients, 0)


def score(results, params, private, split="final"):
    """Skill of a forecast on one split. Controller only: reads the withheld observations."""
    training, development, final = splits(private, params)
    truth = {"development": development, "final": final}[split]
    forecast = results[f"{split}_mm"]
    if forecast.shape != truth.precipitation.shape:
        raise ValueError("Forecast does not cover the split")
    rmse = weighted_rmse(forecast, truth.precipitation.values, truth.latitude.values)
    raw = weighted_rmse(truth.raw_cfsv2.values, truth.precipitation.values, truth.latitude.values)
    seasonal = weighted_rmse(climatology(training, truth.issue_time.values), truth.precipitation.values, truth.latitude.values)
    return {"split": split, "rmse_mm": rmse, "raw_model_rmse_mm": raw, "climatology_rmse_mm": seasonal,
            "skill_vs_raw_model": 1 - rmse / raw, "skill_vs_climatology": 1 - rmse / seasonal,
            "issues": int(truth.sizes["issue_time"]), "cells": int(truth.sizes["location"]),
            "observations_are_public_history": True}


def independent_score(results, params, private, split="final"):
    import importlib.util
    spec = importlib.util.spec_from_file_location("weeks34_reference_independent", HERE / "reference_independent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.score(results, params, private, split)


def baseline_results(private, params, which):
    """A complete, valid forecast made by one of the two baselines, as aligned results."""
    training, development, final = splits(private, params)
    out = {"location": final.location.values.astype(float)}
    for name, ds in (("development", development), ("final", final)):
        out[f"{name}_issue"] = np.array([str(value)[:10] for value in ds.issue_time.values])
        out[f"{name}_mm"] = ds.raw_cfsv2.values.astype("float64") if which == "raw_model" else climatology(training, ds.issue_time.values)
    return out


def regression_checks(inputs):
    """Agreement with the files and scores frozen for the earlier packaged task, when they are present."""
    rows, params, private = [], instance("final-2018-2021", "all-cells"), ROOT / "var/private/templates/weeks34-rainfall"
    if not (LEGACY / "agent-inputs/training.nc").is_file():
        return [{"name": "legacy_task_files", "passed": True, "detail": "earlier task files absent; nothing to compare"}]
    training, development, final = splits(private, params)
    for name, ours in (("training.nc", training), ("development-features.nc", development.drop_vars("precipitation")),
                       ("final-features.nc", final.drop_vars("precipitation"))):
        with xr.open_dataset(LEGACY / "agent-inputs" / name) as file:
            rows.append({"name": f"staged {name} equals the earlier task's input", "passed": bool(file.load().identical(ours)), "detail": ""})
    with xr.open_dataset(LEGACY / "controller/final-baselines.nc") as file:
        gap = float(np.max(np.abs(file.climatology.values - climatology(training, final.issue_time.values))))
    rows.append({"name": "climatology baseline equals the earlier controller's", "passed": gap <= 1e-9, "detail": f"largest difference {gap:.3g} mm"})
    from weatherbench.task_tools.subseasonal.metrics import score_file
    with xr.open_dataset(LEGACY / "controller/final-baselines.nc") as file:
        candidate = xr.Dataset({"precipitation": file.bias_corrected.assign_attrs(units="mm")})
        scratch = Path(inputs) / "_legacy-check.nc"
        candidate.to_netcdf(scratch)
        old = score_file(scratch, LEGACY, "final")
        new = score({"final_mm": file.bias_corrected.values.astype("float64")}, params, private)
        scratch.unlink()
    gap = max(abs(old["rmse_mm"] - new["rmse_mm"]), abs(old["raw_cfsv2_rmse_mm"] - new["raw_model_rmse_mm"]),
              abs(old["climatology_rmse_mm"] - new["climatology_rmse_mm"]))
    rows.append({"name": "scores equal the earlier controller metric", "passed": gap <= 1e-12, "detail": f"largest difference {gap:.3g} mm"})
    return rows


# ---- instances and brief -----------------------------------------------------------

def instance(split, cells):
    first, second, third = SPLITS[split]
    return {"id": f"{split}--{cells}", "training_boundary": first, "development_boundary": second, "final_boundary": third,
            "longitude_limit": CELLS[cells]}


def candidate_instances():
    return [instance(split, cells) for split in SPLITS for cells in CELLS]


def brief_fields(params):
    def span(start, stop):
        last = int(stop[:4]) - 1
        return start[:4] if int(start[:4]) == last else f"{start[:4]}–{last}"
    return {"cells": "nine" if params["longitude_limit"] is None else "six", "training_boundary": params["training_boundary"],
            "development_span": span(params["training_boundary"], params["development_boundary"]),
            "final_span": span(params["development_boundary"], params["final_boundary"])}
