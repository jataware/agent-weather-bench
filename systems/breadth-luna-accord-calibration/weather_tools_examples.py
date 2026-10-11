"""Synthetic public-API smoke test; no task files, private answers, or solver."""
from datetime import datetime
import json

import numpy as np
import xarray as xr
from acmaddl.normalize import normalize
from africas2s import calibrate


def normalization_example():
    raw = xr.Dataset(
        {"rain_rate": (("init_time", "member", "lead_time", "lat", "lon"),
                       np.full((2, 3, 3, 2, 2), 2.0, dtype="float64"))},
        coords={"init_time": np.array(["2010-05-01", "2011-05-01"], dtype="datetime64[ns]"),
                "member": [0, 1, 2], "lead_time": [2, 3, 4],
                "lat": [0.0, 1.0], "lon": [30.0, 31.0]})
    config = {"variables": {"precip": {"native_name": "rain_rate", "units": "mm/day",
                                        "target_units": "mm/day"}},
              "target_range": (datetime(2010, 6, 1), datetime(2011, 8, 31)),
              "leadtime_month": [2, 3, 4]}
    result = normalize(raw, config, "precip", year_index=True).precip
    np.testing.assert_allclose(result.values, 2.0 * (30 + 31 + 31), rtol=0, atol=1e-12)
    assert result.attrs["units"] == "mm"
    return {"dimensions": list(result.dims), "shape": list(result.shape),
            "units": result.attrs["units"]}


def calibration_example():
    rng = np.random.default_rng(19)
    years = np.arange(2010, 2022)
    new_years = [2022, 2023]
    grid = {"lat": [0.0, 1.0], "lon": [30.0, 31.0]}
    observed = xr.DataArray(rng.uniform(100, 500, (12, 2, 2)),
                            dims=("year", "lat", "lon"), coords={"year": years, **grid})
    hindcast = xr.DataArray(observed.values[:, None] * .8 + rng.normal(0, 25, (12, 3, 2, 2)),
                            dims=("year", "member", "lat", "lon"),
                            coords={"year": years, "member": [0, 1, 2], **grid})
    forecast = xr.DataArray(rng.uniform(120, 400, (2, 3, 2, 2)), dims=hindcast.dims,
                            coords={"year": new_years, "member": [0, 1, 2], **grid})
    pairs = {"example_model": (hindcast, forecast)}
    cv = calibrate(pairs, observed, method="ereg", cv="loyo")
    individual = [calibrate(pairs, observed, method="ereg", forecast_year=y).expand_dims(year=[y])
                  for y in new_years]
    prediction = xr.concat(individual, dim="year").transpose("year", "tercile", "lat", "lon")
    for probabilities in (cv, prediction):
        assert np.isfinite(probabilities.values).all()
        np.testing.assert_allclose(probabilities.sum("tercile"), 1.0, atol=1e-12)
    changed = forecast.copy(deep=True)
    changed.loc[dict(year=new_years[0])] *= 2.0
    unaffected = calibrate({"example_model": (hindcast, changed)}, observed,
                           method="ereg", forecast_year=new_years[1])
    np.testing.assert_array_equal(unaffected.values, prediction.sel(year=new_years[1]).values)
    return {"historical_dimensions": list(cv.dims), "historical_shape": list(cv.shape),
            "forecast_dimensions": list(prediction.dims), "forecast_shape": list(prediction.shape),
            "tercile_labels": prediction.tercile.values.tolist(), "new_year_isolation": "pass"}


if __name__ == "__main__":
    print(json.dumps({"normalize": normalization_example(), "calibrate": calibration_example(),
                      "synthetic_only": True}))
