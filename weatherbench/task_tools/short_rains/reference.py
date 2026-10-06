"""Independent explicit numerical reference; never mount in an agent workspace.

No forecast library or original v4zeek solver is imported. The second reference
in audit.py uses different feature, regression, quantile and score code.
"""
from __future__ import annotations

import itertools
import numpy as np
import xarray as xr
from scipy.stats import t

FEATURES = ("nino34", "iod", "wpac", "wv", "wpg", "wvg")
CANDIDATES = tuple(itertools.product(FEATURES, (0, 1, 2), (1, 2, 3), ("identity", "log1p")))
SYSTEMS = ("climatology", "antecedent-iod", "forecast-iod", "nested-search")


def cpt_quantile(y, p):
    a = np.sort(np.asarray(y, dtype=float))
    r = len(a) * p + .5
    j = int(np.floor(r))
    if j <= 0:
        return float(a[0])
    if j >= len(a):
        return float(a[-1])
    return float(a[j - 1] + (r - j) * (a[j] - a[j - 1]))


def components(sst, years, gap, width):
    cache = sst.attrs.setdefault("_component_cache", {})
    rows = []
    for year in years:
        key = (int(year), gap, width)
        if key not in cache:
            values = []
            for month in range(8 - gap - width + 1, 9 - gap):
                values.append(sst.sel(time=f"{int(year)}-{month:02d}-01").values)
            cache[key] = np.mean(values, axis=0)
        rows.append(cache[key])
    return np.asarray(rows)


def feature(sst, gcm, years, training, spec):
    name, gap, width, _ = spec
    if name == "forecast-iod":
        return gcm.sel(year=years).values.astype(float)
    raw = components(sst, years, gap, width)
    boxes = list(sst.box.values)
    a = {b: raw[:, boxes.index(b)] for b in boxes}
    if name in a:
        return a[name]
    if name == "iod":
        return a["iod_w"] - a["iod_e"]
    mask = np.isin(years, training)
    z = {b: (v - np.mean(v[mask])) / np.std(v[mask], ddof=1) for b, v in a.items()}
    if name == "wpg":
        return z["wpac"] - z["nino34"]
    if name == "wvg":
        return z["nino34"] - z["wv"]
    raise ValueError(name)


def fit_probability(x, y, new, transform, boundaries):
    target = np.log1p(y) if transform == "log1p" else y
    limits = np.log1p(boundaries) if transform == "log1p" else boundaries
    xm = float(np.mean(x))
    ym = float(np.mean(target))
    dx = x - xm
    sxx = float(dx @ dx)
    beta = float(dx @ (target - ym) / sxx)
    resid = target - ym - beta * dx
    variance = float(resid @ resid / (len(x) - 2))
    mu = ym + beta * (new - xm)
    scale = np.sqrt(variance * (1 + 1 / len(x) + (new - xm) ** 2 / sxx))
    cdf = t.cdf((limits[None, :] - mu[:, None]) / scale[:, None], df=len(x) - 2)
    return np.column_stack((cdf[:, 0], cdf[:, 1] - cdf[:, 0], 1 - cdf[:, 1]))


def rps(p, y, boundaries):
    cat = np.searchsorted(boundaries, y, side="right")
    o = np.eye(3)[cat]
    return np.mean((np.cumsum(p, axis=-1)[:, :2] - np.cumsum(o, axis=-1)[:, :2]) ** 2, axis=-1)


def forecast(sst, gcm, y, train, test, spec):
    years = np.r_[train, test]
    xx = feature(sst, gcm, years, train, spec)
    yy = y.sel(year=train).values
    bounds = np.array([cpt_quantile(yy, p) for p in (1 / 3, 2 / 3)])
    pred = fit_probability(xx[:len(train)], yy, xx[len(train):], spec[3], bounds)
    return pred, bounds


def select(sst, gcm, y, train):
    losses = []
    for spec in CANDIDATES:
        err = []
        for held in train[8:]:
            inner = train[train < held]
            pp, bb = forecast(sst, gcm, y, inner, [held], spec)
            err.append(rps(pp, y.sel(year=[held]).values, bb)[0])
        losses.append(np.mean(err))
    losses = np.asarray(losses)
    best = int(np.flatnonzero(losses <= np.min(losses) + 1e-12)[0])
    return best, losses


def build(inputs):
    monthly = xr.open_dataset(inputs / "rainfall.nc").monthly_rainfall_scaled.load()
    # The frozen old acquisition converter divided monthly totals by 30.
    # Undo that operation; these numbers are not calendar-aware daily rates.
    y = (monthly * 30).sel(time=monthly.time.dt.month.isin([10, 11, 12])).groupby("time.year").sum("time")
    sst = xr.open_dataset(inputs / "sst.nc").sst.load()
    gcm = xr.open_dataset(inputs / "forecast-index.nc").gcm_iod.load()
    years = np.arange(2005, 2020)
    regions = list(monthly.region.values)
    p = np.zeros((len(SYSTEMS), len(years), len(regions), 3))
    bounds = np.zeros((len(years), len(regions), 2))
    losses = np.zeros((len(years), len(regions), len(CANDIDATES)))
    winners = np.zeros((len(years), len(regions)), dtype=int)
    prod = np.zeros((len(SYSTEMS), 4, len(regions), 3))
    prod_bounds = np.zeros((len(regions), 2))
    prod_losses = np.zeros((len(regions), len(CANDIDATES)))
    prod_winners = np.zeros(len(regions), dtype=int)
    for ri, region in enumerate(regions):
        target = y.sel(region=region)
        for yi, year in enumerate(years):
            train = np.arange(1993, year)
            winner, scores = select(sst, gcm, target, train)
            winners[yi, ri], losses[yi, ri] = winner, scores
            specs = [("iod", 0, 2, "identity"), ("forecast-iod", 0, 0, "identity"), CANDIDATES[winner]]
            p[0, yi, ri] = 1 / 3
            for si, spec in enumerate(specs, 1):
                pred, bb = forecast(sst, gcm, target, train, [year], spec)
                p[si, yi, ri], bounds[yi, ri] = pred[0], bb
        train = np.arange(1993, 2020)
        winner, scores = select(sst, gcm, target, train)
        prod_winners[ri], prod_losses[ri] = winner, scores
        specs = [("iod", 0, 2, "identity"), ("forecast-iod", 0, 0, "identity"), CANDIDATES[winner]]
        prod[0, :, ri] = 1 / 3
        for si, spec in enumerate(specs, 1):
            pp, bb = forecast(sst, gcm, target, train, np.arange(2020, 2024), spec)
            prod[si, :, ri], prod_bounds[ri] = pp, bb
    cv = xr.Dataset({
        "probability": (("system", "year", "region", "tercile"), p),
        "threshold": (("year", "region", "boundary"), bounds),
        "selected_candidate": (("year", "region"), winners),
        "inner_rps": (("year", "region", "candidate"), losses),
    }, coords={"system": list(SYSTEMS), "year": years, "region": regions, "tercile": ["below", "normal", "above"], "boundary": ["lower", "upper"], "candidate": np.arange(len(CANDIDATES))})
    production = xr.Dataset({
        "probability": (("system", "year", "region", "tercile"), prod),
        "threshold": (("region", "boundary"), prod_bounds),
        "selected_candidate": (("region",), prod_winners),
        "inner_rps": (("region", "candidate"), prod_losses),
    }, coords={"system": list(SYSTEMS), "year": np.arange(2020, 2024), "region": regions, "tercile": ["below", "normal", "above"], "boundary": ["lower", "upper"], "candidate": np.arange(len(CANDIDATES))})
    scored = np.zeros((len(SYSTEMS), len(years), len(regions)))
    for yi, year in enumerate(years):
        for ri, region in enumerate(regions):
            for si in range(len(SYSTEMS)):
                scored[si, yi, ri] = rps(p[si, yi, ri][None, :], [y.sel(year=year, region=region).item()], bounds[yi, ri])[0]
    skill = 1 - scored.sum(axis=1) / scored[0].sum(axis=0)[None, :]
    cv["rps"] = (("system", "year", "region"), scored)
    cv["rpss"] = (("system", "region"), skill)
    y.attrs["units"] = "mm"
    cv.threshold.attrs["units"] = production.threshold.attrs["units"] = "mm"
    return y.to_dataset(name="seasonal_total"), cv, production
