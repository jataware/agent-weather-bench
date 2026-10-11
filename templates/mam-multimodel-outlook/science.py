"""MAM source normalization and prescribed default-Wilks ensemble regression.

The deciding implementation uses NumPy/SciPy, never africaS2S. Native-library
parity is an optional diagnostic, not the definition of a correct submission.
All scientific file I/O is serial. Source retrieval is supplied by the task's
catalogue adapter; this module accepts unaltered monthly datasets or arrays.
"""
from calendar import monthrange
import numpy as np
import xarray as xr
from scipy.special import ndtr

MODELS = ("ecmwf", "cmcc", "ukmo", "meteofrance")
TERCILES = (0, 1, 2)  # below, normal, above; equality belongs to normal


def seasonal_model(ds, years, latitude=None, longitude=None, defect=None):
    """Integrate native monthly mean m/s, selecting MAM by VALID month.

    forecastMonth=1 denotes the initialization month. Interpolate onto an
    explicitly supplied target grid before any per-cell regression. No
    extrapolation, annual positional assumptions, or calendar-day shortcuts.
    """
    name = next((n for n in ("tprate", "tp", "precip", "precipitation") if n in ds.data_vars), None)
    if name is None:
        raise ValueError("No recognized native precipitation variable")
    rate = ds[name]
    units = rate.attrs.get("units", "").replace(" ", "")
    if units not in ("ms**-1", "ms^-1", "m/s", "ms-1"):
        raise ValueError(f"Expected native mean precipitation m/s, got {units!r}")
    time = next((n for n in ("forecast_reference_time", "indexing_time") if n in rate.dims), None)
    if time is None:
        raise ValueError("Missing native initialization time dimension")
    pieces = []
    for year in years:
        chosen = rate.sel({time: rate[time].dt.year == int(year)})
        if chosen.sizes[time] != 1:
            raise ValueError(f"Expected one initialization in {year}")
        init_month = int(chosen[time].dt.month.item())
        init_year = int(chosen[time].dt.year.item())
        leads = chosen.forecastMonth.values.astype(int)
        valid_month = (init_month - 1 + leads - 1) % 12 + 1
        valid_year = init_year + (init_month - 1 + leads - 1) // 12
        fields = []
        for month in (3, 4, 5):
            hit = np.flatnonzero((valid_month == month) & (valid_year == year))
            if len(hit) != 1:
                raise ValueError(f"Expected one valid {year}-{month:02d} monthly field")
            days = 30 if defect == "thirty_days" else monthrange(int(year), month)[1]
            factor = days * (1 if defect == "missing_seconds" else 86400) * (1 if defect == "missing_millimetres" else 1000)
            fields.append(chosen.isel({time: 0, "forecastMonth": int(hit[0])}, drop=True).astype("float64") * factor)
        total = sum(fields).rename({"number": "member", "latitude": "lat", "longitude": "lon"})
        if latitude is not None and longitude is not None:
            total = total.sortby("lat").sortby("lon").interp(lat=np.asarray(latitude), lon=np.asarray(longitude), method="linear")
        pieces.append(total.expand_dims(year=[int(year)]))
    out = xr.concat(pieces, "year").transpose("year", "member", "lat", "lon")
    if not np.isfinite(out.values).all():
        raise ValueError("Selected source/target cells must have complete finite MAM values")
    out.attrs["units"] = "mm"
    return out


def seasonal_observed(ds, years, latitude=None, longitude=None):
    name = next((n for n in ("precip", "precipitation", "tp", "prcp") if n in ds.data_vars), None)
    if name is None:
        raise ValueError("No recognized observed precipitation variable")
    rain = ds[name]
    renames = {k: v for k, v in (("latitude", "lat"), ("longitude", "lon"), ("Y", "lat"), ("X", "lon"), ("T", "time")) if k in rain.dims}
    rain = rain.rename(renames)
    units = rain.attrs.get("units", "").lower().replace(" ", "")
    if units not in ("mm", "mm/month", "mmmonth-1", "mmmonth**-1"):
        raise ValueError(f"Expected observed monthly totals mm, got {units!r}")
    pieces = []
    for year in years:
        chosen = rain.sel(time=(rain.time.dt.year == year) & rain.time.dt.month.isin([3, 4, 5]))
        if chosen.sizes["time"] != 3 or set(chosen.time.dt.month.values.tolist()) != {3, 4, 5}:
            raise ValueError(f"Expected exactly three observed MAM months in {year}")
        total = chosen.astype("float64").sum("time", skipna=False)
        if latitude is not None and longitude is not None:
            total = total.sortby("lat").sortby("lon").interp(lat=np.asarray(latitude), lon=np.asarray(longitude), method="linear")
        pieces.append(total.expand_dims(year=[int(year)]))
    out = xr.concat(pieces, "year").transpose("year", "lat", "lon")
    if not np.isfinite(out.values).all():
        raise ValueError("Observed target cells must have complete finite MAM values")
    out.attrs["units"] = "mm"
    return out


def gaussian_terciles(x, y, forecast, thresholds=None):
    """Vectorized per-cell OLS and leverage-inflated prediction variance.

    x/y=(year,...), forecast=(...). Complete finite fixture is required.
    Constant predictors are uncalibratable, matching the native API.
    """
    x, y, forecast = map(lambda z: np.asarray(z, dtype="float64"), (x, y, forecast))
    if x.shape != y.shape or len(x) < 3 or not all(np.isfinite(a).all() for a in (x, y, forecast)):
        raise ValueError("Need >=3 complete paired finite years")
    xb, yb = x.mean(axis=0), y.mean(axis=0)
    dx, dy = x - xb, y - yb
    sxx = np.sum(dx * dx, axis=0)
    if np.any(sxx < 1e-12):
        raise ValueError("Constant predictor is not calibratable")
    slope = np.sum(dx * dy, axis=0) / sxx
    fitted = yb + slope * dx
    residual_variance = np.sum((y - fitted) ** 2, axis=0) / (len(x) - 2)
    mean = yb + slope * (forecast - xb)
    sigma = np.sqrt(np.maximum(residual_variance * (1 + 1 / len(x) + (forecast - xb) ** 2 / sxx), 1e-12))
    bounds = np.quantile(y, [1 / 3, 2 / 3], axis=0, method="linear") if thresholds is None else thresholds
    below = ndtr((bounds[0] - mean) / sigma)
    above = 1 - ndtr((bounds[1] - mean) / sigma)
    return np.stack([below, 1 - below - above, above]), np.asarray(bounds)


def category(values, thresholds):
    return np.where(values < thresholds[0], 0, np.where(values > thresholds[1], 2, 1)).astype("int16")


def rps(probabilities, observed_category):
    """Unnormalized sum over ordered cumulative categories (range 0..2)."""
    p = np.asarray(probabilities, dtype="float64")
    observed = np.stack([np.asarray(observed_category) == i for i in TERCILES], axis=-3)
    return np.sum((np.cumsum(p, axis=-3) - np.cumsum(observed, axis=-3)) ** 2, axis=-3)


def evaluate(hindcasts, observed, forecasts, years, new_years, latitude, longitude, defect=None):
    """Compute all required diagnostics from seasonal member totals in mm.

    hindcasts/forecasts are model dictionaries, values (year,member,lat,lon).
    observed=(year,lat,lon). Withheld new-year observations are never accepted.
    """
    models = list(hindcasts)
    options = defect if isinstance(defect, dict) else {}
    threshold_defect = defect == "full_record_thresholds" or options.get("thresholds") == "full_record_thresholds"
    weight_defect = defect == "member_weighted" or options.get("weighting") == "member_weighted"
    means = np.stack([np.asarray(hindcasts[m], dtype="float64").mean(axis=1) for m in models])
    new_means = np.stack([np.asarray(forecasts[m], dtype="float64").mean(axis=1) for m in models])
    y = np.asarray(observed, dtype="float64")
    n, nf = len(years), len(new_years)
    if means.shape[1:] != y.shape or new_means.shape[1] != nf or y.shape[0] != n:
        raise ValueError("Seasonal arrays do not match declared years")
    hp = np.empty((len(models), n, 3, *y.shape[1:]))
    fp = np.empty((len(models), nf, 3, *y.shape[1:]))
    observed_categories = np.empty_like(y, dtype="int16")
    global_thresholds = np.quantile(y, [1 / 3, 2 / 3], axis=0)
    for t in range(n):
        keep = np.arange(n) != t
        thresholds = global_thresholds if threshold_defect else np.quantile(y[keep], [1 / 3, 2 / 3], axis=0)
        observed_categories[t] = category(y[t], thresholds)
        for i in range(len(models)):
            hp[i, t], _ = gaussian_terciles(means[i, keep], y[keep], means[i, t], thresholds)
    for i in range(len(models)):
        for t in range(nf):
            fp[i, t], _ = gaussian_terciles(means[i], y, new_means[i, t])
    weights = np.array([np.asarray(hindcasts[m]).shape[1] for m in models], dtype=float) if weight_defect else np.ones(len(models))
    combined_h = np.average(hp, axis=0, weights=weights)
    combined_f = np.average(fp, axis=0, weights=weights)
    score = float(rps(combined_h, observed_categories).mean())
    baseline = float(rps(np.full_like(combined_h, 1 / 3), observed_categories).mean())
    coords = {"model": np.arange(len(models)), "year": np.asarray(years), "new_year": np.asarray(new_years), "tercile": list(TERCILES), "lat": latitude, "lon": longitude}
    ds = xr.Dataset({
        "train_model_mean_mm": (("model", "year", "lat", "lon"), means),
        "train_observed_mm": (("year", "lat", "lon"), y),
        "new_model_mean_mm": (("model", "new_year", "lat", "lon"), new_means),
        "model_hindcast_probability": (("model", "year", "tercile", "lat", "lon"), hp),
        "model_forecast_probability": (("model", "new_year", "tercile", "lat", "lon"), fp),
        "hindcast_probability": (("year", "tercile", "lat", "lon"), combined_h),
        "forecast_probability": (("new_year", "tercile", "lat", "lon"), combined_f),
        "observed_category": (("year", "lat", "lon"), observed_categories),
        "cv_rps": score, "cv_rps_climatology": baseline, "cv_rpss": 1 - score / baseline,
    }, coords=coords)
    for name in ("train_model_mean_mm", "train_observed_mm", "new_model_mean_mm"):
        ds[name].attrs["units"] = "mm"
    ds["model"].attrs["model_names"] = ",".join(models)
    return ds


def parity_check(hindcasts, observed, forecasts, years, new_years, latitude, longitude):
    """Optional supported-public-API diagnostic; never called by grading."""
    from africas2s import calibrate
    coords = {"year": years, "lat": latitude, "lon": longitude}
    obs = xr.DataArray(observed, dims=("year", "lat", "lon"), coords=coords)
    pairs = {}
    for m in hindcasts:
        h = xr.DataArray(hindcasts[m], dims=("year", "member", "lat", "lon"), coords={**coords, "member": np.arange(hindcasts[m].shape[1])})
        f = xr.DataArray(forecasts[m], dims=("year", "member", "lat", "lon"), coords={**coords, "year": new_years, "member": np.arange(forecasts[m].shape[1])})
        pairs[m] = (h, f)
    cv = calibrate(pairs, obs, method="ereg", cv="loyo", return_components=True)
    new = [calibrate(pairs, obs, method="ereg", forecast_year=int(year), return_components=True) for year in new_years]
    return cv, new
