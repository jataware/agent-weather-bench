"""Independent implementation of the reference-matched stages: prepare, WVG and eReg.

Separate code path from science.py: netCDF4 reads, explicit loops, Fisher scoring for the
logistic fit, closed-form regression moments, hand-written quantiles. Same conventions.
"""
from calendar import monthrange
from pathlib import Path

import netCDF4
import numpy as np
import xarray as xr
from scipy.special import ndtr

MODELS = ("ccsm4", "geoss2s", "cansipsic4", "cfsv2")
SEASONS = {2: (3, 4, 5), 8: (10, 11, 12)}
TARGET_LAT = np.round(-12.75 + 0.5 * np.arange(58), 3)
TARGET_LON = np.round(21.25 + 0.5 * np.arange(62), 3)
BOXES = {"nino34": (-5, 5, 190, 240), "wnp": (20, 35, 160, 210), "wep": (-15, 20, 120, 160)}
DEFAULT = {"obs_regridding": "conservative", "month_lengths": "actual", "ereg_variance": "prediction_error",
           "thresholds": "fold_only"}


def _dates(variable):
    return netCDF4.num2date(variable[:], variable.units, getattr(variable, "calendar", "standard"), only_use_cftime_datetimes=False)


def _days(init, year, reading):
    if reading == "thirty_days":
        return 30.0 * len(SEASONS[init])
    if reading == "no_day_factor":
        return 1.0
    return float(sum(monthrange(year, m)[1] for m in SEASONS[init]))


def model_totals(paths, init, years, reading):
    """(year, lat, lon) ensemble-mean seasonal totals, stitched over files, read with netCDF4."""
    rows, lat, lon = {}, None, None
    for path in paths:
        with netCDF4.Dataset(path) as nc:
            units = nc["precip"].units
            if units not in ("mm/day", "mm"):
                raise ValueError("units")
            dates = _dates(nc["init_time"])
            la, lo = np.asarray(nc["lat"][:], dtype="float64"), np.asarray(nc["lon"][:], dtype="float64")
            values = np.asarray(nc["precip"][:], dtype="float64")
        order_lat, order_lon = np.argsort(la), np.argsort(lo)
        la, lo, values = la[order_lat], lo[order_lon], values[:, :, order_lat][:, :, :, order_lon]
        lat = la if lat is None else lat
        lon = lo if lon is None else lon
        for i, d in enumerate(dates):
            if d.month != init or d.year not in years:
                continue
            total = np.zeros(values.shape[2:])
            for m in range(values.shape[1]):
                total += values[i, m] * (_days(init, d.year, reading) if units == "mm/day" else 1.0)
            rows[d.year] = total / values.shape[1]
    missing = [y for y in years if y not in rows]
    if missing:
        raise ValueError(f"missing issuances {missing}")
    out = np.stack([rows[y] for y in years])
    if not np.isfinite(out).all():
        raise ValueError("model NaN")
    return out, lat, lon


def interpolate_bilinear(values, lat, lon, target_lat, target_lon):
    """Manual bilinear interpolation of (..., lat, lon) onto target centres."""
    out = np.empty((*values.shape[:-2], len(target_lat), len(target_lon)))
    for i, y in enumerate(target_lat):
        j1 = int(np.searchsorted(lat, y)); j0 = j1 - 1
        if j1 >= len(lat): j0, j1 = len(lat) - 2, len(lat) - 1
        if j0 < 0: j0, j1 = 0, 1
        fy = (y - lat[j0]) / (lat[j1] - lat[j0])
        for k, x in enumerate(target_lon):
            k1 = int(np.searchsorted(lon, x)); k0 = k1 - 1
            if k1 >= len(lon): k0, k1 = len(lon) - 2, len(lon) - 1
            if k0 < 0: k0, k1 = 0, 1
            fx = (x - lon[k0]) / (lon[k1] - lon[k0])
            out[..., i, k] = ((1 - fy) * (1 - fx) * values[..., j0, k0] + (1 - fy) * fx * values[..., j0, k1]
                              + fy * (1 - fx) * values[..., j1, k0] + fy * fx * values[..., j1, k1])
    return out


def observed_totals(path, init, years):
    """Seasonal totals on the 0.05-degree grid, read in one pass over the needed months."""
    with netCDF4.Dataset(path) as nc:
        dates = _dates(nc["time"])
        la, lo = np.asarray(nc["latitude"][:], dtype="float64"), np.asarray(nc["longitude"][:], dtype="float64")
        index = {(d.year, d.month): i for i, d in enumerate(dates)}
        wanted = sorted(index[(y, m)] for y in years for m in SEASONS[init])
        raw = nc["precip"][wanted]
        block = np.where(np.ma.getmaskarray(raw), np.nan, np.asarray(raw, dtype="float64"))
    position = {i: k for k, i in enumerate(wanted)}
    pieces = []
    for y in years:
        total = None
        for m in SEASONS[init]:
            field = block[position[index[(y, m)]]]
            total = field if total is None else total + field
        pieces.append(total)
    values = np.stack(pieces)
    order_lat, order_lon = np.argsort(la), np.argsort(lo)
    return values[:, order_lat][:, :, order_lon], la[order_lat], lo[order_lon]


def aggregate_observations(values, lat, lon, reading):
    n = values.shape[0]
    out = np.full((n, len(TARGET_LAT), len(TARGET_LON)), np.nan)
    support = np.zeros((len(TARGET_LAT), len(TARGET_LON)), dtype=bool)
    weights_lat = np.cos(np.deg2rad(lat))
    for i, y in enumerate(TARGET_LAT):
        rows = np.flatnonzero((lat > y - 0.25) & (lat < y + 0.25))
        for k, x in enumerate(TARGET_LON):
            cols = np.flatnonzero((lon > x - 0.25) & (lon < x + 0.25))
            block = values[:, rows][:, :, cols]
            support[i, k] = bool(np.isfinite(block).all())
            if reading == "conservative":
                w = np.repeat(weights_lat[rows][:, None], len(cols), axis=1)
                out[:, i, k] = (block * w).sum(axis=(1, 2)) / w.sum()
            elif reading == "nearest":
                out[:, i, k] = block[:, 4, 4]
    if reading == "bilinear":
        out = interpolate_bilinear(values, lat, lon, TARGET_LAT, TARGET_LON)
    return out, support


def quantile_linear(sorted_values, q):
    n = sorted_values.shape[0]
    position = (n - 1) * q
    low = int(np.floor(position))
    high = min(low + 1, n - 1)
    frac = position - low
    return sorted_values[low] * (1 - frac) + sorted_values[high] * frac


def bounds_of(observed):
    s = np.sort(observed, axis=0)
    return np.stack([quantile_linear(s, 1 / 3), quantile_linear(s, 2 / 3)])


def categorize(values, bounds):
    out = np.ones(values.shape, dtype="int16")
    out[values < bounds[0] - 1e-6] = 0      # the brief's rule: a total within 1e-6 mm of a boundary is near normal
    out[values > bounds[1] + 1e-6] = 2
    return out


def season_mean_sst(path, init, years, time_name, lat_name, lon_name, member=False):
    with netCDF4.Dataset(path) as nc:
        dates = _dates(nc[time_name])
        la, lo = np.asarray(nc[lat_name][:], dtype="float64"), np.asarray(nc[lon_name][:], dtype="float64")
        raw = nc["sst"][:]
        values = np.where(np.ma.getmaskarray(raw), np.nan, np.asarray(raw, dtype="float64"))
    order_lat, order_lon = np.argsort(la), np.argsort(lo)
    la, lo = la[order_lat], lo[order_lon]
    rows = {}
    if member:
        values = values[:, :, order_lat][:, :, :, order_lon]
        for i, d in enumerate(dates):
            if d.month == init and d.year in years:
                rows[d.year] = np.nanmean(values[i], axis=0)
    else:
        values = values[:, order_lat][:, :, order_lon]
        index = {(d.year, d.month): i for i, d in enumerate(dates)}
        for y in years:
            rows[y] = np.mean([values[index[(y, m)]] for m in SEASONS[init]], axis=0)
    return rows, la, lo


def box_series(rows, years, lat, lon, box, reading):
    south, north, west, east = box
    r = np.flatnonzero((lat >= south) & (lat <= north)); c = np.flatnonzero((lon >= west) & (lon <= east))
    w = np.cos(np.deg2rad(lat[r])) if reading == "cos_latitude" else np.ones(len(r))
    series = []
    for y in years:
        block = rows[y][r][:, c]
        ok = np.isfinite(block)
        weights = np.where(ok, w[:, None] * np.ones_like(block), 0.0)
        series.append(float((np.where(ok, block, 0.0) * weights).sum() / weights.sum()))
    return np.array(series)


def index_values(provider, init, years, forecast_year, reading):
    obs, olat, olon = season_mean_sst(provider / "observations/ersst-v5-monthly.nc", init, years, "time", "lat", "lon")
    all_years = sorted(years + [forecast_year])
    model = {}
    mlat = mlon = None
    rows, mlat, mlon = season_mean_sst(provider / "sst/cfsv2" / f"sst_init{init:02d}.nc", init, all_years, "init_time", "lat", "lon", member=True)
    model.update(rows)
    def z(series, reference):
        return (series - reference.mean()) / reference.std(ddof=1)
    zo = {k: z(box_series(obs, years, olat, olon, b, reading), box_series(obs, years, olat, olon, b, reading)) for k, b in BOXES.items()}
    zm = {k: z(box_series(model, [forecast_year], mlat, mlon, b, reading), box_series(model, years, mlat, mlon, b, reading)) for k, b in BOXES.items()}
    return zo["nino34"] - (zo["wnp"] + zo["wep"]) / 2, float((zm["nino34"] - (zm["wnp"] + zm["wep"]) / 2)[0])


def fit_logistic(x, y):
    """Fisher scoring on the uncentred design; returns (intercept, slope) per cell or NaN where separated/constant."""
    n, cells = y.shape
    X = np.column_stack([np.ones(n), x])
    beta = np.zeros((2, cells))
    for _ in range(60):
        eta = X @ beta
        eta = np.minimum(np.maximum(eta, -30), 30)
        p = 1 / (1 + np.exp(-eta))
        w = p * (1 - p)
        a = w.sum(0); b = (w * x[:, None]).sum(0); c = (w * x[:, None] ** 2).sum(0)
        g0 = (y - p).sum(0); g1 = ((y - p) * x[:, None]).sum(0)
        det = np.maximum(a * c - b * b, 1e-300)
        d0 = (c * g0 - b * g1) / det; d1 = (-b * g0 + a * g1) / det
        beta = beta + np.stack([d0, d1])
        if max(np.abs(d0).max(), np.abs(d1).max()) < 1e-12:
            break
    return beta


def below_probability(x, y, x_new):
    beta = fit_logistic(x, y)
    eta = np.minimum(np.maximum(beta[0] + beta[1] * x_new, -30), 30)
    p = 1 / (1 + np.exp(-eta))
    ones, zeros = y == 1, y == 0
    constant = ones.all(0) | zeros.all(0)
    hi1 = np.where(ones, x[:, None], -np.inf).max(0); lo1 = np.where(ones, x[:, None], np.inf).min(0)
    hi0 = np.where(zeros, x[:, None], -np.inf).max(0); lo0 = np.where(zeros, x[:, None], np.inf).min(0)
    sep_low = (~constant) & (hi1 < lo0)       # below-normal years all have lower index
    sep_high = (~constant) & (hi0 < lo1)
    p = np.where(sep_low, (x_new < (hi1 + lo0) / 2) * 1.0, p)
    p = np.where(sep_high, (x_new > (hi0 + lo1) / 2) * 1.0, p)
    p = np.where(constant, y.mean(0), p)
    return np.minimum(np.maximum(p, 0.0), 1.0)


def wvg_triple(below):
    near = np.minimum(1 / 3, 1 - below)
    above = np.minimum(np.maximum(1 - below - near, 0.0), 1.0)
    return np.stack([below, near, above])


def regression_terciles(x, y, x_new, bounds, reading):
    n = x.shape[0]
    xm, ym = x.mean(0), y.mean(0)
    sxx = np.maximum(((x - xm) ** 2).sum(0), 1e-12)
    sxy = ((x - xm) * (y - ym)).sum(0)
    slope = sxy / sxx
    intercept = ym - slope * xm
    resid = y - (intercept + slope * x)
    s2 = np.maximum((resid ** 2).sum(0) / (n - 2), 1e-12)
    mean = intercept + slope * x_new
    var = s2 * (1 + 1 / n + (x_new - xm) ** 2 / sxx) if reading == "prediction_error" else s2
    sd = np.sqrt(np.maximum(var, 1e-12))
    below = ndtr((bounds[0] - mean) / sd)
    above = 1 - ndtr((bounds[1] - mean) / sd)
    return np.stack([below, 1 - below - above, above]), mean


from functools import lru_cache


@lru_cache(maxsize=4)
def _fine_observations(provider, init, years_key):
    return observed_totals(Path(provider) / "observations/chirps-v2p0-monthly-0p05.nc", init, list(years_key))


@lru_cache(maxsize=24)
def _prepared(provider, init, years_key, fy, month_lengths, obs_regridding, index_box_mean):
    provider, years = Path(provider), list(years_key)
    all_years = sorted(years + [fy])
    natives = []
    for model in MODELS:
        values, plat, plon = model_totals([provider / "models" / model / f"precip_init{init:02d}.nc"], init, all_years, month_lengths)
        natives.append(values)
    native = np.stack(natives)
    on_target = interpolate_bilinear(native, plat, plon, TARGET_LAT, TARGET_LON)
    fine, flat, flon = _fine_observations(str(provider), init, years_key)
    observed_grid, support = aggregate_observations(fine, flat, flon, obs_regridding)
    index, index_forecast = index_values(provider, init, years, fy, index_box_mean)
    return native, on_target, plat, plon, observed_grid, support, index, index_forecast


def compute(provider, params, conventions=None, stages=("prepare", "wvg", "ereg")):
    options = {**DEFAULT, **(conventions or {})}
    init, years, fy = int(params["init_month"]), [int(y) for y in params["training_years"]], int(params["forecast_year"])
    all_years = sorted(years + [fy])
    native, on_target, plat, plon, observed_grid, support, index, index_forecast = _prepared(
        str(provider), init, tuple(years), fy, options["month_lengths"], options["obs_regridding"], "unweighted")
    is_train = np.isin(all_years, years)
    n, cells = len(years), np.flatnonzero(support.ravel())
    observed = observed_grid.reshape(n, -1)[:, cells]
    full = bounds_of(observed)
    categories = np.empty((n, len(cells)), dtype="int16")
    fold_bounds = []
    for t in range(n):
        keep = np.arange(n) != t
        b = full if options["thresholds"] == "full_record" else bounds_of(observed[keep])
        fold_bounds.append(b)
        categories[t] = categorize(observed[t], b)

    def spread(values, front=()):
        out = np.zeros((*front, len(TARGET_LAT) * len(TARGET_LON)))
        out[..., cells] = values
        return out.reshape(*front, len(TARGET_LAT), len(TARGET_LON))

    data = {
        "prepare_observed_mm": (("year", "lat", "lon"), spread(observed, (n,))),
        "prepare_support": (("lat", "lon"), support.astype("int16")),
        "prepare_model_hindcast_mean_mm": (("model", "year", "lat", "lon"), on_target[:, is_train]),
        "prepare_model_forecast_mean_mm": (("model", "lat", "lon"), on_target[:, ~is_train][:, 0]),
        "prepare_model_predictor_mm": (("model", "year", "plat", "plon"), native[:, is_train]),
        "prepare_model_predictor_forecast_mm": (("model", "plat", "plon"), native[:, ~is_train][:, 0]),
        "prepare_tercile_lower_mm": (("lat", "lon"), spread(full[0])),
        "prepare_tercile_upper_mm": (("lat", "lon"), spread(full[1])),
        "prepare_observed_category": (("year", "lat", "lon"), spread(categories, (n,)).astype("int16")),
        "prepare_sst_index": (("year",), index),
        "prepare_sst_index_forecast": ((), index_forecast),
    }
    if "wvg" in stages:
        hp = np.empty((n, 3, len(cells)))
        for t in range(n):
            keep = np.arange(n) != t
            labels = (observed[keep] < fold_bounds[t][0] - 1e-6).astype("float64")
            hp[t] = wvg_triple(below_probability(index[keep], labels, index[t]))
        fp = wvg_triple(below_probability(index, (observed < full[0] - 1e-6).astype("float64"), index_forecast))
        data["wvg_hindcast_probability"] = (("year", "category", "lat", "lon"), spread(hp, (n, 3)))
        data["wvg_forecast_probability"] = (("category", "lat", "lon"), spread(fp, (3,)))
    if "ereg" in stages:
        m = len(MODELS)
        train = on_target[:, is_train].reshape(m, n, -1)[:, :, cells]
        new = on_target[:, ~is_train][:, 0].reshape(m, -1)[:, cells]
        mhp = np.empty((m, n, 3, len(cells))); mfp = np.empty((m, 3, len(cells))); fitted = np.zeros((n, len(cells)))
        for i in range(m):
            for t in range(n):
                keep = np.arange(n) != t
                mhp[i, t], mean = regression_terciles(train[i, keep], observed[keep], train[i, t], fold_bounds[t], options["ereg_variance"])
                fitted[t] += mean / m
            mfp[i], _ = regression_terciles(train[i], observed, new[i], full, options["ereg_variance"])
        data["ereg_model_hindcast_probability"] = (("model", "year", "category", "lat", "lon"), spread(mhp, (m, n, 3)))
        data["ereg_model_forecast_probability"] = (("model", "category", "lat", "lon"), spread(mfp, (m, 3)))
        data["ereg_hindcast_probability"] = (("year", "category", "lat", "lon"), spread(mhp.mean(0), (n, 3)))
        data["ereg_forecast_probability"] = (("category", "lat", "lon"), spread(mfp.mean(0), (3,)))
        data["ereg_fitted_mean_mm"] = (("year", "lat", "lon"), spread(fitted, (n,)))
    coords = {"year": np.asarray(years), "model": np.arange(len(MODELS)), "category": np.arange(3), "stream": np.arange(3),
              "lat": TARGET_LAT, "lon": TARGET_LON, "plat": plat, "plon": plon}
    return xr.Dataset(data, coords=coords)
