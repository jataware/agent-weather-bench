"""Offline public-API examples on synthetic data; no benchmark files or answers."""
from datetime import datetime
import json

import numpy as np
import xarray as xr
from acmaddl.normalize import normalize
from africas2s import calibrate


def normalization_example():
    # Two February initializations, three monthly means, two members, 2x2 grid.
    raw = xr.Dataset(
        {"tprate": (("forecast_reference_time", "number", "forecastMonth",
                     "latitude", "longitude"),
                    np.full((2, 2, 3, 2, 2), 2.0 / (86400 * 1000), dtype="float64"))},
        coords={"forecast_reference_time": np.array(["2000-02-01", "2001-02-01"],
                                                    dtype="datetime64[ns]"),
                "number": [0, 1], "forecastMonth": [2, 3, 4],
                "latitude": [1.0, 0.0], "longitude": [30.0, 31.0]})
    config = {"variables": {"precip": {"native_name": "tprate", "units": "m s-1",
                                        "target_units": "mm/day"}},
              "target_range": (datetime(2000, 3, 1), datetime(2000, 5, 31)),
              "leadtime_month": [2, 3, 4]}
    result = normalize(raw, config, "precip", year_index=True).precip
    # Constant 2 mm/day over March, April, May: 184 mm in each year.
    np.testing.assert_allclose(result.values, 184.0, rtol=0, atol=1e-10)
    assert result.attrs["units"] == "mm"
    return {"dimensions": list(result.dims), "shape": list(result.shape),
            "units": result.attrs["units"], "years": result.year.values.tolist()}


def calibration_example():
    rng = np.random.default_rng(7)
    years = np.arange(2000, 2012)
    coords = {"year": years, "lat": [0.0, 1.0], "lon": [30.0, 31.0]}
    observed = xr.DataArray(rng.uniform(100, 400, (12, 2, 2)),
                            dims=("year", "lat", "lon"), coords=coords)
    pairs = {}
    for name, members in (("centre_a", 3), ("centre_b", 5)):
        hindcast = xr.DataArray(observed.values[:, None] + rng.normal(0, 30, (12, members, 2, 2)),
                                dims=("year", "member", "lat", "lon"),
                                coords={**coords, "member": np.arange(members)})
        forecast = xr.DataArray(rng.uniform(100, 400, (1, members, 2, 2)),
                                dims=hindcast.dims,
                                coords={**coords, "year": [2012], "member": np.arange(members)})
        pairs[name] = (hindcast, forecast)
    cv = calibrate(pairs, observed, method="ereg", cv="loyo", return_components=True)
    prediction = calibrate(pairs, observed, method="ereg", forecast_year=2012,
                           return_components=True)
    for result in (cv, prediction):
        assert np.isfinite(result.combined.values).all()
        np.testing.assert_allclose(result.combined.sum("tercile"), 1.0, atol=1e-12)
        np.testing.assert_allclose(result.combined,
                                   sum(result.per_model.values()) / len(pairs), atol=1e-12)
    return {"cv_dimensions": list(cv.combined.dims), "cv_shape": list(cv.combined.shape),
            "forecast_dimensions": list(prediction.combined.dims),
            "forecast_shape": list(prediction.combined.shape),
            "tercile_labels": prediction.combined.tercile.values.tolist(),
            "per_model_keys": list(prediction.per_model)}


if __name__ == "__main__":
    print(json.dumps({"normalize": normalization_example(),
                      "calibrate": calibration_example(), "synthetic_only": True}))
