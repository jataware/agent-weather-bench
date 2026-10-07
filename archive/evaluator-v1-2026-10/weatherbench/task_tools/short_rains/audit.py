"""Separate scalar/matrix implementation and source reduction checks.

This deliberately imports no calculation from reference.py. Candidate order is
read from the frozen public JSON, regression uses least squares on a design
matrix, quantiles use interpolation on probability positions, and verification
uses direct two-CDF category targets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import xarray as xr
from scipy.special import stdtr


def independent(inputs):
    rain = xr.open_dataset(inputs / "rainfall.nc")
    sst = xr.open_dataset(inputs / "sst.nc")
    gcm = xr.open_dataset(inputs / "forecast-index.nc")
    spec = json.loads((inputs / "candidates.json").read_text())
    dates = rain.time.values.astype("datetime64[M]").astype(int)
    rain_year = dates // 12 + 1970
    rain_month = dates % 12 + 1
    y = np.array([np.sum(rain.monthly_rainfall_scaled.values[(rain_year == yr) & (rain_month >= 10)], axis=0) * 30 for yr in range(1993, 2020)])
    raw = sst.sst.values.reshape(43, 12, 5)[12:]
    ocean = {(g, w): raw[:, 8-g-w:8-g].mean(axis=1) for g in range(3) for w in range(1, 4)}
    gc = gcm.gcm_iod.values

    def values(c, fit, predict):
        if c["feature"] == "forecast-iod":
            return gc[fit], gc[predict]
        a = ocean[(c["gap"], c["width"])]
        name = c["feature"]
        if name in ("nino34", "wpac", "wv"):
            col = {"nino34": 0, "wpac": 3, "wv": 4}[name]
            return a[fit, col], a[predict, col]
        if name == "iod":
            d = a[:, 1] - a[:, 2]
            return d[fit], d[predict]
        means = a[fit].mean(axis=0)
        sd = a[fit].std(axis=0, ddof=1)
        z = (a - means) / sd
        d = z[:, 3] - z[:, 0] if name == "wpg" else z[:, 0] - z[:, 4]
        return d[fit], d[predict]

    def prob(c, region, end, test):
        fit = np.arange(end)
        x, xp = values(c, fit, np.asarray(test))
        yy = y[fit, region]
        pp = (np.arange(len(yy)) + .5) / len(yy)
        bounds = np.interp([1/3, 2/3], pp, np.sort(yy))
        if c["transform"] == "log1p":
            yy, cut = np.log1p(yy), np.log1p(bounds)
        else:
            cut = bounds
        # Center the design for a well-conditioned independent least-squares fit.
        mx = x.mean()
        design = np.column_stack([np.ones(len(x)), x-mx])
        coefficient = np.linalg.lstsq(design, yy, rcond=None)[0]
        new = np.column_stack([np.ones(len(xp)), xp-mx])
        mu = new @ coefficient
        residual = yy - design @ coefficient
        noise = np.sum(residual**2) / (len(fit)-2)
        inv = np.linalg.inv(design.T @ design)
        leverage = np.sum((new @ inv) * new, axis=1)
        scale = np.sqrt(noise * (1+leverage))
        cdf = stdtr(len(fit)-2, (cut[None, :]-mu[:, None])/scale[:, None])
        p = np.column_stack([cdf[:, 0], np.diff(cdf, axis=1)[:, 0], 1-cdf[:, 1]])
        return p, bounds

    def loss(p, obs, b):
        targets = np.column_stack([obs < b[0], obs < b[1]])
        return ((np.column_stack([p[:, 0], p[:, :2].sum(axis=1)])-targets)**2).sum(axis=1)/2

    def select(region, end):
        scores = np.array([np.mean([loss(*lambda_unpack(prob(c, region, i, [i]), y[i, region])) for i in range(8, end)]) for c in spec])
        winner = int(np.flatnonzero(scores - scores.min() <= 1e-12)[0])
        return winner, scores

    # Keep loss invocation explicit: tuple expansion of p, observed, boundaries.
    def lambda_unpack(pair, obs):
        p, b = pair
        return p, np.array([obs]), b

    probabilities = np.empty((4, 15, 3, 3))
    thresholds = np.empty((15, 3, 2))
    winners = np.empty((15, 3), int)
    scores = np.empty((15, 3, 108))
    prod = np.empty((4, 4, 3, 3))
    prod_b = np.empty((3, 2))
    prod_w = np.empty(3, int)
    prod_s = np.empty((3, 108))
    fixed = [{"feature":"iod", "gap":0, "width":2, "transform":"identity"}, {"feature":"forecast-iod", "transform":"identity"}]
    for r in range(3):
        for pos, yr in enumerate(range(2005, 2020)):
            end = yr-1993
            winner, ls = select(r, end)
            winners[pos, r], scores[pos, r] = winner, ls
            probabilities[0, pos, r] = 1/3
            for si, c in enumerate([*fixed, spec[winner]], 1):
                p, b = prob(c, r, end, [end])
                probabilities[si, pos, r], thresholds[pos, r] = p[0], b
        winner, ls = select(r, 27)
        prod_w[r], prod_s[r] = winner, ls
        prod[0, :, r] = 1/3
        for si, c in enumerate([*fixed, spec[winner]], 1):
            p, b = prob(c, r, 27, list(range(27, 31)))
            prod[si, :, r], prod_b[r] = p, b
    rps = np.empty((4, 15, 3))
    for ri in range(3):
        for yi in range(15):
            for si in range(4):
                rps[si, yi, ri] = loss(probabilities[si, yi, ri][None], y[yi+12, ri:ri+1], thresholds[yi, ri])[0]
    skill = 1-rps.sum(axis=1)/rps[0].sum(axis=0)[None]
    return {"seasonal_total": y, "probability": probabilities, "threshold":thresholds,
            "selected_candidate":winners, "inner_rps":scores, "rps":rps, "rpss":skill}, {
            "probability":prod, "threshold":prod_b, "selected_candidate":prod_w, "inner_rps":prod_s}


def audit(root):
    cv, prod = independent(root / "agent-inputs")
    errors = {}
    for file, actual in (("hindcasts.nc", cv), ("forecast.nc", prod)):
        gold = xr.open_dataset(root / "controller" / file)
        for name, a in actual.items():
            if name == "seasonal_total":
                continue
            b = gold[name].values
            error = float(np.max(np.abs(a-b)))
            errors[f"{file}:{name}"] = error
            np.testing.assert_allclose(a, b, rtol=1e-10, atol=1e-10)
    gold = xr.open_dataset(root / "controller/seasonal.nc")
    np.testing.assert_allclose(cv["seasonal_total"], gold.seasonal_total.values, rtol=1e-12)
    errors["seasonal.nc:seasonal_total"] = float(np.max(np.abs(cv["seasonal_total"]-gold.seasonal_total.values)))
    return {"independent_implementation_agreement": True, "max_absolute_errors":errors,
            "independent_regression": "centered-design least squares and matrix leverage",
            "independent_quantile": "linear interpolation on (rank-0.5)/n positions",
            "agent_attempts_used_for_reference_or_prompt": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("var/private/tasks/short-rains-workflow"))
    args = parser.parse_args()
    result = audit(args.root)
    (args.root / "controller/reference-validation.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
