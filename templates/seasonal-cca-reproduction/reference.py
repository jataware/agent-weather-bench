"""A bounded CPT-inspired CCA adaptation; no claim of exact CPT parity."""
import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import xarray as xr

from assessment.sources import restore

HERE = Path(__file__).resolve().parent


def module(name):
    loader = importlib.util.spec_from_file_location(f"cca_{name}", HERE / f"{name}.py")
    loaded = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(loaded)
    return loaded


def prepare(private, source_dir):
    return restore(HERE, private, source_dir)


def candidate_instances():
    return [{"id": f"outer-{start}-2019--{region}", "outer_start": start, "region": region}
            for start in (2005, 2008) for region in ("all-cells", "eastern-cells")]


def brief_fields(params):
    return {"outer_start": params["outer_start"], "region": params["region"]}


def stage_inputs(private, params, destination):
    source, destination = Path(private) / "agent-inputs", Path(destination)
    destination.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file() and path.name != "targets.nc":
            shutil.copyfile(path, destination / path.name)
    with xr.open_dataset(source / "targets.nc") as data:
        if params["region"] == "eastern-cells":
            data = data.where(data.target_lon >= 38, drop=True)
        data.to_netcdf(destination / "targets.nc")
    shutil.copyfile(HERE / "algorithm.md", destination / "algorithm.md")
    (destination / "instance.json").write_text(json.dumps(params) + "\n")


def perturb_inputs(inputs, seed, kind="data"):
    path = Path(inputs) / ("predictors.nc" if kind == "later_forecast" else "targets.nc")
    with xr.open_dataset(path) as data:
        changed = data.load()
    rng = np.random.default_rng(seed)
    if kind == "later_forecast":
        changed["sst"].loc[{"year": [2022, 2023]}] += 1.5
    elif kind in ("data", "outer_future"):
        years = changed.year.values
        keep = np.ones(len(years), bool) if kind == "data" else years >= 2012
        values = changed.rainfall.values.copy()
        values[keep] = values[keep] * rng.uniform(0.8, 1.5, (keep.sum(), 1)) + rng.uniform(5, 25, values.shape[1])
        changed["rainfall"] = (changed.rainfall.dims, values, changed.rainfall.attrs)
    else:
        raise ValueError(kind)
    changed.to_netcdf(path.with_suffix(".tmp"))
    path.with_suffix(".tmp").replace(path)


def arrays(hindcast, forecast):
    return {"outer_year": hindcast.year.values, "forecast_year": forecast.year.values,
            "target": np.arange(hindcast.sizes["target"]), "system": np.arange(3), "category": np.arange(3),
            "boundary": np.arange(2), "candidate": hindcast.candidate.values,
            "hindcast_mean_mm": hindcast.prediction.values, "hindcast_probability": hindcast.probability.values,
            "hindcast_threshold_mm": hindcast.threshold.values, "selected_candidate": hindcast.selected_candidate.values,
            "inner_loss": hindcast.inner_loss.values, "hindcast_rpss": hindcast.rpss.values,
            "forecast_mean_mm": forecast.prediction.transpose("year", "system", "target").values,
            "forecast_probability": forecast.probability.transpose("year", "system", "target", "category").values,
            "forecast_threshold_mm": forecast.threshold.values, "final_candidate": forecast.selected_candidate.values,
            "final_inner_loss": forecast.inner_loss.values,
            "full_fit_mean_mm": hindcast.full_fit_prediction.values, "full_fit_probability": hindcast.full_fit_probability.values}


def reference(inputs, params, conventions):
    hindcast, forecast, _ = module("science").build(inputs, defect="full-training" if conventions["training"] == "full_training" else None)
    return arrays(hindcast, forecast)


def independent(inputs, params, conventions):
    return module("reference_independent").reference(inputs, params, conventions)


def expected_coordinates(inputs, params):
    with xr.open_dataset(Path(inputs) / "targets.nc") as data:
        targets = data.sizes["target"]
    return {"outer_year": np.arange(params["outer_start"], 2020), "forecast_year": np.arange(2020, 2024),
            "target": np.arange(targets), "system": np.arange(3), "category": np.arange(3), "boundary": np.arange(2), "candidate": np.arange(14)}


def early_outer(results, inputs, params):
    early = results["outer_year"] <= 2012
    return {name: results[name][early] for name in ("hindcast_mean_mm", "hindcast_probability", "hindcast_threshold_mm", "selected_candidate", "inner_loss")}


def early_forecasts(results, inputs, params):
    return {name: results[name][:2] for name in ("forecast_mean_mm", "forecast_probability")}


INVARIANCE_PROBES = {
    "outer_year_isolation": {"perturb": "outer_future", "unchanged": early_outer,
        "passes": "Each outer forecast through 2012 excludes its target and all later observations.",
        "fails": "An outer forecast uses its own or later observations."},
    "forecast_batch_isolation": {"perturb": "later_forecast", "unchanged": early_forecasts,
        "passes": "The first two production forecasts do not depend on the later forecast batch.",
        "fails": "Earlier production forecasts change when later predictors change."},
}


def probabilities(results, params, inputs):
    """Every tercile probability lies in [0,1] and each distribution sums to one."""
    names = ("hindcast_probability", "forecast_probability", "full_fit_probability")
    gap = max(float(np.max(np.abs(results[name].sum(axis=-1) - 1))) for name in names)
    ok = all(bool(((results[name] >= -1e-10) & (results[name] <= 1 + 1e-10)).all()) for name in names)
    return ok and gap <= 1e-8, f"largest probability normalization error is {gap:.3g}"


def skill_identity(results, params, inputs):
    """Climatology RPSS is zero and no system's RPSS exceeds one."""
    values = results["hindcast_rpss"]
    return abs(values[0]) <= 1e-9 and bool((values <= 1 + 1e-9).all()), f"RPSS values: {values.tolist()}"


INVARIANTS = {"probabilities_valid": probabilities, "rpss_identity": skill_identity}


def expected_claims(results, params):
    difference = results["hindcast_rpss"][2] - results["hindcast_rpss"][1]
    return {"nested_beats_fixed": [["yes" if difference > 1e-9 else "no"]], "full_fit_is_independent": [["no"]]}
