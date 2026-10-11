"""Controller hooks for a retrieval-to-outlook task.

Raw provider files are controller-private staged inputs. Only the public
descriptors enter the actor sandbox; acquisition.py serves the provider files.
No withheld observations enter that service or the deciding calculation.
"""
import hashlib
import importlib.util
import json
import shutil
from functools import lru_cache
from pathlib import Path

import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent
MODELS = ["ecmwf", "cmcc", "ukmo", "meteofrance"]


@lru_cache(None)
def _module(name):
    spec = importlib.util.spec_from_file_location("mam_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(private, source_dir=None):
    from assessment.sources import restore
    # Existing source snapshots are verified rather than regenerated implicitly.
    return restore(HERE, private, source_dir or private)


def candidate_instances():
    return [{"id": "kenya-interior--mam-2016", "training_years": list(range(1993, 2016)),
             "new_years": [2016], "target_latitude": [-2.5, -1.5, -.5, .5, 1.5, 2.5],
             "target_longitude": [36.5, 37.5, 38.5], "model_names": MODELS}]


def brief_fields(params):
    return {"forecast_year": ", ".join(map(str, params["new_years"])),
            "training_start": min(params["training_years"]), "training_end": max(params["training_years"])}


def stage_inputs(private, params, destination):
    private, destination = Path(private), Path(destination)
    prepare(private)
    destination.mkdir(parents=True)
    shutil.copytree(private / "provider", destination / "provider")
    public = destination / "public"
    public.mkdir()
    text = json.dumps(params, indent=2) + "\n"
    (destination / "instance.json").write_text(text)
    (public / "instance.json").write_text(text)
    (public / "acquisition.json").write_text(json.dumps({
        "base_url": "http://weather-source:8000", "catalog_path": "catalog.json",
        "transport": "frozen HTTP source snapshot; not a live provider API",
        "instructions": "GET the catalogue, then retrieve and hash-check the named resources."
    }, indent=2) + "\n")
    _module("acquisition").provider_manifest(destination / "provider")


def expected_coordinates(inputs, params):
    return {"model": np.arange(4), "year": np.asarray(params["training_years"]),
            "new_year": np.asarray(params["new_years"]), "tercile": np.arange(3),
            "lat": np.asarray(params["target_latitude"]), "lon": np.asarray(params["target_longitude"])}


def compute(provider, params, conventions=None, independent=False):
    """Controller-side direct reads; actor controls acquire their own HTTP files."""
    module = _module("reference_independent" if independent else "science")
    provider, options = Path(provider), conventions or {}
    years, new_years = params["training_years"], params["new_years"]
    lat, lon = params["target_latitude"], params["target_longitude"]
    integration = options.get("integration") if options.get("integration") in ("thirty_days", "missing_seconds", "missing_millimetres") else None
    hindcasts, forecasts = {}, {}
    for model in MODELS:
        with xr.open_dataset(provider / "models" / (model + ".nc"), engine="h5netcdf") as ds:
            native = ds.load()
        seasonal = module.seasonal_model(native, years + new_years, lat, lon, defect=integration)
        values = np.asarray(seasonal)
        hindcasts[model], forecasts[model] = values[:len(years)], values[len(years):]
    with xr.open_dataset(provider / "observations/chirps-monthly-pre2016.nc", engine="h5netcdf") as ds:
        observed = np.asarray(module.seasonal_observed(ds.load(), years, lat, lon))
    return module.evaluate(hindcasts, observed, forecasts, years, new_years, lat, lon, defect=options)


def _raw(dataset):
    return {name: dataset[name].values for name in dataset.variables}


def reference(inputs, params, conventions):
    return _raw(compute(Path(inputs) / "provider", params, conventions))


def independent(inputs, params, conventions):
    return _raw(compute(Path(inputs) / "provider", params, conventions, independent=True))


def _rehash(provider):
    path = provider / "catalog.json"
    catalog = json.loads(path.read_text())
    for row in catalog["resources"]:
        source = provider / row["path"]
        row.update(sha256=hashlib.sha256(source.read_bytes()).hexdigest(), bytes=source.stat().st_size)
    path.write_text(json.dumps(catalog, indent=2) + "\n")


def perturb_inputs(inputs, seed, kind="data"):
    root, rng = Path(inputs), np.random.default_rng(seed)
    params = json.loads((root / "instance.json").read_text())
    provider = root / "provider"
    paths = ([provider / "observations/chirps-monthly-pre2016.nc"] if kind == "held_out" else
             [provider / "models" / (name + ".nc") for name in MODELS] +
             [provider / "observations/chirps-monthly-pre2016.nc"])
    if kind not in ("data", "held_out"):
        raise ValueError(kind)
    for path in paths:
        with xr.open_dataset(path, engine="h5netcdf") as ds:
            changed = ds.load()
        variable = next(iter(changed.data_vars))
        field, attrs = changed[variable], dict(changed[variable].attrs)
        time = next(name for name in ("forecast_reference_time", "indexing_time", "time") if name in field.dims)
        if kind == "held_out":
            factors = xr.where(field[time].dt.year == params["training_years"][0], 2.75, 1.0)
        else:
            factors = xr.DataArray(rng.uniform(.75, 1.3, field.sizes[time]), dims=[time], coords={time: field[time]})
        # Change source values without changing the agent's arithmetic precision.
        changed[variable] = (field.astype("float64") * factors).astype(field.dtype)
        changed[variable].attrs = attrs
        temporary = path.with_suffix(".tmp.nc")
        changed.to_netcdf(temporary, engine="h5netcdf")
        temporary.replace(path)
    _rehash(provider)


def probabilities_valid(results, params, inputs=None):
    names = ("model_hindcast_probability", "model_forecast_probability", "hindcast_probability", "forecast_probability")
    axes = (2, 2, 1, 1)
    epsilon = 1e-9
    ok = all(np.isfinite(results[n]).all() and np.all(results[n] >= -epsilon) and np.all(results[n] <= 1 + epsilon)
             and np.all(np.abs(results[n].sum(axis=a) - 1) <= epsilon) for n, a in zip(names, axes))
    return bool(ok), "All per-centre and combined probabilities must be finite, bounded, and sum to one."


def equal_model_combination(results, params, inputs=None):
    gap = max(float(np.max(np.abs(results[combined] - results[component].mean(axis=0))))
              for combined, component in (("hindcast_probability", "model_hindcast_probability"),
                                          ("forecast_probability", "model_forecast_probability")))
    return gap <= 1e-9, f"Maximum deviation from equal-centre probability average: {gap:g}."


def cv_score_identity(results, params, inputs=None):
    p, categories = results["hindcast_probability"], results["observed_category"]
    truth = np.stack([categories == i for i in range(3)], axis=1)
    score = float(np.sum((np.cumsum(p, axis=1) - np.cumsum(truth, axis=1)) ** 2, axis=1).mean())
    baseline = float(np.sum((np.cumsum(np.full_like(p, 1 / 3), axis=1) - np.cumsum(truth, axis=1)) ** 2, axis=1).mean())
    expected = (score, baseline, 1 - score / baseline)
    gap = max(abs(float(results[n]) - value) for n, value in zip(("cv_rps", "cv_rps_climatology", "cv_rpss"), expected))
    return gap <= 1e-9, f"Maximum discrepancy in RPS, climatological RPS and RPSS identities: {gap:g}."


INVARIANTS = {"probabilities_valid": probabilities_valid, "equal_model_combination": equal_model_combination,
              "cv_score_identity": cv_score_identity}


def _held_out_probabilities(results, inputs, params):
    index = int(np.flatnonzero(results["year"] == params["training_years"][0])[0])
    return {"model_hindcast_probability": results["model_hindcast_probability"][:, index:index + 1],
            "hindcast_probability": results["hindcast_probability"][index:index + 1]}


INVARIANCE_PROBES = {"held_out_year_isolation": {
    "perturb": "held_out", "unchanged": _held_out_probabilities,
    "passes": "Changing the held-out year's observation leaves that year's forecast probabilities unchanged.",
    "fails": "The held-out year's forecast depends on its own verifying observation."}}


def expected_claims(results, params):
    value = float(results["cv_rpss"])
    return {"cv_skill": [{"positive"} if value > 1e-9 else {"nonpositive"} if value < -1e-9 else {"positive", "nonpositive"}]}


def score(results, params, private, split):
    if split != "new_years":
        raise ValueError(split)
    module = _module("science")
    private = Path(private)
    with xr.open_dataset(private / "private-targets/chirps-monthly-2016.nc", engine="h5netcdf") as ds:
        observed = np.asarray(module.seasonal_observed(ds.load(), params["new_years"], params["target_latitude"], params["target_longitude"]))
    with xr.open_dataset(private / "provider/observations/chirps-monthly-pre2016.nc", engine="h5netcdf") as ds:
        training = np.asarray(module.seasonal_observed(ds.load(), params["training_years"], params["target_latitude"], params["target_longitude"]))
    thresholds = np.quantile(training, [1 / 3, 2 / 3], axis=0, method="linear")
    category = module.category(observed, thresholds)
    probabilities = results["forecast_probability"]
    score = float(module.rps(probabilities, category).mean())
    baseline = float(module.rps(np.full_like(probabilities, 1 / 3), category).mean())
    return {"split": split, "rps": score, "climatology_rps": baseline, "rpss": 1 - score / baseline,
            "years": params["new_years"], "cells": int(np.prod(category.shape[1:])), "ranking_enabled": False}


def independent_score(results, params, private, split):
    """Separate scalar category/score implementation, using private observations."""
    from math import fsum
    if split != "new_years":
        raise ValueError(split)
    module, private = _module("reference_independent"), Path(private)
    lat, lon = params["target_latitude"], params["target_longitude"]
    with xr.open_dataset(private / "provider/observations/chirps-monthly-pre2016.nc", engine="h5netcdf") as ds:
        training = module.seasonal_observed(ds.load(), params["training_years"], lat, lon)
    with xr.open_dataset(private / "private-targets/chirps-monthly-2016.nc", engine="h5netcdf") as ds:
        observed = module.seasonal_observed(ds.load(), params["new_years"], lat, lon)
    scores, baselines = [], []
    for year, j, k in np.ndindex(observed.shape):
        lower, upper = [module.quantile(training[:, j, k], q) for q in (1 / 3, 2 / 3)]
        label = 0 if observed[year, j, k] < lower else 2 if observed[year, j, k] > upper else 1
        probability, error, baseline = 0.0, 0.0, 0.0
        for category in range(3):
            probability += float(results["forecast_probability"][year, category, j, k])
            truth = float(category >= label)
            error += (probability - truth) ** 2
            baseline += ((category + 1) / 3 - truth) ** 2
        scores.append(error)
        baselines.append(baseline)
    score, baseline = fsum(scores) / len(scores), fsum(baselines) / len(baselines)
    return {"split": split, "rps": score, "climatology_rps": baseline, "rpss": 1 - score / baseline,
            "years": params["new_years"], "cells": len(lat) * len(lon), "ranking_enabled": False}


def sandbox_factory(*args, **kwargs):
    return _module("acquisition").sandbox_factory(*args, **kwargs)


def executor_factory(executor):
    return _module("acquisition").executor_factory(executor)


def acquisition_evidence(scratch, destination=None):
    return _module("acquisition").acquisition_evidence(scratch, destination)
