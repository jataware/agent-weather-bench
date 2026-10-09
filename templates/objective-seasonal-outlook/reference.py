"""Controller hooks for the objective seasonal outlook.

Provider files are controller-private staged inputs served over the task's snapshot
HTTP service; the actor sees only the public descriptors. prepare_*, wvg_* and ereg_*
are reference-matched; cca_*, combine_*, verify_* and issue_* are free arrays checked
by invariants that recompute them from the submission's own upstream arrays (the local
verdict) and, for CCA, by agreement with the controller's CCA on the same inputs.
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
INPUTS_SHARED_ACROSS_INSTANCES = False
# Measured engine spread (var/validation/objective-seasonal-outlook/cca-engine-spread-*.json): africaS2S's
# CPT-parity CCA (window-5 cross-validation, Kendall-tau mode selection, with and without the empirical
# transform) correlates with this reference at 0.66-0.90 per category on the hindcasts and scores 0.05-0.06
# RPSS below it on MAM. A valid alternative engine must pass, so the floor and margin sit below that spread.
# The design record's 0.85 floor is not attainable by that engine and is superseded by the measurement.
CCA_CORRELATION_FLOOR = 0.6
CCA_RPSS_MARGIN = 0.08
WITHHELD_YEAR = 2015


@lru_cache(None)
def _module(name):
    spec = importlib.util.spec_from_file_location("outlook_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(private, source_dir=None):
    from assessment.sources import restore
    return restore(HERE, private, source_dir or private)


def candidate_instances():
    years = [y for y in range(1993, 2017) if y != WITHHELD_YEAR]
    return [{"id": "gha--mam-2015", "init_month": 2, "forecast_year": WITHHELD_YEAR, "training_years": years},
            {"id": "gha--ond-2015", "init_month": 8, "forecast_year": WITHHELD_YEAR, "training_years": years}]


def brief_fields(params):
    names = {2: ("March–May", "February"), 8: ("October–December", "August")}[int(params["init_month"])]
    return {"season_name": names[0], "init_month_name": names[1], "forecast_year": params["forecast_year"],
            "training_start": min(params["training_years"]), "training_end": max(params["training_years"])}


def _target_grid(path):
    science = _module("science")
    ds = xr.Dataset(coords={"lat": science.TARGET_LAT, "lon": science.TARGET_LON})
    ds["lat"].attrs.update(units="degrees_north", long_name="target cell centre latitude", cell_width_degrees=0.5)
    ds["lon"].attrs.update(units="degrees_east", long_name="target cell centre longitude", cell_width_degrees=0.5)
    ds.attrs.update(description="The centre's 0.5-degree working grid; each cell spans +-0.25 degrees about its centre.",
                    south=float(science.TARGET_LAT[0] - 0.25), north=float(science.TARGET_LAT[-1] + 0.25),
                    west=float(science.TARGET_LON[0] - 0.25), east=float(science.TARGET_LON[-1] + 0.25))
    ds.to_netcdf(path, engine="netcdf4")


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
        "transport": "frozen HTTP snapshot of acmadDL deliveries; not a live provider",
        "instructions": "GET the catalogue, then retrieve and hash-check the named resources."}, indent=2) + "\n")
    shutil.copyfile(HERE / "practice.md", public / "practice.md")
    _target_grid(public / "target-grid.nc")
    _module("acquisition").provider_manifest(destination / "provider")


def expected_coordinates(inputs, params):
    science = _module("science")
    with open_model(inputs, params) as ds:
        plat, plon = ds["lat"].values.astype("float64"), ds["lon"].values.astype("float64")
    return {"year": np.asarray(params["training_years"]), "model": np.arange(4), "category": np.arange(3), "stream": np.arange(3),
            "lat": science.TARGET_LAT, "lon": science.TARGET_LON, "plat": plat, "plon": plon}


def open_model(inputs, params):
    science = _module("science")
    return xr.open_dataset(science.provider_files(Path(inputs) / "provider", "ccsm4", int(params["init_month"]))[0])


def compute(provider, params, conventions=None, independent=False, stages=None):
    module = _module("reference_independent" if independent else "science")
    kwargs = {} if stages is None else {"stages": stages}
    return module.compute(Path(provider), params, conventions or {}, **kwargs)


def _raw(dataset):
    return {name: dataset[name].values for name in dataset.variables}


def reference(inputs, params, conventions):
    return _raw(compute(Path(inputs) / "provider", params, conventions, stages=("prepare", "wvg", "ereg")))


def independent(inputs, params, conventions):
    return _raw(compute(Path(inputs) / "provider", params, conventions, independent=True, stages=("prepare", "wvg", "ereg")))


def _rehash(provider):
    path = provider / "catalog.json"
    catalog = json.loads(path.read_text())
    for row in catalog["resources"]:
        source = provider / row["path"]
        row.update(sha256=hashlib.sha256(source.read_bytes()).hexdigest(), bytes=source.stat().st_size)
    path.write_text(json.dumps(catalog, indent=2) + "\n")


def _scale_years(path, variable, time_name, factor_of_year):
    with xr.open_dataset(path, engine="netcdf4") as ds:
        changed = ds.load()
    field = changed[variable]
    attrs = dict(field.attrs)
    years = field[time_name].dt.year.values
    factors = xr.DataArray(np.array([factor_of_year(int(y)) for y in years], dtype="float64"), dims=[time_name], coords={time_name: field[time_name]})
    changed[variable] = (field.astype("float64") * factors).astype(field.dtype)
    changed[variable].attrs = attrs
    temporary = path.with_suffix(".tmp.nc")
    changed.to_netcdf(temporary, engine="netcdf4")
    temporary.replace(path)


def perturb_inputs(inputs, seed, kind="data"):
    """data: scale every model issuance and every observed month by a random per-year factor.
    held_out: scale only the first training year's observed rainfall, which must leave that year's hindcasts unchanged."""
    root, rng = Path(inputs), np.random.default_rng(seed)
    params = json.loads((root / "instance.json").read_text())
    provider = root / "provider"
    science = _module("science")
    if kind == "data":
        factor = {int(y): float(rng.uniform(0.75, 1.3)) for y in range(1990, 2020)}
        for model in science.MODELS:
            for path in science.provider_files(provider, model, int(params["init_month"])):
                _scale_years(path, "precip", "init_time", lambda y: factor[y])
        _scale_years(provider / "observations/chirps-v2p0-monthly-0p05.nc", "precip", "time", lambda y: factor[y])
    elif kind == "held_out":
        first = int(params["training_years"][0])
        _scale_years(provider / "observations/chirps-v2p0-monthly-0p05.nc", "precip", "time", lambda y: 2.75 if y == first else 1.0)
    else:
        raise ValueError(kind)
    _rehash(provider)


# ---- invariants: the local verdicts ---------------------------------------------------

def _support(results):
    return results["prepare_support"] > 0.5


def probabilities_valid(results, params, inputs=None):
    epsilon = 1e-9
    support = _support(results)
    names = {"wvg_hindcast_probability": 1, "wvg_forecast_probability": 0, "ereg_model_hindcast_probability": 2, "ereg_model_forecast_probability": 1,
             "ereg_hindcast_probability": 1, "ereg_forecast_probability": 0, "cca_hindcast_probability": 1, "cca_forecast_probability": 0,
             "combine_hindcast_probability": 1, "combine_forecast_probability": 0, "issue_forecast_probability": 0}
    for name, axis in names.items():
        p = results[name]
        total = p.sum(axis=axis)
        bounded = np.all(p >= -epsilon) and np.all(p <= 1 + epsilon)
        on = np.broadcast_to(support, total.shape)
        if not (bounded and np.all(np.abs(total[on] - 1) <= epsilon) and np.all(np.abs(p.swapaxes(0, axis)[..., ~support]) <= epsilon)):
            return False, f"{name}: probabilities must be bounded, sum to one on supported cells and be zero elsewhere."
    return True, "Every probability array is bounded, sums to one on supported cells and is zero on unsupported cells."


def support_consistent(results, params, inputs=None):
    support = _support(results)
    if not np.array_equal(results["combine_available_streams"] > 0.5, support):
        return False, "combine_available_streams must be positive exactly on supported cells."
    lower, upper = results["prepare_tercile_lower_mm"], results["prepare_tercile_upper_mm"]
    if np.any(lower[support] > upper[support] + 1e-9):
        return False, "The lower tercile boundary exceeds the upper one on some supported cell."
    if not np.all(np.isin(results["prepare_observed_category"], [0, 1, 2])):
        return False, "Observed categories must be 0, 1 or 2."
    return True, "Support, boundaries and categories are mutually consistent."


def equal_stream_combination(results, params, inputs=None):
    gap = max(float(np.max(np.abs(results["combine_hindcast_probability"] - np.mean([results[f"{s}_hindcast_probability"] for s in ("cca", "ereg", "wvg")], axis=0)))),
              float(np.max(np.abs(results["combine_forecast_probability"] - np.mean([results[f"{s}_forecast_probability"] for s in ("cca", "ereg", "wvg")], axis=0)))))
    return gap <= 1e-9, f"Maximum deviation of the objective from the equal-weight stream average: {gap:g}."


def score_identity(results, params, inputs=None):
    """verify_* recomputed from the submission's own probabilities and categories."""
    science = _module("science")
    support = _support(results)
    categories = results["prepare_observed_category"].astype(int)
    streams = [results[f"{s}_hindcast_probability"] for s in ("cca", "ereg", "wvg")]
    baseline = science.rps(np.full_like(streams[0], 1 / 3), categories).mean(0)
    stream_rps = np.stack([science.rps(p, categories).mean(0) for p in streams])
    objective_rps = science.rps(results["combine_hindcast_probability"], categories).mean(0)
    expected = {"verify_stream_rps": stream_rps * support, "verify_objective_rps": objective_rps * support, "verify_climatology_rps": baseline * support,
                "verify_stream_rpss": 1 - stream_rps[:, support].mean(1) / baseline[support].mean(),
                "verify_objective_rpss": 1 - objective_rps[support].mean() / baseline[support].mean()}
    gap = max(float(np.max(np.abs(np.asarray(results[name], dtype="float64") - value))) for name, value in expected.items())
    return gap <= 1e-7, f"Maximum discrepancy between stated and recomputed verification scores: {gap:g}."


def issue_identity(results, params, inputs=None):
    science = _module("science")
    gap = float(np.max(np.abs(results["issue_forecast_probability"] - results["combine_forecast_probability"])))
    dominant = science.dominant(results["combine_forecast_probability"]) * _support(results)
    same = np.array_equal(results["issue_dominant_category"].astype(int), dominant)
    return gap <= 1e-9 and same, f"Issued probabilities differ from the objective by at most {gap:g}; dominant categories {'agree' if same else 'disagree'}."


def cca_agreement(results, params, inputs=None):
    """Method-blind gate: the submission's CCA must correlate with the controller's CCA on the same
    inputs and must not fall short of its cross-validated skill by more than the margin."""
    if inputs is None:
        return False, "No inputs available to compute the controller's CCA."
    science = _module("science")
    reference = science.compute(Path(inputs) / "provider", params, {}, stages=("prepare", "cca"))
    support = _support(results) & (reference["prepare_support"].values > 0)
    correlations = []
    for name in ("cca_hindcast_probability", "cca_forecast_probability"):
        mine, theirs = results[name], reference[name].values
        for k in range(3):
            a, b = np.moveaxis(mine, -3, 0)[k][..., support].ravel(), np.moveaxis(theirs, -3, 0)[k][..., support].ravel()
            if a.std() < 1e-12 or b.std() < 1e-12:
                correlations.append(0.0)
            else:
                correlations.append(float(np.corrcoef(a, b)[0, 1]))
    categories = results["prepare_observed_category"].astype(int)
    baseline = science.rps(np.full_like(results["cca_hindcast_probability"], 1 / 3), categories).mean(0)[support].mean()
    mine = 1 - science.rps(results["cca_hindcast_probability"], categories).mean(0)[support].mean() / baseline
    theirs = 1 - science.rps(reference["cca_hindcast_probability"].values, reference["prepare_observed_category"].values.astype(int)).mean(0)[support].mean() / baseline
    ok = min(correlations) >= CCA_CORRELATION_FLOOR and mine >= theirs - CCA_RPSS_MARGIN
    return ok, (f"Minimum per-category correlation with the controller's CCA {min(correlations):.3f} (floor {CCA_CORRELATION_FLOOR}); "
                f"cross-validated RPSS {mine:.4f} against the controller's {theirs:.4f} (margin {CCA_RPSS_MARGIN}).")


INVARIANTS = {"probabilities_valid": probabilities_valid, "support_consistent": support_consistent, "equal_stream_combination": equal_stream_combination,
              "score_identity": score_identity, "issue_identity": issue_identity, "cca_agreement": cca_agreement}


def _first_year_hindcasts(results, inputs, params):
    index = int(np.flatnonzero(results["year"] == params["training_years"][0])[0])
    return {name: results[name][index:index + 1] for name in ("wvg_hindcast_probability", "ereg_hindcast_probability", "cca_hindcast_probability")} | \
           {"ereg_model_hindcast_probability": results["ereg_model_hindcast_probability"][:, index:index + 1]}


INVARIANCE_PROBES = {"held_out_year_isolation": {
    "perturb": "held_out", "unchanged": _first_year_hindcasts,
    "passes": "Changing a training year's observed rainfall leaves that year's own hindcast probabilities unchanged in every stream.",
    "fails": "A year's own observation enters its hindcast in at least one stream."}}


def expected_claims(results, params):
    rpss = list(np.asarray(results["verify_stream_rpss"], dtype="float64")) + [float(results["verify_objective_rpss"])]
    return {"hindcast_skill": [{"positive"} if v > 1e-9 else {"nonpositive"} if v < -1e-9 else {"positive", "nonpositive"} for v in rpss]}


def _withheld_category(private, params, module):
    science = _module("science")
    with xr.open_dataset(Path(private) / "private-targets/chirps-v2p0-monthly-0p05-2015.nc") as ds:
        withheld = ds.load()
    with xr.open_dataset(Path(private) / "provider/observations/chirps-v2p0-monthly-0p05.nc") as ds:
        training = ds.load()
    init, years = int(params["init_month"]), [int(y) for y in params["training_years"]]
    observed = science.observed_seasonal(training, init, years)
    target = science.observed_seasonal(withheld, init, [int(params["forecast_year"])])
    observed_t, support = science.regrid_observations(observed, "conservative")
    target_t, _ = science.regrid_observations(target, "conservative")
    bounds = science.thresholds(observed_t.values)
    return science.category(target_t.values[0], bounds), support


def score(results, params, private, split):
    if split != "forecast_year":
        raise ValueError(split)
    science = _module("science")
    category, support = _withheld_category(private, params, science)
    probabilities = results["issue_forecast_probability"]
    scored = science.rps(probabilities, category)[support]
    baseline = science.rps(np.full_like(probabilities, 1 / 3), category)[support]
    return {"split": split, "rps": float(scored.mean()), "climatology_rps": float(baseline.mean()), "rpss": float(1 - scored.mean() / baseline.mean()),
            "year": int(params["forecast_year"]), "cells": int(support.sum()), "ranking_enabled": False}


def independent_score(results, params, private, split):
    from math import fsum
    if split != "forecast_year":
        raise ValueError(split)
    category, support = _withheld_category(private, params, _module("science"))
    probabilities = results["issue_forecast_probability"]
    scores, baselines = [], []
    for j, k in zip(*np.nonzero(support)):
        label = int(category[j, k])
        cumulative, error, base = 0.0, 0.0, 0.0
        for c in range(3):
            cumulative += float(probabilities[c, j, k])
            truth = float(c >= label)
            error += (cumulative - truth) ** 2
            base += ((c + 1) / 3 - truth) ** 2
        scores.append(error)
        baselines.append(base)
    mean, baseline = fsum(scores) / len(scores), fsum(baselines) / len(baselines)
    return {"split": split, "rps": mean, "climatology_rps": baseline, "rpss": 1 - mean / baseline,
            "year": int(params["forecast_year"]), "cells": len(scores), "ranking_enabled": False}


def sandbox_factory(*args, **kwargs):
    return _module("acquisition").sandbox_factory(*args, **kwargs)


def executor_factory(executor):
    return _module("acquisition").executor_factory(executor)


def acquisition_evidence(scratch, destination=None):
    return _module("acquisition").acquisition_evidence(scratch, destination)
