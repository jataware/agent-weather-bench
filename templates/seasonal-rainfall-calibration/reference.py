"""Reference function and controller hooks for the seasonal rainfall calibration template (process mode).

Three results have a reference answer: the two prepared seasonal totals, and the
skill score of the submission's own cross-validated probabilities. The
probabilities themselves are free: any sound calibration is acceptable.
Implementation A is here; reference_independent.py is implementation B.
"""
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REFERENCE_USES_SUBMISSION = True          # the skill score is recomputed from the submitted probabilities
FILES = ("forecast-development.nc", "observations-development.nc", "forecast.nc", "verification.nc", "training.nc")
DAYS = {"actual": (31, 30, 31), "thirty_days": (30, 30, 30), "rates_not_converted": (1, 1, 1)}

# training years, then the new years to forecast; the last entry of each is exclusive
PERIODS = {"train-1993-2004--new-2005-2006": ((1993, 2005), (2005, 2007)),
           "train-1993-2002--new-2003-2004": ((1993, 2003), (2003, 2005)),
           "train-1993-2000--new-2001-2002": ((1993, 2001), (2001, 2003))}
CELLS = {"all-cells": None, "southern-rows": -1.0}                 # None keeps every row; a number keeps latitudes below it


# ---- data ------------------------------------------------------------------------

def prepare(private, source_dir=None):
    private, records = Path(private), json.loads((HERE / "sources.json").read_text())["files"]
    for name in FILES:
        target = private / name
        if not target.is_file():
            source = Path(source_dir or ROOT / "var/private/tasks/seasonal-calibration") / records[name]["from"]
            if not source.is_file():
                raise ValueError(f"{name} is missing. Pass the private directory of the packaged seasonal-calibration task.")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != records[name]["sha256"]:
            raise ValueError(f"{name} does not match its recorded hash")
    return {"files": len(FILES)}


def _rows(lat, params):
    return np.ones(len(lat), bool) if params["latitude_limit"] is None else lat < params["latitude_limit"]


def _source(private, params):
    """Monthly forecast rates and native observations for every year the instance touches, on its cells."""
    with xr.open_dataset(Path(private) / "forecast-development.nc") as file:
        forecast = file.load()
    with xr.open_dataset(Path(private) / "observations-development.nc") as file:
        observed = file.load()
    return forecast.sel(lat=forecast.lat[_rows(forecast.lat.values, params)]), observed


def _new_forecast(private, params):
    """Seasonal totals by member for the new years, as the operational system would hand them over."""
    (_, _), (first, stop) = params["training_years"], params["new_years"]
    if first >= 2005:
        with xr.open_dataset(Path(private) / "forecast.nc") as file:
            ds = file.load()
        return ds.sel(lat=ds.lat[_rows(ds.lat.values, params)])
    forecast, _ = _source(private, params)
    chosen = forecast.sel(init_time=(forecast.init_time.dt.year >= first) & (forecast.init_time.dt.year < stop))
    totals = (chosen.precip.transpose("init_time", "member", "lead_time", "lat", "lon").values.astype("float64")
              * np.array(DAYS["actual"], dtype="float64")[None, None, :, None, None]).sum(axis=2)
    ds = xr.Dataset({"forecast": (("year", "member", "lat", "lon"), totals)},
                    coords={"year": chosen.init_time.dt.year.values, "member": chosen.member.values, "lat": chosen.lat.values, "lon": chosen.lon.values})
    ds.forecast.attrs["units"] = "mm"
    return ds


def stage_inputs(private, params, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    forecast, observed = _source(private, params)
    first, stop = params["training_years"]
    forecast.sel(init_time=(forecast.init_time.dt.year >= first) & (forecast.init_time.dt.year < stop)).to_netcdf(destination / "forecast-training.nc")
    observed.sel(time=(observed.time.dt.year >= first) & (observed.time.dt.year < stop)).to_netcdf(destination / "observations-training.nc")
    _new_forecast(private, params).to_netcdf(destination / "forecast-new.nc")
    shutil.copyfile(HERE / "guidance.md", destination / "guidance.md")
    (destination / "instance.json").write_text(json.dumps(params, indent=2) + "\n")


def _rewrite(path, change):
    with xr.open_dataset(path) as file:
        ds = file.load()
    change(ds)
    temporary = path.with_name(path.name + ".tmp")
    ds.to_netcdf(temporary)
    temporary.replace(path)


def probe_year(inputs):
    """The middle training year: the one whose observation the isolation probe changes."""
    with xr.open_dataset(Path(inputs) / "forecast-training.nc") as ds:
        years = ds.init_time.dt.year.values
    return int(years[len(years) // 2])


def perturb_inputs(inputs, seed, kind="data"):
    inputs, rng = Path(inputs), np.random.default_rng(seed)
    if kind == "data":                                             # every year moves, so every reference moves
        def forecast(ds):
            factor = 1 + 0.4 * np.sin(np.arange(ds.sizes["init_time"]) + rng.uniform(0, 3))
            values = ds.precip.transpose("member", "init_time", "lead_time", "lat", "lon").values.astype("float64") * factor[None, :, None, None, None]
            ds["precip"] = (("member", "init_time", "lead_time", "lat", "lon"), values.astype("float32"), ds.precip.attrs)
        def observed(ds):
            factor = 1 + 0.35 * np.cos(0.7 * np.arange(ds.sizes["time"]) + rng.uniform(0, 3))
            ds["precip"] = (ds.precip.dims, (ds.precip.values.astype("float64") * factor[:, None, None]).astype("float32"), ds.precip.attrs)
        _rewrite(inputs / "forecast-training.nc", forecast)
        _rewrite(inputs / "observations-training.nc", observed)
    elif kind == "observation_of_one_year":
        year = probe_year(inputs)
        def observed(ds):
            values = ds.precip.values.astype("float64")
            values[ds.time.dt.year.values == year] *= 2.5
            ds["precip"] = (ds.precip.dims, values.astype("float32"), ds.precip.attrs)
        _rewrite(inputs / "observations-training.nc", observed)
    elif kind == "one_new_forecast_year":
        def forecast(ds):
            values = ds.forecast.values.astype("float64").copy()
            values[0] = values[0] * 1.7 + 40                       # the first new year only
            ds["forecast"] = (ds.forecast.dims, values, ds.forecast.attrs)
        _rewrite(inputs / "forecast-new.nc", forecast)
    else:
        raise ValueError("Unknown perturbation: " + str(kind))


def expected_coordinates(inputs, params):
    with xr.open_dataset(Path(inputs) / "forecast-training.nc") as training, xr.open_dataset(Path(inputs) / "forecast-new.nc") as new:
        return {"year": training.init_time.dt.year.values.astype(float), "new_year": new.year.values.astype(float),
                "latitude": training.lat.values.astype(float), "longitude": training.lon.values.astype(float)}


# ---- the reference calculation (implementation A) -----------------------------------

def seasonal_totals(inputs, conventions):
    """(ensemble-mean forecast totals, observed totals on the forecast grid), each [year, lat, lon] in mm."""
    with xr.open_dataset(Path(inputs) / "forecast-training.nc") as file:
        f = file.load()
    with xr.open_dataset(Path(inputs) / "observations-training.nc") as file:
        o = file.load()
    if f.precip.attrs.get("units") != "mm/day" or o.precip.attrs.get("units") != "mm/month":
        raise ValueError("Unexpected source units")
    rates = f.precip.transpose("init_time", "member", "lead_time", "lat", "lon").values.astype("float64")
    forecast = (rates * np.array(DAYS[conventions["month_lengths"]], dtype="float64")[None, None, :, None, None]).sum(axis=2).mean(axis=1)
    years = f.init_time.dt.year.values
    native = o.precip.transpose("time", "lat", "lon").values.astype("float64")
    months = o.time.dt.year.values
    observed = np.empty((len(years), f.sizes["lat"], f.sizes["lon"]))
    for i, lat in enumerate(f.lat.values):
        for j, lon in enumerate(f.lon.values):
            rows = (o.lat.values >= lat - 0.5) & (o.lat.values < lat + 0.5)
            cols = (o.lon.values >= lon - 0.5) & (o.lon.values < lon + 0.5)
            block = native[:, rows][:, :, cols]
            weights = np.cos(np.deg2rad(o.lat.values[rows])) if conventions["observation_weighting"] == "cos_latitude" else np.ones(rows.sum())
            monthly = (block.mean(axis=2) * weights[None, :]).sum(axis=1) / weights.sum()
            observed[:, i, j] = [monthly[months == year].sum() for year in years]
    return forecast, observed


def categories(values, thresholds):
    """0 below, 1 near, 2 above. A total equal to a boundary is near-normal."""
    return np.where(values < thresholds[0], 0, np.where(values > thresholds[1], 2, 1))


def ranked_probability_score(probability, category):
    """probability [..., 3]; category [...] -> score [...]."""
    cumulative = np.cumsum(probability, axis=-1)[..., :2]
    observed = np.stack([category <= 0, category <= 1], axis=-1).astype(float)
    return ((cumulative - observed) ** 2).sum(axis=-1)


def observed_categories(observed, conventions):
    """The category each year's observation falls in, with boundaries from the years the convention allows."""
    out = np.empty(observed.shape)
    for y in range(observed.shape[0]):
        basis = np.delete(observed, y, axis=0) if conventions["category_thresholds"] == "leave_one_out" else observed
        out[y] = categories(observed[y], np.quantile(basis, [1 / 3, 2 / 3], axis=0, method="linear"))
    return out


def hindcast_rpss(probability, observed, conventions):
    """Skill of cross-validated probabilities [year, 3, lat, lon] against a climatological forecast, pooled over years and cells."""
    years = observed.shape[0]
    scores, reference = [], []
    for y in range(years):
        others = np.delete(observed, y, axis=0)
        basis = others if conventions["category_thresholds"] == "leave_one_out" else observed
        thresholds = np.quantile(basis, [1 / 3, 2 / 3], axis=0, method="linear")
        category = categories(observed[y], thresholds)
        scores.append(ranked_probability_score(np.moveaxis(probability[y], 0, -1), category))
        if conventions["climatology_reference"] == "equal_thirds":
            climate = np.full(category.shape + (3,), 1 / 3)
        else:
            fold = categories(others, thresholds)
            climate = np.stack([(fold == k).mean(axis=0) for k in range(3)], axis=-1)
        reference.append(ranked_probability_score(climate, category))
    return float(1 - np.mean(scores) / np.mean(reference))


def reference(inputs, params, conventions, given=None):
    forecast, observed = seasonal_totals(inputs, conventions)
    out = {"forecast_mean_mm": forecast, "observed_total_mm": observed, "observed_category": observed_categories(observed, conventions)}
    if given is not None:
        out["hindcast_rpss"] = np.array(hindcast_rpss(given["hindcast_probability"], observed, conventions))
    return out


def independent(inputs, params, conventions, given=None):
    import importlib.util
    spec = importlib.util.spec_from_file_location("seasonal_reference_independent", HERE / "reference_independent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.answer(inputs, params, conventions, given)


def example_free_results(inputs, params):
    """A fixed, arbitrary set of valid probabilities, so that certification can exercise the skill score."""
    frame = expected_coordinates(inputs, params)
    shape = (len(frame["year"]), 3, len(frame["latitude"]), len(frame["longitude"]))
    raw = 1 + np.sin(np.arange(np.prod(shape)).reshape(shape) * 0.37) ** 2
    return {"hindcast_probability": raw / raw.sum(axis=1, keepdims=True)}


def regression_checks(inputs):
    """Agreement with the reference arrays frozen for the earlier packaged task."""
    private = ROOT / "var/private/templates/seasonal-rainfall-calibration"
    scratch = Path(inputs) / "_regression"
    stage_inputs(private, instance("train-1993-2004--new-2005-2006", "all-cells"), scratch)
    forecast, observed = seasonal_totals(scratch, {"month_lengths": "actual", "observation_weighting": "cos_latitude"})
    shutil.rmtree(scratch)
    with xr.open_dataset(private / "training.nc") as file:
        old = file.load()
    gaps = (float(np.max(np.abs(forecast - old.forecast.transpose("year", "member", "lat", "lon").values.mean(axis=1)))),
            float(np.max(np.abs(observed - old.observed.transpose("year", "lat", "lon").values))))
    return [{"name": "seasonal totals equal the earlier task's reference arrays", "passed": max(gaps) <= 1e-9,
             "detail": f"largest differences: forecast {gaps[0]:.3g} mm, observed {gaps[1]:.3g} mm"}]


# ---- rules, probes and skill --------------------------------------------------------

def _valid_probabilities(results, params, inputs=None):
    worst = 0.0
    for name in ("hindcast_probability", "forecast_probability"):
        p = results[name]
        if p.shape[1] != 3:
            return False, f"{name} must have three categories on its second axis"
        if p.min() < -1e-9 or p.max() > 1 + 1e-9:
            return False, f"{name} has values outside 0 to 1"
        worst = max(worst, float(np.max(np.abs(p.sum(axis=1) - 1))))
    return worst <= 1e-6, f"category probabilities sum to one within {worst:.2g}"


INVARIANTS = {"probabilities_valid": _valid_probabilities}


def _held_out_year(results, inputs, params):
    index = int(np.flatnonzero(results["year"] == probe_year(inputs))[0])
    return {"hindcast_probability": results["hindcast_probability"][index]}


def _other_new_years(results, inputs, params):
    return {"forecast_probability": results["forecast_probability"][1:]}


INVARIANCE_PROBES = {
    "held_out_year_isolation": {
        "perturb": "observation_of_one_year", "unchanged": _held_out_year,
        "passes": "The cross-validated forecast for a year does not move when that year's own observation changes.",
        "fails": "The cross-validated forecast for a year moves when that year's own observation changes, so the year was not held out."},
    "new_years_forecast_separately": {
        "perturb": "one_new_forecast_year", "unchanged": _other_new_years,
        "passes": "The forecast for one new year does not move when another new year's model forecast changes.",
        "fails": "The forecast for one new year moves when another new year's model forecast changes, so the batch was pooled or refitted."},
}


def score(results, params, private, split="new_years"):
    """Skill of the forecast for the new years against their withheld observations. Controller only."""
    scratch_free = {"month_lengths": "actual", "observation_weighting": "cos_latitude"}
    first, stop = params["new_years"]
    forecast, native = _source(private, params)
    if first >= 2005:
        with xr.open_dataset(Path(private) / "verification.nc") as file:
            ds = file.load()
        truth = ds.sel(lat=ds.lat[_rows(ds.lat.values, params)]).observed.transpose("year", "lat", "lon").values
    else:
        truth = _observed_block(forecast, native, range(first, stop), scratch_free)
    training = _observed_block(forecast, native, range(*params["training_years"]), scratch_free)
    thresholds = np.quantile(training, [1 / 3, 2 / 3], axis=0, method="linear")
    category = categories(truth, thresholds)
    rps = ranked_probability_score(np.moveaxis(results["forecast_probability"], 1, -1), category)
    climate = ranked_probability_score(np.full(category.shape + (3,), 1 / 3), category)
    return {"split": split, "rps": float(rps.mean()), "climatology_rps": float(climate.mean()), "rpss": float(1 - rps.mean() / climate.mean()),
            "cases": int(category.size), "years": int(category.shape[0]),
            "caveat": "Two years on a handful of neighbouring cells: far too few cases to rank methods."}


def _observed_block(forecast, native, years, conventions):
    values = native.precip.transpose("time", "lat", "lon").values.astype("float64")
    months = native.time.dt.year.values
    out = np.empty((len(list(years)), forecast.sizes["lat"], forecast.sizes["lon"]))
    for i, lat in enumerate(forecast.lat.values):
        for j, lon in enumerate(forecast.lon.values):
            rows = (native.lat.values >= lat - 0.5) & (native.lat.values < lat + 0.5)
            cols = (native.lon.values >= lon - 0.5) & (native.lon.values < lon + 0.5)
            weights = np.cos(np.deg2rad(native.lat.values[rows]))
            monthly = (values[:, rows][:, :, cols].mean(axis=2) * weights[None, :]).sum(axis=1) / weights.sum()
            out[:, i, j] = [monthly[months == year].sum() for year in years]
    return out


# ---- instances and brief -----------------------------------------------------------

def instance(period, cells):
    training, new = PERIODS[period]
    return {"id": f"{period}--{cells}", "training_years": list(training), "new_years": list(new), "latitude_limit": CELLS[cells]}


def candidate_instances():
    return [instance(period, cells) for period in PERIODS for cells in CELLS]


def brief_fields(params):
    (first, stop), (new_first, new_stop) = params["training_years"], params["new_years"]
    return {"training_span": f"{first}–{stop - 1}", "new_span": f"{new_first} and {new_stop - 1}" if new_stop - new_first == 2 else f"{new_first}–{new_stop - 1}"}
