"""Probe precision must not manufacture a held-out-observation dependency."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template


def fixture_inputs(tmp_path):
    root = tmp_path / "inputs"
    provider = root / "provider"
    (provider / "models").mkdir(parents=True)
    (provider / "observations").mkdir()
    params = {"training_years": [1993, 1994, 1995, 1996]}
    (root / "instance.json").write_text(json.dumps(params))
    times = np.array([f"{year}-{month:02}-01" for year in params["training_years"] for month in (3, 4, 5)], dtype="datetime64[ns]")
    values = (np.arange(48, dtype="float32").reshape(12, 2, 2) * np.float32(.731) + np.float32(19.117))
    observed = xr.Dataset({"precip": (("time", "latitude", "longitude"), values)},
                          coords={"time": times, "latitude": [0., 1.], "longitude": [36., 37.]})
    observed.precip.attrs["units"] = "mm/month"
    observed.to_netcdf(provider / "observations/chirps-monthly-pre2016.nc", engine="h5netcdf")
    for model in ("ecmwf", "cmcc", "ukmo", "meteofrance"):
        ds = xr.Dataset({"tprate": (("forecast_reference_time", "latitude", "longitude"), values[:4] * np.float32(1e-8))},
                        coords={"forecast_reference_time": np.array([f"{y}-02-01" for y in params["training_years"]], dtype="datetime64[ns]"),
                                "latitude": [0., 1.], "longitude": [36., 37.]})
        ds.tprate.attrs["units"] = "m s**-1"
        ds.to_netcdf(provider / "models" / (model + ".nc"), engine="h5netcdf")
    paths = sorted(provider.rglob("*.nc"))
    catalog = {"resources": [{"path": str(p.relative_to(provider)), "bytes": p.stat().st_size,
                               "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}
    (provider / "catalog.json").write_text(json.dumps(catalog))
    return root, paths


def loaded(path):
    with xr.open_dataset(path, engine="h5netcdf") as ds:
        return ds.load()


@pytest.mark.parametrize("kind", ["data", "held_out"])
def test_perturbation_preserves_source_precision_and_untouched_records(tmp_path, kind):
    template = Template("mam-multimodel-outlook")
    inputs, paths = fixture_inputs(tmp_path)
    before = {p: loaded(p) for p in paths}
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    template.hooks.perturb_inputs(inputs, 19, kind)
    for path in paths:
        original, changed = before[path], loaded(path)
        name = next(iter(original.data_vars))
        assert original[name].dtype == changed[name].dtype == np.dtype("float32")
        assert original[name].attrs == changed[name].attrs
        for coordinate in original.coords:
            np.testing.assert_array_equal(original[coordinate], changed[coordinate])
        if kind == "held_out" and "models" in path.parts:
            assert hashlib.sha256(path.read_bytes()).hexdigest() == hashes[path]
        elif kind == "held_out":
            outside = original.time.dt.year.values != 1993
            assert np.array_equal(original[name].values[outside].view("uint8"), changed[name].values[outside].view("uint8"))
            assert np.any(original[name].values[~outside] != changed[name].values[~outside])
        else:
            assert np.any(original[name].values != changed[name].values)
    template.hooks._module("acquisition").provider_manifest(inputs / "provider")


def test_dtype_preserving_probe_accepts_isolated_fold_but_catches_leaked_thresholds(tmp_path):
    template = Template("mam-multimodel-outlook")
    inputs, _ = fixture_inputs(tmp_path)
    path = inputs / "provider/observations/chirps-monthly-pre2016.nc"
    def seasonal_float32():
        monthly = loaded(path).precip
        return np.stack([monthly.sel(time=monthly.time.dt.year == year).sum("time").values
                         for year in (1993, 1994, 1995, 1996)]).astype("float64")
    before = seasonal_float32()
    template.hooks.perturb_inputs(inputs, 19, "held_out")
    after = seasonal_float32()
    np.testing.assert_array_equal(before[1:], after[1:])
    x = np.broadcast_to(np.array([180., 130., 170., 210.])[:, None, None], before.shape)
    science = template.hooks._module("science")
    def probabilities(y, leaked):
        thresholds = np.quantile(y if leaked else y[1:], [1 / 3, 2 / 3], axis=0)
        return science.gaussian_terciles(x[1:], y[1:], x[0], thresholds)[0]
    np.testing.assert_array_equal(probabilities(before, False), probabilities(after, False))
    gap = float(np.max(np.abs(probabilities(before, True) - probabilities(after, True))))
    assert gap > template.spec["results"]["model_hindcast_probability"]["tolerance"]["atol"]
