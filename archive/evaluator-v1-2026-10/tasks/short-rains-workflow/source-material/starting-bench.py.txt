"""bench.py — the locked evaluation harness for v4zeek.

ONE objective, fixed here and not reachable by any candidate:

    RPSS of a tercile-probability forecast of a FIXED target, on years the
    candidate never saw, referenced against climatology.

    0.0  = no better than forecasting the historical distribution
    > 0  = better than that
    < 0  = worse than doing nothing
    1.0  = perfect

Why RPSS and not correlation: the signal in this problem is one-sided (a predictor
informs bad years and says nothing about good ones). A point-forecast metric averages
that to zero, which is exactly how the prior work (AGUv0-v3) concluded "no signal" and
then spent three revisions inventing conditional metrics to get it back. A proper
probabilistic score detects one-sided signal without being told to look for it, so
"which evaluation mode" stops being a search axis.

The metric is registered into deepscale's own registry at import time via
`register_metric`, so it is retrieved through `get_metric("rpss_oos")` like any other
deepscale metric. Nothing in the deepscale checkout is modified.

WHAT IS FIXED BY A BENCHMARK (candidates cannot influence any of it):
  - the target: fixture, bounding box, month window, years
  - the fold split
  - the tercile boundaries (fit on TRAIN years only, never on test years)
  - the climatology reference
  - the score

The target arrives entirely through argv, so adding a new region or season needs a NEW
BENCHMARK REGISTRATION, not an edit to this file. That is what keeps this evaluator
lockable: what varies is a parameter, what defines the measurement is the code.

WHAT A CANDIDATE CHOOSES:
  - which ocean feature(s) to build, at what lead
  - what model maps feature -> tercile probabilities

CANDIDATE CONTRACT — a candidate module defines:

    def fit_predict(ctx) -> np.ndarray of shape (len(ctx.test_years), 3)

  rows are tercile probabilities [P(below), P(near), P(above)], each summing to 1.
  `ctx` exposes train years, train target values, and CAUSAL predictor access only.
  Test-year target values are never placed on ctx.

Usage:
    python bench.py [--fixture F --bbox S,N,W,E --months M,M,M | --synthetic]
                    [--protocol walkforward|kfold] [--folds N] [--shuffle SEED]
                    [--label NAME] candidates/<name>.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import traceback
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import xarray as xr

from deepscale.metrics.base import MetricBase
from deepscale.metrics.rpss import _cpt_boundaries          # CPT-compatible tercile edges
from deepscale.registry import get_metric, register_metric

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

CLIM_BASE = (1991, 2020)          # fixed anomaly base for predictors; independent of folds
DAYS_PER_MONTH = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


# ── the out-of-sample RPSS, registered into deepscale ─────────────────────────
@register_metric("rpss_oos")
class OutOfSampleRPSS(MetricBase):
    """RPSS where the tercile boundaries and the climatology reference come from
    TRAIN years only.

    deepscale's built-in `rpss` derives its boundaries from whatever obs it is handed.
    Handing it test-year obs would let the test set define its own categories, which is
    a real (if small) leak. This variant takes the boundaries as an explicit argument so
    they can be fit on training years and applied to test years.

    Uses deepscale's own `_cpt_boundaries`, so the tercile definition is identical to
    the built-in metric and the two are directly comparable.

    Returns per-year (rps_forecast, rps_climatology) rather than a scalar, so the caller
    pools across folds instead of averaging ratios of ratios.
    """

    def compute(self, forecast, obs, boundaries=None, **kwargs):
        p = np.asarray(forecast, dtype=float)             # (n, 3)
        y = np.asarray(obs, dtype=float)                  # (n,)
        if p.ndim != 2 or p.shape[1] != 3:
            raise ValueError(f"forecast must be (n,3) tercile probabilities; got {p.shape}")
        if len(y) != len(p):
            raise ValueError(f"obs has {len(y)} years, forecast has {len(p)}")
        if boundaries is None:
            raise ValueError("rpss_oos requires train-fitted `boundaries=(t33, t67)`")
        t33, t67 = boundaries

        # CPT convention: category 0 if y < t33, 1 if y < t67, else 2
        cat = np.where(t33 > y, 0, np.where(t67 > y, 1, 2))
        obs_oh = np.stack([(cat == i).astype(float) for i in range(3)], axis=1)

        rps_f = np.sum((np.cumsum(p, 1) - np.cumsum(obs_oh, 1)) ** 2, axis=1) / 2.0
        clim = np.full_like(p, 1.0 / 3.0)
        rps_c = np.sum((np.cumsum(clim, 1) - np.cumsum(obs_oh, 1)) ** 2, axis=1) / 2.0
        return rps_f, rps_c


# ── predictor context handed to candidates ────────────────────────────────────
class Context:
    """Causal access to predictors, plus train-only target values.

    `preseason(box, year, gap, width)` returns the mean SST anomaly over a window of
    `width` months ending `gap+1` months before the target window starts, for that year.
    It is structurally impossible to request a month inside or after the target window,
    so a candidate cannot peek forward no matter what it asks for.

    Any statistic a candidate fits (means, regression coefficients, thresholds) MUST be
    fit on `train_years` only. The shuffled control and the climatology candidate are
    the harness's checks that this discipline held.
    """

    def __init__(self, sst_anoms, months, years, train_years, test_years, y_train):
        self._sst = sst_anoms
        self.months = list(months)
        self.window_start_month = self.months[0]
        self.wraps = self.months[0] > self.months[-1]
        self.years = np.asarray(years)
        self.train_years = np.asarray(train_years)
        self.test_years = np.asarray(test_years)
        self.y_train = np.asarray(y_train, dtype=float)
        self.boxes = tuple(sst_anoms)

    def _month_of(self, year, offset):
        """Calendar (year, month) `offset` months before the window start of `year`.

        A window is labelled by the year its LAST month falls in, so a Dec-Jan-Feb
        window for year Y starts in Dec of Y-1. All of this is arithmetic on an absolute
        month index, because year-wrap is the single most common silent bug in this kind
        of code (tests/test_wrap.py pins it).
        """
        start_year = year - 1 if self.wraps else year
        abs_idx = start_year * 12 + (self.window_start_month - 1) - offset
        return abs_idx // 12, abs_idx % 12 + 1

    def preseason(self, box, year, gap=0, width=2):
        """Mean SST anomaly over `width` months ending gap+1 months before the window."""
        vals = []
        for k in range(width):
            yy, mm = self._month_of(year, gap + 1 + k)
            try:
                v = float(self._sst[box].sel(year=yy, month=mm).values)
            except (KeyError, IndexError):
                return np.nan
            if not np.isfinite(v):
                return np.nan
            vals.append(v)
        return float(np.mean(vals))

    def feature(self, box, gap=0, width=2, years=None):
        """`preseason` evaluated over a list of years -> 1-D array."""
        yrs = self.years if years is None else np.asarray(years)
        return np.array([self.preseason(box, int(y), gap, width) for y in yrs])


# ── fixture loading ───────────────────────────────────────────────────────────
def load_sst(prefix="sst_"):
    """Monthly SST anomalies per box as (year, month) grids. The anomaly base is fixed,
    so it never depends on the fold split.

    `prefix` selects a fixture family: "sst_" is the 1981-2023 set that matches CHIRPS,
    "sstlong_" is the 1940-2023 set that matches the ERA5 record. They are separate files
    rather than one overwritten set so a long-record run and a short-record run can never
    silently read each other's data.
    """
    out = {}
    for f in sorted(DATA.glob(f"{prefix}*_monthly.nc")):
        box = f.stem.replace(prefix, "").replace("_monthly", "")
        da = xr.open_dataset(f)["sst"]
        wgt = np.cos(np.deg2rad(da.lat))
        series = da.weighted(wgt).mean(["lat", "lon"])                 # area mean
        base = series.sel(time=slice(f"{CLIM_BASE[0]}-01", f"{CLIM_BASE[1]}-12"))
        clim = base.groupby("time.month").mean("time")
        anom = series.groupby("time.month") - clim
        anom = anom.assign_coords(year=anom["time.year"], month=anom["time.month"])
        out[box] = anom.set_index(time=["year", "month"]).unstack("time")
    if not out:
        raise SystemExit(f"no SST fixtures in {DATA} — run src/fetch_fixtures.py")
    return out


def build_synthetic(sst_anoms):
    """A target with a KNOWN dependence on Nino-3.4. Harness self-test only."""
    rng = np.random.default_rng(20260805)
    years = np.arange(1982, 2024)
    drv = np.array([
        np.nanmean([float(sst_anoms["nino34"].sel(year=y - 1, month=11).values),
                    float(sst_anoms["nino34"].sel(year=y - 1, month=12).values)])
        for y in years])
    y = -1.2 * drv + rng.normal(0, 1.0, len(years))
    ok = np.isfinite(y) & np.isfinite(drv)
    return years[ok], y[ok]


def build_target(fixture, bbox, months):
    """The fixed predictand: one scalar per season-year, area-mean over `bbox`, summed
    over `months`. Years with any missing or non-finite month are dropped, so every
    scored year is a complete season."""
    f = DATA / fixture
    if not f.exists():
        raise SystemExit(f"missing fixture {f} — run src/fetch_fixtures.py")
    ds = xr.open_dataset(f)
    var = [v for v in ds.data_vars][0]
    da = ds[var]

    s, n, w, e = bbox
    lat_asc = float(da.lat[0]) < float(da.lat[-1])
    lon_asc = float(da.lon[0]) < float(da.lon[-1])
    da = da.sel(lat=slice(s, n) if lat_asc else slice(n, s),
                lon=slice(w, e) if lon_asc else slice(e, w))
    if da.sizes.get("lat", 0) == 0 or da.sizes.get("lon", 0) == 0:
        raise SystemExit(f"bbox {bbox} selects no cells from {fixture}")

    wgt = np.cos(np.deg2rad(da.lat))
    series = da.weighted(wgt).mean(["lat", "lon"])                     # mm/day, NaN-aware
    days = xr.DataArray([DAYS_PER_MONTH[int(m) - 1] for m in series["time.month"].values],
                        coords={"time": series.time}, dims="time")
    monthly = series * days                                            # mm/day -> mm/month

    yr = monthly["time.year"].values
    mo = monthly["time.month"].values
    vals = monthly.values
    wraps = months[0] > months[-1]
    # a window is labelled by the year of its LAST month; earlier months roll forward
    roll = [m for m in months if m > months[-1]] if wraps else []
    label = np.where(np.isin(mo, roll), yr + 1, yr)
    keep = np.isin(mo, months)

    years, totals = [], []
    for y in sorted(set(label[keep])):
        sel = keep & (label == y)
        if sel.sum() != len(months):
            continue                                                   # incomplete season
        v = vals[sel]
        if not np.isfinite(v).all():
            continue
        years.append(int(y))
        totals.append(float(v.sum()))
    if len(years) < 25:
        raise SystemExit(f"only {len(years)} complete seasons for bbox={bbox} months={months}")
    return np.array(years), np.array(totals)


# ── fold construction ─────────────────────────────────────────────────────────
def make_folds(years, protocol, n_folds):
    """walkforward: expanding train window, contiguous forward test blocks (causal).
       kfold:       contiguous year blocks held out in turn (uses every year, mildly
                    optimistic because later years inform earlier predictions)."""
    n = len(years)
    if protocol == "walkforward":
        first = max(20, n // 2)                       # minimum training sample
        edges = np.linspace(first, n, n_folds + 1).astype(int)
        folds = []
        for i in range(n_folds):
            lo, hi = edges[i], edges[i + 1]
            if hi > lo:
                folds.append((np.arange(0, lo), np.arange(lo, hi)))
        return folds
    if protocol == "kfold":
        blocks = np.array_split(np.arange(n), n_folds)
        return [(np.setdiff1d(np.arange(n), b), b) for b in blocks if len(b)]
    raise ValueError(protocol)


def load_candidate(path):
    spec = importlib.util.spec_from_file_location("candidate", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "fit_predict"):
        raise SystemExit(f"{path} defines no fit_predict(ctx)")
    return mod


def evaluate(candidate, sst, months, years, y, protocol, n_folds):
    """Run every fold and return pooled per-year (rps_forecast, rps_clim) plus per-fold RPSS."""
    metric = get_metric("rpss_oos")()
    rf_all, rc_all, per_fold = [], [], []
    for tr_i, te_i in make_folds(years, protocol, n_folds):
        ctx = Context(sst, months, years, years[tr_i], years[te_i], y[tr_i])
        p = np.asarray(candidate.fit_predict(ctx), dtype=float)
        if p.shape != (len(te_i), 3):
            raise SystemExit(f"candidate returned {p.shape}, expected {(len(te_i), 3)}")
        if not np.allclose(p.sum(1), 1.0, atol=1e-6):
            raise SystemExit("candidate rows are not probability distributions")
        p = np.clip(p, 1e-9, 1.0)
        p = p / p.sum(1, keepdims=True)
        rf, rc = metric.compute(p, y[te_i], boundaries=_cpt_boundaries(y[tr_i]))
        rf_all.append(rf)
        rc_all.append(rc)
        per_fold.append(float(1.0 - rf.sum() / rc.sum()))
    return np.concatenate(rf_all), np.concatenate(rc_all), per_fold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--fixture", default="ca_precip_monthly.nc")
    ap.add_argument("--sst-prefix", default="sst_",
                    help="SST fixture family: sst_ (1981-2023) or sstlong_ (1940-2023)")
    ap.add_argument("--bbox", default="32,42.5,-125,-114",
                    help="lat_s,lat_n,lon_w,lon_e")
    ap.add_argument("--months", default="12,1,2",
                    help="season window, in order; may wrap the year boundary")
    ap.add_argument("--label", default=None, help="name for this target in the output")
    ap.add_argument("--synthetic", action="store_true",
                    help="use the planted-signal self-test target instead of a fixture")
    ap.add_argument("--protocol", default="walkforward", choices=("walkforward", "kfold"))
    ap.add_argument("--folds", type=int, default=6)
    ap.add_argument("--year-min", type=int, default=None,
                    help="restrict the target to years >= this. Used to put an "
                         "observed-index and a forecast-index candidate on IDENTICAL "
                         "years, since model reforecasts are shorter than the obs record.")
    ap.add_argument("--year-max", type=int, default=None)
    ap.add_argument("--shuffle", type=int, default=None,
                    help="permute target years with this seed — the null control. "
                         "A correct harness scores ~0 here for every candidate.")
    a = ap.parse_args()

    try:
        bbox = [float(v) for v in a.bbox.split(",")]
        months = [int(v) for v in a.months.split(",")]
        if len(bbox) != 4:
            raise SystemExit("--bbox needs 4 comma-separated numbers: lat_s,lat_n,lon_w,lon_e")

        sst = load_sst(a.sst_prefix)
        if a.synthetic:
            years, y = build_synthetic(sst)
            label = "synthetic"
        else:
            years, y = build_target(a.fixture, bbox, months)
            label = a.label or f"{Path(a.fixture).stem}:{a.bbox}:{a.months}"

        if a.year_min is not None or a.year_max is not None:
            keep = np.ones(len(years), dtype=bool)
            if a.year_min is not None:
                keep &= years >= a.year_min
            if a.year_max is not None:
                keep &= years <= a.year_max
            if keep.sum() < 25:
                raise SystemExit(f"year filter leaves {keep.sum()} seasons, need >= 25")
            years, y = years[keep], y[keep]

        if a.shuffle is not None:
            y = y[np.random.default_rng(a.shuffle).permutation(len(y))]

        cand = load_candidate(Path(a.candidate))
        rps_f, rps_c, per_fold = evaluate(cand, sst, months, years, y, a.protocol, a.folds)

        print(json.dumps({
            "rpss": round(float(1.0 - rps_f.sum() / rps_c.sum()), 4),
            "rpss_fold_stdev": round(float(np.std(per_fold)), 4),
            "rpss_fold_min": round(float(np.min(per_fold)), 4),
            "rpss_fold_max": round(float(np.max(per_fold)), 4),
            "n_test_years": int(len(rps_f)),
            "n_folds": len(per_fold),
            "n_years_total": int(len(years)),
            "year_first": int(years.min()),
            "year_last": int(years.max()),
            "protocol": a.protocol,
            "target": label,
            "bbox": a.bbox,
            "months": a.months,
            "sst_prefix": a.sst_prefix,
            "year_min": a.year_min, "year_max": a.year_max,
            "shuffled": "yes" if a.shuffle is not None else "no",
            "candidate": Path(a.candidate).name,
            "status": "ok",
        }))
    except SystemExit:
        raise
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"status": "crashed", "error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
