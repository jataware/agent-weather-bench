"""Deciding implementation of the objective seasonal outlook: prepare, WVG, eReg, CCA, combine, verify, issue.

NumPy, SciPy and xarray only. No forecasting library, no CPT, no R. Every
function takes arrays and returns arrays; `compute` wires the stages together
from the frozen provider files. Conventions name the readings the controller
accepts or rejects; a reading changes the numbers, never the interface.
"""
from calendar import monthrange
from functools import lru_cache
from pathlib import Path

import numpy as np
import xarray as xr
from scipy.special import ndtr, stdtr

MODELS = ("ccsm4", "geoss2s", "cansipsic4", "cfsv2")
STREAMS = ("cca", "ereg", "wvg")
CATEGORIES = (0, 1, 2)                      # below, near, above normal; equality belongs to near
SEASONS = {2: (3, 4, 5), 8: (10, 11, 12)}   # initialization month -> valid target months
TARGET_LAT = np.round(-12.75 + 0.5 * np.arange(58), 3)
TARGET_LON = np.round(21.25 + 0.5 * np.arange(62), 3)
# Western-V Gradient boxes (south, north, west, east), degrees east in 0..360.
BOXES = {"nino34": (-5, 5, 190, 240), "wnp": (20, 35, 160, 210), "wep": (-15, 20, 120, 160)}
CCA_CANDIDATES = tuple((x, y, c) for x in range(1, 9) for y in range(1, 7) for c in range(1, min(x, y, 3) + 1))
EPS = 1e-12
TIE_MM = 1e-6          # a total within this distance of a tercile boundary is near normal (ties at the boundary are common in CHIRPS desert cells)
DEFAULT = {"obs_regridding": "conservative", "month_lengths": "actual", "ereg_variance": "prediction_error",
           "thresholds": "fold_only"}


# ---- raw provider files (acmadDL deliveries) --------------------------------------------

def season_days(init_month, year, reading="actual"):
    """Days in the target season of `year` for the calendar reading; the pitfalls are 90 and 1."""
    if reading == "thirty_days":
        return 30.0 * len(SEASONS[init_month])
    if reading == "no_day_factor":
        return 1.0
    return float(sum(monthrange(int(year), m)[1] for m in SEASONS[init_month]))


def read_model_precipitation(files, init_month, years, conventions):
    """Ensemble-mean seasonal totals in mm per issuance year, (year, lat, lon), from one or more acmadDL files.

    Each file holds precip(init_time, member, lat, lon) in the units it declares: a
    target-season mean rate in mm/day, or a season total in mm already accumulated by the
    delivery. Several files are stitched along the issuance year with the member mean
    taken per file, so member counts may differ between files.
    """
    pieces, members = [], {}
    for path in files:
        with xr.open_dataset(path) as ds:
            rate = ds["precip"].load()
        units = rate.attrs.get("units", "").replace(" ", "")
        if units not in ("mm/day", "mm"):
            raise ValueError(f"Unexpected precipitation units {units!r} in {path}")
        issued = rate["init_time"].dt.year.values
        if not np.all(rate["init_time"].dt.month.values == init_month):
            raise ValueError(f"{path} holds issuances of another month")
        keep = np.flatnonzero(np.isin(issued, years))
        if not len(keep):
            continue
        rate = rate.isel(init_time=keep)
        days = xr.DataArray([season_days(init_month, y, conventions["month_lengths"]) if units == "mm/day" else 1.0 for y in issued[keep]], dims=["init_time"])
        total = (rate.astype("float64") * days).mean("member")
        members[Path(path).name] = int(rate.sizes["member"])
        pieces.append(total.assign_coords(init_time=issued[keep]).rename({"init_time": "year"}))
    if not pieces:
        raise ValueError("No issuances for the requested years")
    out = xr.concat(pieces, "year").sortby("year")
    out = out.assign_coords(lat=out["lat"].values.astype("float64"), lon=out["lon"].values.astype("float64")).sortby("lat").sortby("lon")
    if not np.array_equal(out["year"].values, np.asarray(years)):
        raise ValueError(f"Issuance years {out['year'].values.tolist()} do not cover {years} exactly")
    if not np.isfinite(out.values).all():
        raise ValueError("Model precipitation has missing values on the served domain")
    return out.transpose("year", "lat", "lon"), members


def observed_seasonal(ds, init_month, years):
    """CHIRPS seasonal totals in mm on the 0.05-degree grid, (year, lat, lon) ascending, NaN where missing."""
    rain = ds["precip"]
    if rain.attrs.get("units", "").replace(" ", "") != "mm/month":
        raise ValueError("Expected CHIRPS mm/month")
    rain = rain.rename({"latitude": "lat", "longitude": "lon"})
    t_year, t_month = rain["time"].dt.year.values, rain["time"].dt.month.values
    pieces = []
    for year in years:
        hit = np.flatnonzero((t_year == year) & np.isin(t_month, SEASONS[init_month]))
        if len(hit) != len(SEASONS[init_month]):
            raise ValueError(f"CHIRPS lacks the target months of {year}")
        pieces.append(rain.isel(time=hit).astype("float64").sum("time", skipna=False).expand_dims(year=[int(year)]))
    return xr.concat(pieces, "year").sortby("lat").sortby("lon").transpose("year", "lat", "lon")


def read_observed_precipitation(path, init_month, years):
    with xr.open_dataset(path) as ds:
        rain = ds[["precip"]].load()
    return observed_seasonal(rain, init_month, years)


def read_observed_sst(path, init_month, years):
    """ERSST target-season mean per year, (year, lat, lon), longitudes 0..360."""
    with xr.open_dataset(path) as ds:
        sst = ds["sst"].load()
    t_year, t_month = sst["time"].dt.year.values, sst["time"].dt.month.values
    pieces = []
    for year in years:
        hit = np.flatnonzero((t_year == year) & np.isin(t_month, SEASONS[init_month]))
        if len(hit) != len(SEASONS[init_month]):
            raise ValueError(f"ERSST lacks the target months of {year}")
        pieces.append(sst.isel(time=hit).astype("float64").mean("time", skipna=False).expand_dims(year=[int(year)]))
    return xr.concat(pieces, "year").sortby("lat").sortby("lon").transpose("year", "lat", "lon")


def read_model_sst(files, init_month, years):
    """CFSv2 ensemble-mean target-season forecast SST per issuance year, (year, lat, lon), from acmadDL files."""
    pieces = []
    for path in files:
        with xr.open_dataset(path) as ds:
            sst = ds["sst"].load()
        issued = sst["init_time"].dt.year.values
        keep = np.flatnonzero(np.isin(issued, years))
        if not len(keep):
            continue
        seasonal = sst.isel(init_time=keep).astype("float64").mean("member", skipna=True)
        pieces.append(seasonal.assign_coords(init_time=issued[keep]).rename({"init_time": "year"}))
    out = xr.concat(pieces, "year").sortby("year")
    out = out.assign_coords(lat=out["lat"].values.astype("float64"), lon=out["lon"].values.astype("float64")).sortby("lat").sortby("lon")
    if not np.array_equal(out["year"].values, np.asarray(years)):
        raise ValueError("Model SST issuance years do not cover the requested years exactly")
    return out.transpose("year", "lat", "lon")


# ---- prepare ---------------------------------------------------------------------------

def regrid_observations(field, reading):
    """CHIRPS 0.05-degree seasonal totals (year, lat, lon) onto the 0.5-degree target grid.

    conservative: cosine-latitude-weighted mean of the hundred source cells inside each target
    cell. bilinear: linear interpolation at the target centre. nearest (a pitfall): the one
    source cell just south-west of the centre, which samples one percent of the cell.
    Returns (values on the target grid, support mask: every source cell inside the target
    cell finite in every year).
    """
    lat, lon = field["lat"].values, field["lon"].values
    rows = [np.flatnonzero(np.abs(lat - centre) < 0.25) for centre in TARGET_LAT]
    cols = [np.flatnonzero(np.abs(lon - centre) < 0.25) for centre in TARGET_LON]
    if any(len(r) != 10 for r in rows) or any(len(c) != 10 for c in cols):
        raise ValueError("The 0.05-degree grid does not tile the target grid")
    values = field.values
    blocks = values[:, np.concatenate(rows)][:, :, np.concatenate(cols)].reshape(values.shape[0], len(TARGET_LAT), 10, len(TARGET_LON), 10)
    support = np.isfinite(blocks).all(axis=(0, 2, 4))
    if reading == "conservative":
        weights = np.cos(np.deg2rad(lat[np.concatenate(rows)])).reshape(len(TARGET_LAT), 10)[None, :, :, None, None]
        out = (blocks * weights).sum(axis=(2, 4)) / (weights * np.ones_like(blocks)).sum(axis=(2, 4))
    elif reading == "bilinear":
        out = field.interp(lat=TARGET_LAT, lon=TARGET_LON, method="linear").values
    elif reading == "nearest":
        out = blocks[:, :, 4, :, 4]
    else:
        raise ValueError(reading)
    result = xr.DataArray(out, dims=("year", "lat", "lon"), coords={"year": field["year"].values, "lat": TARGET_LAT, "lon": TARGET_LON})
    return result, support


def regrid_models(field):
    """Model 1-degree seasonal totals (year, lat, lon) bilinearly onto the target grid."""
    return field.interp(lat=TARGET_LAT, lon=TARGET_LON, method="linear")


def box_mean(field, box, reading):
    south, north, west, east = box
    sub = field.sel(lat=slice(south, north), lon=slice(west, east))
    if sub.sizes["lat"] == 0 or sub.sizes["lon"] == 0:
        raise ValueError("Empty SST box")
    # Ocean-only means: land and missing cells inside a box do not count.
    finite = np.isfinite(sub)
    if reading == "cos_latitude":
        weights = xr.DataArray(np.cos(np.deg2rad(sub["lat"].values)), dims=["lat"]) * xr.ones_like(sub)
        return (sub.fillna(0) * weights).sum(("lat", "lon")) / weights.where(finite, 0).sum(("lat", "lon"))
    return sub.mean(("lat", "lon"), skipna=True)


def wvg_index(observed_sst, model_sst_training, model_sst_forecast, reading):
    """Training index from observed SST; forecast index from the model's own hindcast climatology.

    z = (box mean - training mean) / training standard deviation (ddof 1), per box;
    index = z(Nino3.4) - (z(WNP) + z(WEP)) / 2.
    """
    def standardised(series, reference):
        return (series - reference.mean("year")) / reference.std("year", ddof=1)
    obs = {name: box_mean(observed_sst, box, reading) for name, box in BOXES.items()}
    train = {name: box_mean(model_sst_training, box, reading) for name, box in BOXES.items()}
    new = {name: box_mean(model_sst_forecast, box, reading) for name, box in BOXES.items()}
    z_obs = {name: standardised(obs[name], obs[name]) for name in BOXES}
    z_new = {name: standardised(new[name], train[name]) for name in BOXES}
    index = z_obs["nino34"] - (z_obs["wnp"] + z_obs["wep"]) / 2
    forecast = z_new["nino34"] - (z_new["wnp"] + z_new["wep"]) / 2
    return index.values.astype("float64"), float(np.asarray(forecast.values).reshape(-1)[0])


def thresholds(values):
    """Lower and upper tercile boundaries per cell: linear-interpolation quantiles at 1/3 and 2/3 along axis 0."""
    return np.quantile(np.asarray(values, dtype="float64"), [1 / 3, 2 / 3], axis=0, method="linear")


def category(values, bounds):
    return np.where(values < bounds[0] - TIE_MM, 0, np.where(values > bounds[1] + TIE_MM, 2, 1)).astype("int16")


# ---- streams ---------------------------------------------------------------------------

def logistic_below(x_train, labels, x_new, iterations=50):
    """P(below normal | index) per cell by unpenalised maximum likelihood (vectorised Newton steps).

    x_train (n,), labels (n, cells) in {0,1}, x_new scalar. Cells whose labels are
    perfectly separated by the index take the limiting step function: 1 on the side
    of the below-normal years, 0 on the other, with the step at the midpoint of the
    nearest years of each class.
    """
    x = np.asarray(x_train, dtype="float64")
    y = np.asarray(labels, dtype="float64")
    n, cells = y.shape
    xc = x - x.mean()
    design = np.stack([np.ones(n), xc], axis=1)                          # (n, 2)
    beta = np.zeros((2, cells))
    beta[0] = np.log(np.clip(y.mean(axis=0), 1e-3, 1 - 1e-3) / (1 - np.clip(y.mean(axis=0), 1e-3, 1 - 1e-3)))
    for _ in range(iterations):
        eta = np.clip(design @ beta, -30, 30)
        p = 1 / (1 + np.exp(-eta))
        w = p * (1 - p)
        gradient = design.T @ (y - p)                                     # (2, cells)
        h00, h01, h11 = (w.sum(axis=0), (w * xc[:, None]).sum(axis=0), (w * xc[:, None] ** 2).sum(axis=0))
        det = h00 * h11 - h01 ** 2
        det = np.where(det > 1e-300, det, 1e-300)
        step0 = (h11 * gradient[0] - h01 * gradient[1]) / det
        step1 = (-h01 * gradient[0] + h00 * gradient[1]) / det
        beta = beta + np.stack([step0, step1])
        if np.max(np.abs(np.stack([step0, step1]))) < 1e-12:
            break
    eta_new = beta[0] + beta[1] * (x_new - x.mean())
    probability = 1 / (1 + np.exp(-np.clip(eta_new, -30, 30)))
    # Separated or degenerate cells: the limiting rule.
    constant = (y.min(axis=0) == y.max(axis=0))
    below_max = np.where(y == 1, x[:, None], -np.inf).max(axis=0)
    below_min = np.where(y == 1, x[:, None], np.inf).min(axis=0)
    other_max = np.where(y == 0, x[:, None], -np.inf).max(axis=0)
    other_min = np.where(y == 0, x[:, None], np.inf).min(axis=0)
    separated = (~constant) & ((below_max < other_min) | (other_max < below_min))
    midpoint = np.where(below_max < other_min, (below_max + other_min) / 2, (other_max + below_min) / 2)
    limit = np.where(below_max < other_min, (x_new < midpoint), (x_new > midpoint)).astype("float64")
    probability = np.where(separated, limit, probability)
    probability = np.where(constant, y.mean(axis=0), probability)
    return np.clip(probability, 0.0, 1.0)


def wvg_terciles(below):
    """The centre's rule: near normal is one third; above normal is the remainder; a below-normal
    probability above two thirds leaves the remainder to near normal."""
    near = np.minimum(1 / 3, 1 - below)
    above = np.clip(1 - below - near, 0, 1)
    return np.stack([below, near, above])


def wvg_stream(index, observed, index_forecast, reading_thresholds, leak=False):
    """(hindcast (year, category, cells), forecast (category, cells)) for supported cells; leave-one-year-out."""
    n = len(index)
    hindcast = np.empty((n, 3, observed.shape[1]))
    full = thresholds(observed)
    for t in range(n):
        keep = np.arange(n) != t
        bounds = full if reading_thresholds == "full_record" else thresholds(observed[keep])
        fit = np.arange(n) >= 0 if leak else keep
        labels = (observed[fit] < bounds[0] - TIE_MM).astype("float64")
        hindcast[t] = wvg_terciles(logistic_below(index[fit], labels, index[t]))
    labels = (observed < full[0] - TIE_MM).astype("float64")
    forecast = wvg_terciles(logistic_below(index, labels, index_forecast))
    return hindcast, forecast


def gaussian_terciles(x, y, x_new, bounds, reading_variance):
    """Per-cell OLS of y on x and the Gaussian tercile probabilities of the prediction at x_new."""
    x, y, x_new = (np.asarray(v, dtype="float64") for v in (x, y, x_new))
    n = len(x)
    xb, yb = x.mean(axis=0), y.mean(axis=0)
    dx = x - xb
    sxx = np.maximum((dx * dx).sum(axis=0), EPS)
    slope = (dx * (y - yb)).sum(axis=0) / sxx
    fitted = yb + slope * dx
    residual = np.maximum(((y - fitted) ** 2).sum(axis=0) / (n - 2), EPS)
    mean = yb + slope * (x_new - xb)
    if reading_variance == "prediction_error":
        variance = residual * (1 + 1 / n + (x_new - xb) ** 2 / sxx)
    elif reading_variance == "residual":
        variance = residual
    else:
        raise ValueError(reading_variance)
    sigma = np.sqrt(np.maximum(variance, EPS))
    below = ndtr((bounds[0] - mean) / sigma)
    above = 1 - ndtr((bounds[1] - mean) / sigma)
    return np.stack([below, 1 - below - above, above]), mean


def ereg_stream(model_means, observed, model_new, reading_variance, reading_thresholds, leak=False):
    """model_means (model, year, cells), observed (year, cells), model_new (model, cells).
    Returns per-model and combined hindcast/forecast probabilities and the combined fitted mean."""
    m, n, cells = model_means.shape
    hp = np.empty((m, n, 3, cells))
    fp = np.empty((m, 3, cells))
    fitted = np.empty((m, n, cells))
    full = thresholds(observed)
    for t in range(n):
        keep = np.arange(n) != t
        bounds = full if reading_thresholds == "full_record" else thresholds(observed[keep])
        fit = np.arange(n) >= 0 if leak else keep
        for i in range(m):
            hp[i, t], fitted[i, t] = gaussian_terciles(model_means[i, fit], observed[fit], model_means[i, t], bounds, reading_variance)
    for i in range(m):
        fp[i], _ = gaussian_terciles(model_means[i], observed, model_new[i], full, reading_variance)
    return hp, hp.mean(axis=0), fp, fp.mean(axis=0), fitted.mean(axis=0)


def cca_basis(x, y, xlat, ylat):
    """Centred, standardised, cosine-weighted fields and their full SVDs, shared by every mode choice."""
    xm, ym = x.mean(0), y.mean(0)
    xs, ys = np.maximum(x.std(0, ddof=1), EPS), np.maximum(y.std(0, ddof=1), EPS)
    xw, yw = np.sqrt(np.cos(np.deg2rad(xlat))), np.sqrt(np.cos(np.deg2rad(ylat)))
    a, b = (x - xm) * xw / xs, (y - ym) * yw / ys
    ux, sx, vxt = np.linalg.svd(a, full_matrices=False)
    uy, sy, vyt = np.linalg.svd(b, full_matrices=False)
    return {"xm": xm, "ym": ym, "xscale": xw / xs, "yscale": ys / yw, "ux": ux, "sx": np.maximum(sx, EPS), "vx": vxt.T,
            "uy": uy, "sy": np.maximum(sy, EPS), "vy": vyt.T, "n": len(x)}


def cca_from_basis(basis, modes):
    """The CCA model for (predictor modes, predictand modes, canonical modes), in factored form."""
    kx, ky = min(modes[0], len(basis["sx"])), min(modes[1], len(basis["sy"]))
    ux, sx, vx = basis["ux"][:, :kx], basis["sx"][:kx], basis["vx"][:, :kx]
    uy, sy, vy = basis["uy"][:, :ky], basis["sy"][:ky], basis["vy"][:, :ky]
    q, rho, rt = np.linalg.svd(ux.T @ uy, full_matrices=False)
    c = min(modes[2], len(rho))
    projection = basis["xscale"][:, None] * (vx / sx) @ q[:, :c]            # (px, c)
    return {"xmean": basis["xm"], "ymean": basis["ym"], "projection": projection, "rho": rho[:c], "rt": rt[:c] * sy[None, :],
            "vy": vy, "yscale": basis["yscale"], "n": basis["n"], "modes": (kx, ky, c)}


def cca_fit(x, y, xlat, ylat, modes):
    return cca_from_basis(cca_basis(x, y, xlat, ylat), modes)


def cca_predict_mean(model, x_new):
    scores = (np.atleast_2d(x_new) - model["xmean"]) @ model["projection"] * model["rho"]    # (m, c)
    return (scores @ model["rt"]) @ model["vy"].T * model["yscale"] + model["ymean"]


def _candidate_predictions(basis, x_new, candidates):
    """Predictions of every candidate mode choice for one predictor row, as (candidates, cells)."""
    return np.stack([cca_predict_mean(cca_from_basis(basis, modes), x_new)[0] for modes in candidates])


def _best(predictions, y, candidates):
    """Index of the candidate whose predictions (candidates, years, cells) correlate best with y, mean over cells."""
    best, best_score = 0, -np.inf
    for k in range(len(candidates)):
        score = _mean_correlation(predictions[k], y)
        if score > best_score + 1e-12:
            best, best_score = k, score
    return best, best_score


def cca_select(x, y, xlat, ylat, candidates=CCA_CANDIDATES):
    """Modes with the highest mean leave-one-year-out correlation over cells, using all years;
    returns the modes, the score, and the leave-one-year-out predictions of every candidate."""
    n = len(x)
    predictions = np.empty((len(candidates), n, y.shape[1]))
    for t in range(n):
        keep = np.arange(n) != t
        predictions[:, t] = _candidate_predictions(cca_basis(x[keep], y[keep], xlat, ylat), x[t], candidates)
    best, score = _best(predictions, y, candidates)
    return candidates[best], score, {modes: predictions[k] for k, modes in enumerate(candidates)}


def _mean_correlation(a, b):
    ac, bc = a - a.mean(0), b - b.mean(0)
    denominator = np.sqrt((ac * ac).sum(0) * (bc * bc).sum(0))
    r = np.where(denominator > EPS, (ac * bc).sum(0) / np.maximum(denominator, EPS), 0.0)
    return float(r.mean())


def student_terciles(mean, variance, df, bounds):
    sigma = np.sqrt(np.maximum(variance, EPS))
    below = stdtr(df, (bounds[0] - mean) / sigma)
    above = 1 - stdtr(df, (bounds[1] - mean) / sigma)
    return np.stack([below, 1 - below - above, above])


def cca_nested_hindcasts(x, y, xlat, ylat, candidates=CCA_CANDIDATES):
    """Leave-one-year-out hindcasts in which nothing about year t touches y[t]: for each held-out
    year the modes are selected by an inner leave-one-year-out over the other years, and the
    residual variance comes from those inner predictions. Returns (loo means (n, cells),
    variances (n, cells), degrees of freedom (n,), modes per year). One SVD pair serves every
    candidate; each pair of years is factored once and its predictions kept for both orders."""
    n, cells, k = len(x), y.shape[1], len(candidates)
    single = [cca_basis(x[np.arange(n) != t], y[np.arange(n) != t], xlat, ylat) for t in range(n)]
    pending = {t: {} for t in range(n)}              # pending[t][u]: inner predictions for year u with t and u both held out
    loo, variance, dof, modes_of = np.empty((n, cells)), np.empty((n, cells)), np.empty(n, dtype=int), []
    for t in range(n):
        inner = np.empty((k, n - 1, cells), dtype="float64")
        others = [u for u in range(n) if u != t]
        for j, u in enumerate(others):
            if u in pending[t]:
                inner[:, j] = pending[t].pop(u)
            else:
                keep = (np.arange(n) != t) & (np.arange(n) != u)
                basis = cca_basis(x[keep], y[keep], xlat, ylat)
                inner[:, j] = _candidate_predictions(basis, x[u], candidates)
                pending[u][t] = _candidate_predictions(basis, x[t], candidates).astype("float32")
        best, _ = _best(inner, y[others], candidates)
        modes = candidates[best]
        modes_of.append(modes)
        loo[t] = cca_predict_mean(cca_from_basis(single[t], modes), x[t])[0]
        dof[t] = max((n - 1) - modes[0] - 1, 1)
        variance[t] = ((y[others] - inner[best]) ** 2).sum(0) / dof[t]
    return loo, variance, dof, modes_of


def cca_stream(predictors, observed, predictors_new, xlat, ylat, reading_thresholds, leak=False):
    """predictors (model, year, px), observed (year, cells), predictors_new (model, px).
    Per model: nested mode selection and leave-one-year-out Student-t terciles for the hindcasts;
    modes selected on all training years for the forecast; equal average across models.
    Returns (hindcast (year, 3, cells), forecast (3, cells), hindcast mean, forecast modes)."""
    m, n, _ = predictors.shape
    hp = np.empty((m, n, 3, observed.shape[1]))
    fp = np.empty((m, 3, observed.shape[1]))
    means = np.empty((m, n, observed.shape[1]))
    chosen = []
    full = thresholds(observed)
    for i in range(m):
        modes, _, predictions = cca_select(predictors[i], observed, xlat, ylat)
        chosen.append(modes)
        if leak:
            model_all = cca_fit(predictors[i], observed, xlat, ylat, modes)
            loo = cca_predict_mean(model_all, predictors[i])
            df = max(n - modes[0] - 1, 1)
            residual = ((observed - loo) ** 2).sum(0) / df
            variance, dof = np.broadcast_to(residual, loo.shape), np.full(n, df)
        else:
            loo, variance, dof, _ = cca_nested_hindcasts(predictors[i], observed, xlat, ylat)
        means[i] = loo
        for t in range(n):
            keep = np.arange(n) != t
            bounds = full if reading_thresholds == "full_record" else thresholds(observed[keep])
            hp[i, t] = student_terciles(loo[t], variance[t] * (1 + 1 / (n - 1)), int(dof[t]), bounds)
        model = cca_fit(predictors[i], observed, xlat, ylat, modes)
        df = max(n - modes[0] - 1, 1)
        residual = ((observed - predictions[modes]) ** 2).sum(0) / df
        fp[i] = student_terciles(cca_predict_mean(model, predictors_new[i])[0], residual * (1 + 1 / n), df, full)
    return hp.mean(0), fp.mean(0), means.mean(0), chosen


# ---- verification and issue ----------------------------------------------------------

def rps(probabilities, observed_category, axis=-3):
    """Ranked probability score over the three ordered categories.

    `axis` is the category axis of `probabilities`; the observed categories have the same
    shape without that axis. Grid arrays (..., 3, lat, lon) use the default -3; the
    flattened (..., 3, cells) arrays inside `compute` use -2.
    """
    p = np.asarray(probabilities, dtype="float64")
    truth = np.stack([np.asarray(observed_category) == k for k in CATEGORIES], axis=axis).astype("float64")
    return np.sum((np.cumsum(p, axis=axis) - np.cumsum(truth, axis=axis)) ** 2, axis=axis)


def dominant(probabilities):
    """Highest probability category; ties go to near normal, then to the lower category."""
    p = np.asarray(probabilities)
    order = np.stack([p[1], p[0], p[2]])                 # near first so a tie resolves to near normal
    index = np.argmax(order, axis=0)
    return np.array([1, 0, 2])[index].astype("int16")


# ---- the whole job from the provider snapshot ----------------------------------------

def provider_files(provider, model, init):
    return [Path(provider) / "models" / model / f"precip_init{init:02d}.nc"]


def sst_files(provider, init):
    return [Path(provider) / "sst" / "cfsv2" / f"sst_init{init:02d}.nc"]


@lru_cache(maxsize=4)
def _observed_fine(provider, init, years_key, token):
    return read_observed_precipitation(Path(provider) / "observations/chirps-v2p0-monthly-0p05.nc", init, list(years_key))


@lru_cache(maxsize=8)
def _prepared(provider, init, years_key, forecast_year, obs_regridding, month_lengths, index_box_mean, token):
    """Stage 2 for one reading of the preparation conventions; cached because many combinations share it."""
    years = list(years_key)
    all_years = sorted(years + [forecast_year])
    provider = Path(provider)
    conventions = {"month_lengths": month_lengths}
    model_native, members = {}, {}
    for model in MODELS:
        model_native[model], members[model] = read_model_precipitation(provider_files(provider, model, init), init, all_years, conventions)
    observed_fine = _observed_fine(str(provider), init, tuple(years), token)
    observed, support = regrid_observations(observed_fine, obs_regridding)
    observed_sst = read_observed_sst(provider / "observations/ersst-v5-monthly.nc", init, years)
    model_sst = read_model_sst(sst_files(provider, init), init, all_years)
    index, index_forecast = wvg_index(observed_sst, model_sst.sel(year=years), model_sst.sel(year=[forecast_year]), index_box_mean)
    plat, plon = model_native[MODELS[0]]["lat"].values, model_native[MODELS[0]]["lon"].values
    predictor = np.stack([model_native[m].values for m in MODELS])                       # (model, all_years, plat, plon)
    on_target = np.stack([regrid_models(model_native[m]).values for m in MODELS])       # (model, all_years, lat, lon)
    is_train = np.isin(all_years, years)
    return {"years": np.asarray(years), "forecast_year": forecast_year, "plat": plat, "plon": plon,
            "predictor_train": predictor[:, is_train], "predictor_new": predictor[:, ~is_train][:, 0],
            "model_train": on_target[:, is_train], "model_new": on_target[:, ~is_train][:, 0],
            "observed": observed.values, "support": support, "index": index, "index_forecast": index_forecast,
            "members": members}


def compute(provider, params, conventions=None, stages=("prepare", "wvg", "ereg", "cca", "combine", "verify", "issue"), token="", leak=None):
    """Every pinned array as an xarray Dataset. `stages` limits the work; CCA is the expensive stage."""
    options = {**DEFAULT, **(conventions or {})}
    init, years, forecast_year = int(params["init_month"]), [int(y) for y in params["training_years"]], int(params["forecast_year"])
    prepared = _prepared(str(provider), init, tuple(years), forecast_year, options["obs_regridding"], options["month_lengths"], "unweighted", token)
    support = prepared["support"]
    cells = np.flatnonzero(support.ravel())
    n, nlat, nlon = len(years), len(TARGET_LAT), len(TARGET_LON)
    observed = prepared["observed"].reshape(n, -1)[:, cells]
    full = thresholds(observed)
    categories = np.empty((n, len(cells)), dtype="int16")
    for t in range(n):
        keep = np.arange(n) != t
        bounds = full if options["thresholds"] == "full_record" else thresholds(observed[keep])
        categories[t] = category(observed[t], bounds)

    def spread(values, shape_front=()):
        """Supported-cell arrays back onto the full grid with zero fill."""
        out = np.zeros((*shape_front, nlat * nlon), dtype="float64")
        out[..., cells] = values
        return out.reshape(*shape_front, nlat, nlon)

    data = {
        "prepare_observed_mm": (("year", "lat", "lon"), spread(observed, (n,))),
        "prepare_support": (("lat", "lon"), support.astype("int16")),
        "prepare_model_hindcast_mean_mm": (("model", "year", "lat", "lon"), prepared["model_train"]),
        "prepare_model_forecast_mean_mm": (("model", "lat", "lon"), prepared["model_new"]),
        "prepare_model_predictor_mm": (("model", "year", "plat", "plon"), prepared["predictor_train"]),
        "prepare_model_predictor_forecast_mm": (("model", "plat", "plon"), prepared["predictor_new"]),
        "prepare_tercile_lower_mm": (("lat", "lon"), spread(full[0])),
        "prepare_tercile_upper_mm": (("lat", "lon"), spread(full[1])),
        "prepare_observed_category": (("year", "lat", "lon"), spread(categories, (n,)).astype("int16")),
        "prepare_sst_index": (("year",), prepared["index"]),
        "prepare_sst_index_forecast": ((), prepared["index_forecast"]),
    }
    coords = {"year": np.asarray(years), "model": np.arange(len(MODELS)), "category": np.asarray(CATEGORIES), "stream": np.arange(len(STREAMS)),
              "lat": TARGET_LAT, "lon": TARGET_LON, "plat": prepared["plat"], "plon": prepared["plon"]}
    streams = {}
    if "wvg" in stages:
        hp, fp = wvg_stream(prepared["index"], observed, prepared["index_forecast"], options["thresholds"], leak == "wvg_leak")
        streams["wvg"] = (hp, fp)
        data["wvg_hindcast_probability"] = (("year", "category", "lat", "lon"), spread(hp, (n, 3)))
        data["wvg_forecast_probability"] = (("category", "lat", "lon"), spread(fp, (3,)))
    if "ereg" in stages:
        model_train = prepared["model_train"].reshape(len(MODELS), n, -1)[:, :, cells]
        model_new = prepared["model_new"].reshape(len(MODELS), -1)[:, cells]
        mhp, hp, mfp, fp, fitted = ereg_stream(model_train, observed, model_new, options["ereg_variance"], options["thresholds"], leak == "ereg_no_cross_validation")
        streams["ereg"] = (hp, fp)
        data["ereg_model_hindcast_probability"] = (("model", "year", "category", "lat", "lon"), spread(mhp, (len(MODELS), n, 3)))
        data["ereg_model_forecast_probability"] = (("model", "category", "lat", "lon"), spread(mfp, (len(MODELS), 3)))
        data["ereg_hindcast_probability"] = (("year", "category", "lat", "lon"), spread(hp, (n, 3)))
        data["ereg_forecast_probability"] = (("category", "lat", "lon"), spread(fp, (3,)))
        data["ereg_fitted_mean_mm"] = (("year", "lat", "lon"), spread(fitted, (n,)))
    if "cca" in stages:
        predictors = prepared["predictor_train"].reshape(len(MODELS), n, -1)
        predictors_new = prepared["predictor_new"].reshape(len(MODELS), -1)
        xlat = np.repeat(prepared["plat"], len(prepared["plon"]))
        ylat = np.repeat(TARGET_LAT, nlon)[cells]
        hp, fp, mean, modes = cca_stream(predictors, observed, predictors_new, xlat, ylat, options["thresholds"], leak == "cca_future_training")
        streams["cca"] = (hp, fp)
        data["cca_hindcast_probability"] = (("year", "category", "lat", "lon"), spread(hp, (n, 3)))
        data["cca_forecast_probability"] = (("category", "lat", "lon"), spread(fp, (3,)))
        data["cca_hindcast_mean_mm"] = (("year", "lat", "lon"), spread(mean, (n,)))
        data["cca_modes_selected"] = (("model",), np.array([m[2] for m in modes], dtype="int16"))
    if "combine" in stages and len(streams) == 3:
        hp = np.mean([streams[s][0] for s in STREAMS], axis=0)
        fp = np.mean([streams[s][1] for s in STREAMS], axis=0)
        data["combine_hindcast_probability"] = (("year", "category", "lat", "lon"), spread(hp, (n, 3)))
        data["combine_forecast_probability"] = (("category", "lat", "lon"), spread(fp, (3,)))
        data["combine_available_streams"] = (("lat", "lon"), (support * 3).astype("int16"))
        if "verify" in stages:
            climatology = np.full_like(hp, 1 / 3)
            baseline = rps(climatology, categories, axis=-2).mean(0)
            stream_rps = np.stack([rps(streams[s][0], categories, axis=-2).mean(0) for s in STREAMS])
            objective_rps = rps(hp, categories, axis=-2).mean(0)
            data["verify_stream_rps"] = (("stream", "lat", "lon"), spread(stream_rps, (len(STREAMS),)))
            data["verify_stream_rpss"] = (("stream",), 1 - stream_rps.mean(1) / baseline.mean())
            data["verify_objective_rps"] = (("lat", "lon"), spread(objective_rps))
            data["verify_objective_rpss"] = ((), float(1 - objective_rps.mean() / baseline.mean()))
            data["verify_climatology_rps"] = (("lat", "lon"), spread(baseline))
        if "issue" in stages:
            data["issue_forecast_probability"] = (("category", "lat", "lon"), spread(fp, (3,)))
            data["issue_dominant_category"] = (("lat", "lon"), spread(dominant(fp)).astype("int16"))
    ds = xr.Dataset(data, coords=coords)
    for name in ds.data_vars:
        if name.endswith("_mm"):
            ds[name].attrs["units"] = "mm"
    ds["model"].attrs["model_names"] = ",".join(MODELS)
    ds["stream"].attrs["stream_names"] = ",".join(STREAMS)
    ds.attrs["members"] = str(prepared["members"])
    return ds
