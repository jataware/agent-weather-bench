"""Frozen rank calibration with conservative fine detail, on real Kenya data."""
import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import xarray as xr

from assessment.sources import restore

HERE = Path(__file__).resolve().parent


def module(name):
    loader = importlib.util.spec_from_file_location(f"downscaling_{name}", HERE / f"{name}.py")
    loaded = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(loaded)
    return loaded


def prepare(private, source_dir):
    return restore(HERE, private, source_dir)


def candidate_instances():
    return [{"id": f"train-to-{end}--forecast-{start}-{stop}", "training_end": end,
             "forecast_years": list(range(start, stop + 1))}
            for end in (2006, 2008) for start, stop in ((2009, 2012), (2013, 2016))]


def brief_fields(params):
    return {"training_end": params["training_end"], "forecast_start": params["forecast_years"][0],
            "forecast_end": params["forecast_years"][-1]}


def stage_inputs(private, params, destination):
    private, destination = Path(private), Path(destination)
    destination.mkdir(parents=True)
    source = private / "agent-inputs"
    for path in source.iterdir():
        if path.is_file() and path.suffix != ".nc":
            shutil.copyfile(path, destination / path.name)
    with xr.open_dataset(source / "fine-training.nc") as data:
        data.sel(year=slice(None, params["training_end"])).to_netcdf(destination / "fine-training.nc")
    with xr.open_dataset(source / "coarse-forecast.nc") as data:
        years = list(range(1993, params["training_end"] + 1)) + params["forecast_years"]
        data.sel(year=years).to_netcdf(destination / "coarse-forecast.nc")
    shutil.copyfile(source / "geometry.nc", destination / "geometry.nc")
    shutil.copyfile(HERE / "algorithm.md", destination / "algorithm.md")
    (destination / "instance.json").write_text(json.dumps(params) + "\n")


def _rewrite(path, transform):
    with xr.open_dataset(path) as data:
        changed = data.load()
    transform(changed)
    changed.to_netcdf(path.with_suffix(".tmp"))
    path.with_suffix(".tmp").replace(path)


def perturb_inputs(inputs, seed, kind="data"):
    inputs, rng = Path(inputs), np.random.default_rng(seed)
    if kind == "raw_affine":
        def change(data):
            data["raw_predictor"] = data.raw_predictor * 1.75 + 11
        _rewrite(inputs / "coarse-forecast.nc", change)
    elif kind in ("data", "held_out_year"):
        def change(data):
            values = data.seasonal_total.values.copy()
            if kind == "held_out_year":
                values[len(values) // 2] *= 1.8
            else:
                values *= rng.uniform(0.7, 1.6, (len(values), 1, 1))
                values *= rng.uniform(0.85, 1.15, values.shape[1:])
            data["seasonal_total"] = (data.seasonal_total.dims, values, data.seasonal_total.attrs)
        _rewrite(inputs / "fine-training.nc", change)
    else:
        raise ValueError(kind)


def arrays(forecast, hindcast):
    return {"train_year": hindcast.year.values, "forecast_year": forecast.year.values,
            "latitude": forecast.lat.values, "longitude": forecast.lon.values, "coarse_cell": forecast.coarse_cell.values,
            "hindcast_mm": hindcast.rainfall_mm.values, "hindcast_coarse_mm": hindcast.mapped_coarse_mm.values,
            "forecast_mm": forecast.rainfall_mm.values, "forecast_coarse_mm": forecast.mapped_coarse_mm.values,
            "area_m2": forecast.area_m2.values, "coarse_cell_id": forecast.coarse_cell_id.values}


def reference(inputs, params, conventions):
    forecast, hindcast, _ = module("science").build(inputs, defect="full_training" if conventions["validation"] == "full_training" else None)
    return arrays(forecast, hindcast)


def independent(inputs, params, conventions):
    return module("reference_independent").reference(inputs, params, conventions)


def expected_coordinates(inputs, params):
    with xr.open_dataset(Path(inputs) / "fine-training.nc") as data:
        return {"train_year": data.year.values, "forecast_year": np.array(params["forecast_years"]),
                "latitude": data.lat.values, "longitude": data.lon.values, "coarse_cell": np.arange(4)}


def held_out(results, inputs, params):
    i = len(results["train_year"]) // 2
    return {name: results[name][i:i + 1] for name in ("hindcast_mm", "hindcast_coarse_mm")}


INVARIANCE_PROBES = {
    "held_out_year_isolation": {"perturb": "held_out_year", "unchanged": held_out,
        "passes": "Changing the held-out year's observation leaves that year's hindcast unchanged.",
        "fails": "The hindcast uses its own held-out observation."},
    "raw_scale_invariance": {"perturb": "raw_affine", "unchanged": lambda r, *_: r,
        "passes": "A positive affine change of all raw predictors leaves calibrated rainfall unchanged.",
        "fails": "Calibration depends on an arbitrary positive affine raw predictor scale."},
}


def conservation(results, params, inputs):
    """Each fine forecast and hindcast has the area-weighted mean of its mapped coarse cell."""
    area, cells = results["area_m2"], results["coarse_cell_id"]
    gap = 0.0
    for prefix in ("hindcast", "forecast"):
        for cell in range(4):
            mask = cells == cell
            if not np.any(mask) or area[mask].sum() <= 0:
                return False, "A coarse cell has no positive area."
            mean = (results[f"{prefix}_mm"][:, mask] * area[mask]).sum(axis=1) / area[mask].sum()
            gap = max(gap, float(np.max(np.abs(mean - results[f"{prefix}_coarse_mm"][:, cell]))))
    return gap <= 2e-4, f"largest conservation error is {gap:.6g} mm"


def nonnegative(results, params, inputs):
    """Calibrated rainfall is nonnegative and fine pixel areas are positive."""
    low = min(float(results[name].min()) for name in ("hindcast_mm", "forecast_mm", "hindcast_coarse_mm", "forecast_coarse_mm"))
    return low >= 0 and bool((results["area_m2"] > 0).all()), f"minimum rainfall is {low:.6g} mm"


INVARIANTS = {"conservation": conservation, "nonnegative": nonnegative}


def expected_claims(results, params):
    return {"raw_unit_status": [["unresolved_source_scale"]], "conservation_definition": [["mapped_coarse_area_mean"]]}
