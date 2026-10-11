"""Read-only real-source parity diagnostic for the pinned ACCORD runtime."""
import argparse
import json
from pathlib import Path
import numpy as np
import xarray as xr
import science
import reference_independent


def run(provider, params):
    h, f, hi, fi = {}, {}, {}, {}
    years, new_years = params["training_years"], params["new_years"]
    lat, lon = params["target_latitude"], params["target_longitude"]
    for name in science.MODELS:
        with xr.open_dataset(Path(provider) / "models" / (name + ".nc"), engine="h5netcdf") as ds:
            ds = ds.load()
        totals = np.asarray(science.seasonal_model(ds, years + new_years, lat, lon))
        independent = reference_independent.seasonal_model(ds, years + new_years, lat, lon)
        h[name], f[name] = totals[:len(years)], totals[len(years):]
        hi[name], fi[name] = independent[:len(years)], independent[len(years):]
    with xr.open_dataset(Path(provider) / "observations/chirps-monthly-pre2016.nc", engine="h5netcdf") as ds:
        ds = ds.load()
    obs = np.asarray(science.seasonal_observed(ds, years, lat, lon))
    obs_i = reference_independent.seasonal_observed(ds, years, lat, lon)
    deciding = science.evaluate(h, obs, f, years, new_years, lat, lon)
    independent = reference_independent.evaluate(hi, obs_i, fi, years, new_years, lat, lon)
    cv, new = science.parity_check(h, obs, f, years, new_years, lat, lon)
    gaps = {"independent_" + name: float(np.max(np.abs(deciding[name].values - independent[name].values))) for name in deciding.data_vars}
    gaps["native_combined_cv"] = float(np.max(np.abs(deciding.hindcast_probability.values - cv.combined.transpose("year", "tercile", "lat", "lon").values)))
    for i, name in enumerate(science.MODELS):
        gaps["native_" + name + "_cv"] = float(np.max(np.abs(deciding.model_hindcast_probability.isel(model=i).values - cv.per_model[name].transpose("year", "tercile", "lat", "lon").values)))
    for t, prediction in enumerate(new):
        gaps["native_combined_new_" + str(new_years[t])] = float(np.max(np.abs(deciding.forecast_probability.isel(new_year=t).values - prediction.combined.transpose("tercile", "lat", "lon").values)))
        for i, name in enumerate(science.MODELS):
            gaps["native_" + name + "_new_" + str(new_years[t])] = float(np.max(np.abs(deciding.model_forecast_probability.isel(model=i, new_year=t).values - prediction.per_model[name].transpose("tercile", "lat", "lon").values)))
    result = {"passed": all(value < (2e-6 if key.endswith("_mm") else 2e-10) for key, value in gaps.items()),
              "max_absolute_discrepancies": gaps,
              "members": {name: h[name].shape[1] for name in h},
              "cv_rps": float(deciding.cv_rps), "cv_rps_climatology": float(deciding.cv_rps_climatology), "cv_rpss": float(deciding.cv_rpss),
              "forecast_spatial_mean_probabilities": deciding.forecast_probability.mean(("lat", "lon")).values.tolist(),
              "max_abs_seasonal_mm": max(float(np.abs(deciding[name]).max()) for name in ("train_model_mean_mm", "train_observed_mm", "new_model_mean_mm"))}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--instance", required=True)
    args = parser.parse_args()
    result = run(args.provider, json.loads(Path(args.instance).read_text()))
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(0 if result["passed"] else 1)
