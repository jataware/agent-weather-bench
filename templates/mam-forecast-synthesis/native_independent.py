"""Independent scalar reference: no science.py or africaS2S imports.

Order-statistic interpolation, scalar least squares, math.erf Gaussian CDF,
and explicit cumulative score loops deliberately differ from implementation A.
"""
from calendar import monthrange
from math import erf, fsum, sqrt
import numpy as np
import xarray as xr


def quantile(values, probability):
    ordered = sorted(float(v) for v in values)
    position = (len(ordered) - 1) * probability
    left = int(position)
    right = min(left + 1, len(ordered) - 1)
    return ordered[left] + (position - left) * (ordered[right] - ordered[left])


def predict(x, y, new_x, thresholds=None):
    n = len(x)
    if n < 3:
        raise ValueError("At least three paired years required")
    xb, yb = fsum(x) / n, fsum(y) / n
    ssx = fsum((float(a) - xb) ** 2 for a in x)
    if ssx < 1e-12:
        raise ValueError("Constant predictor")
    b = fsum((float(a) - xb) * (float(o) - yb) for a, o in zip(x, y)) / ssx
    a = yb - b * xb
    residual = fsum((float(o) - a - b * float(v)) ** 2 for v, o in zip(x, y)) / (n - 2)
    sd = sqrt(max(1e-12, residual * (1 + 1 / n + (new_x - xb) ** 2 / ssx)))
    edges = thresholds if thresholds is not None else (quantile(y, 1 / 3), quantile(y, 2 / 3))
    cdf = [0.5 * (1 + erf((e - a - b * new_x) / sd / sqrt(2))) for e in edges]
    return (cdf[0], cdf[1] - cdf[0], 1 - cdf[1])


def interpolate(values, source_lat, source_lon, target_lat, target_lon):
    """Separable bilinear interpolation with NumPy, no xarray/SciPy interp."""
    ilat, ilon = np.argsort(source_lat), np.argsort(source_lon)
    source_lat, source_lon = np.asarray(source_lat)[ilat], np.asarray(source_lon)[ilon]
    values = np.asarray(values)[..., ilat, :][..., ilon]
    target_lat, target_lon = np.asarray(target_lat), np.asarray(target_lon)
    if min(target_lat) < source_lat[0] or max(target_lat) > source_lat[-1] or min(target_lon) < source_lon[0] or max(target_lon) > source_lon[-1]:
        raise ValueError("No extrapolation")
    result = np.empty((*values.shape[:-2], len(target_lat), len(target_lon)))
    for index in np.ndindex(values.shape[:-2]):
        along_lon = np.array([np.interp(target_lon, source_lon, row) for row in values[index]])
        result[index] = np.array([np.interp(target_lat, source_lat, along_lon[:, j]) for j in range(len(target_lon))]).T
    return result


def seasonal_model(ds, years, latitude, longitude, defect=None):
    var = next(n for n in ("tprate", "tp", "precip", "precipitation") if n in ds.data_vars)
    time = next(n for n in ("forecast_reference_time", "indexing_time") if n in ds[var].dims)
    data = ds[var].transpose(time, "forecastMonth", "number", "latitude", "longitude")
    times = ds[time].values.astype("datetime64[M]").astype(int)
    seasons = []
    for year in years:
        positions = np.flatnonzero(times // 12 + 1970 == year)
        if len(positions) != 1:
            raise ValueError("One initialization per year required")
        i = int(positions[0])
        total = np.zeros(data.shape[2:])
        for month in (3, 4, 5):
            requested = (int(year) - 1970) * 12 + month - 1
            positions = np.flatnonzero(times[i] + np.asarray(ds.forecastMonth) - 1 == requested)
            if len(positions) != 1:
                raise ValueError("Missing MAM month")
            days = 30 if defect == "thirty_days" else monthrange(int(year), month)[1]
            seconds = 1 if defect == "missing_seconds" else 86400
            millimetres = 1 if defect == "missing_millimetres" else 1000
            total += np.asarray(data[i, int(positions[0])], dtype=float) * days * seconds * millimetres
        seasons.append(interpolate(total, ds.latitude.values, ds.longitude.values, latitude, longitude))
    return np.stack(seasons)


def seasonal_observed(ds, years, latitude, longitude):
    var = next(n for n in ("precip", "precipitation", "tp", "prcp") if n in ds.data_vars)
    time = next(n for n in ("time", "T") if n in ds[var].dims)
    lat = next(n for n in ("lat", "latitude", "Y") if n in ds[var].dims)
    lon = next(n for n in ("lon", "longitude", "X") if n in ds[var].dims)
    data = ds[var].transpose(time, lat, lon)
    months = ds[time].values.astype("datetime64[M]").astype(int)
    seasons = []
    for year in years:
        total = np.zeros(data.shape[1:])
        for month in (3, 4, 5):
            positions = np.flatnonzero(months == (int(year) - 1970) * 12 + month - 1)
            if len(positions) != 1:
                raise ValueError("Missing observed MAM month")
            total += np.asarray(data[int(positions[0])], dtype=float)
        seasons.append(interpolate(total, ds[lat].values, ds[lon].values, latitude, longitude))
    return np.stack(seasons)


def evaluate(hindcasts, observed, forecasts, years, new_years, latitude, longitude, defect=None):
    models = list(hindcasts)
    options = defect if isinstance(defect, dict) else {}
    global_edges = defect == "full_record_thresholds" or options.get("thresholds") == "full_record_thresholds"
    pooled_weights = defect == "member_weighted" or options.get("weighting") == "member_weighted"
    y = np.asarray(observed, dtype=float)
    means = np.stack([np.asarray(hindcasts[m], dtype=float).mean(axis=1) for m in models])
    new_means = np.stack([np.asarray(forecasts[m], dtype=float).mean(axis=1) for m in models])
    n, nf = len(years), len(new_years)
    hp = np.empty((len(models), n, 3, *y.shape[1:]))
    fp = np.empty((len(models), nf, 3, *y.shape[1:]))
    categories = np.empty_like(y, dtype="int16")
    for cell in np.ndindex(y.shape[1:]):
        target = y[(slice(None), *cell)]
        for t in range(n):
            train = [i for i in range(n) if i != t]
            yt = [float(target[i]) for i in train]
            edges = [quantile(target if global_edges else yt, q) for q in (1 / 3, 2 / 3)]
            categories[(t, *cell)] = 0 if target[t] < edges[0] else 2 if target[t] > edges[1] else 1
            for model in range(len(models)):
                x = means[(model, slice(None), *cell)]
                hp[(model, t, slice(None), *cell)] = predict([float(x[i]) for i in train], yt, float(x[t]), edges)
        for model in range(len(models)):
            x = means[(model, slice(None), *cell)]
            for t in range(nf):
                fp[(model, t, slice(None), *cell)] = predict(x, target, float(new_means[(model, t, *cell)]))
    weights = [hindcasts[m].shape[1] if pooled_weights else 1 for m in models]
    combined_h = sum(hp[i] * weights[i] for i in range(len(models))) / sum(weights)
    combined_f = sum(fp[i] * weights[i] for i in range(len(models))) / sum(weights)
    scores, baselines = [], []
    for index in np.ndindex(categories.shape):
        t, *cell = index
        label = categories[index]
        cumulative = 0.0
        score, baseline = 0.0, 0.0
        for c in range(3):
            cumulative += combined_h[(t, c, *cell)]
            truth = float(c >= label)
            score += (cumulative - truth) ** 2
            baseline += ((c + 1) / 3 - truth) ** 2
        scores.append(score)
        baselines.append(baseline)
    score, baseline = fsum(scores) / len(scores), fsum(baselines) / len(baselines)
    return xr.Dataset({
        "train_model_mean_mm": (("model", "year", "lat", "lon"), means),
        "train_observed_mm": (("year", "lat", "lon"), y),
        "new_model_mean_mm": (("model", "new_year", "lat", "lon"), new_means),
        "model_hindcast_probability": (("model", "year", "tercile", "lat", "lon"), hp),
        "model_forecast_probability": (("model", "new_year", "tercile", "lat", "lon"), fp),
        "hindcast_probability": (("year", "tercile", "lat", "lon"), combined_h),
        "forecast_probability": (("new_year", "tercile", "lat", "lon"), combined_f),
        "observed_category": (("year", "lat", "lon"), categories),
        "cv_rps": score, "cv_rps_climatology": baseline, "cv_rpss": 1 - score / baseline,
    }, coords={"model": np.arange(len(models)), "year": years, "new_year": new_years, "tercile": [0, 1, 2], "lat": latitude, "lon": longitude})
