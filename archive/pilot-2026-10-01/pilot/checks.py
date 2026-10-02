"""Independent numerical checks. Never import either competing toolkit."""
from pathlib import Path
import json

import numpy as np
import xarray as xr
from PIL import Image

from .common import read, task, inventory


def compare(actual, expected, atol=1e-4, rtol=1e-6):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and compare(actual[k], v, atol, rtol)
                                                 for k, v in expected.items())
    if isinstance(expected, (str, bool)) or expected is None:
        return type(actual) is type(expected) and actual == expected
    try:
        a, b = np.asarray(actual), np.asarray(expected)
        if a.shape != b.shape:
            return False
        if b.dtype.kind in "US":
            return np.array_equal(a, b)
        if a.dtype.kind not in "iuf" or b.dtype.kind not in "iuf":
            return False
        return bool(np.isfinite(a).all() and np.isfinite(b).all() and
                    np.allclose(a, b, atol=atol, rtol=rtol))
    except (ValueError, TypeError):
        return False


def weighted(values, lat):
    w = np.broadcast_to(np.cos(np.deg2rad(lat))[:, None], values.shape)
    valid = np.isfinite(values)
    mass = np.where(valid, w, 0).sum(axis=(-2, -1))
    if (mass <= 0).any():
        raise ValueError("Empty spatial support")
    return np.where(valid, values * w, 0).sum(axis=(-2, -1)) / mass


def kenya_reference(raw, init, source):
    """Raw cumulative liquid-water mass, including an actual lead-zero field."""
    ds = xr.open_zarr(raw, chunks=None)
    a = ds.tp.where((ds.latitude >= -5) & (ds.latitude <= 5) &
                    (ds.longitude >= 34) & (ds.longitude <= 42), drop=True)
    a = a.transpose("number", "step", "latitude", "longitude")
    if a.attrs.get("units") not in ("kg m**-2", "kg m-2", "mm"):
        raise ValueError("Unsupported raw rainfall units")
    leads = a.step.values / np.timedelta64(1, "D")
    indices = [np.flatnonzero(leads == d) for d in range(43)]
    if not all(len(i) == 1 for i in indices):
        raise ValueError("Need unique daily cumulative leads 0 through 42")
    values = a.values[:, np.array(indices).ravel()].astype(float)
    if not np.isfinite(values).all() or values.shape[0] < 2:
        raise ValueError("Missing cells or insufficient members")
    inc = np.diff(values, axis=1)
    if inc.min() < -1e-4:
        raise ValueError("Substantial negative increments require source audit")
    weekly = np.maximum(inc, 0).reshape(values.shape[0], 6, 7, *values.shape[-2:]).sum(2)
    regional = weighted(weekly, a.latitude.values)
    return dict(period_end_lead_days=[7, 14, 21, 28, 35, 42],
                ensemble_mean_mm=weekly.mean(0).tolist(),
                regional_median_mm=np.median(regional, axis=0).tolist(),
                regional_spread_mm=regional.std(axis=0, ddof=1).tolist(),
                latitude=a.latitude.values.tolist(), longitude=a.longitude.values.tolist(),
                units="mm", source_url=source, figure="/work/outlook.png")


def box(a, west):
    bounds = (50, 70, -10, 10) if west else (90, 110, -10, 0)
    sub = a.where((a.lon >= bounds[0]) & (a.lon <= bounds[1]) &
                  (a.lat >= bounds[2]) & (a.lat <= bounds[3]), drop=True)
    return weighted(sub.values, sub.lat.values)


def iod_reference(forecast, observed, windows, sources):
    """Requires audited valid_date coordinates, never guessed lead labels."""
    f = xr.load_dataset(forecast).sst.transpose("member", "valid_date", "lat", "lon")
    o = xr.load_dataset(observed).sst.transpose("time", "lat", "lon")
    for a in [f, o]:
        if a.attrs.get("units") != "degree_Celsius":
            raise ValueError("Normalize and audit SST units first")
    if f.sizes["member"] != 101 or len(np.unique(f.member)) != 101:
        raise ValueError("Expected control plus 100 unique perturbed members")
    baseline_dates = np.concatenate([np.arange(f"{y}-09-24", f"{y}-10-09", dtype="datetime64[D]")
                                     for y in range(2013, 2023)])
    if len(np.unique(o.time)) != o.sizes["time"] or len(np.unique(f.valid_date)) != f.sizes["valid_date"]:
        raise ValueError("Duplicate timestamps")
    baseline = o.sel(time=baseline_dates).mean("time", skipna=False)
    cw, ce = box(baseline, True), box(baseline, False)
    out = {k: [] for k in ("valid_from", "valid_to", "forecast_dmi_c", "spread_dmi_c",
                            "observed_dmi_c", "error_dmi_c")}
    for start, end in windows:
        dates = np.arange(start, np.datetime64(end) + np.timedelta64(1, "D"), dtype="datetime64[D]")
        if len(dates) != 7:
            raise ValueError("Expected complete seven-day window")
        fm = f.sel(valid_date=dates).mean("valid_date", skipna=False)
        om = o.sel(time=dates).mean("time", skipna=False)
        members = (box(fm, True) - cw) - (box(fm, False) - ce)
        observed_index = float((box(om, True) - cw) - (box(om, False) - ce))
        out["valid_from"].append(start)
        out["valid_to"].append(end)
        out["forecast_dmi_c"].append(float(members.mean()))
        out["spread_dmi_c"].append(float(members.std(ddof=1)))
        out["observed_dmi_c"].append(observed_index)
        out["error_dmi_c"].append(float(members.mean()) - observed_index)
    out.update(units="degree_Celsius", figure="/work/outlook.png", source_url=sources)
    return out


def probabilities(samples, thresholds):
    lo = (samples < thresholds[0]).mean(axis=0)
    hi = (samples > thresholds[1]).mean(axis=0)
    return np.stack([lo, 1-lo-hi, hi])


def seasonal_scores(prediction, verification, training):
    p = prediction.probability.transpose("year", "tercile", "lat", "lon")
    estimate = prediction.rainfall_mm.transpose("year", "lat", "lon")
    y = verification.observed.transpose("year", "lat", "lon")
    f = verification.forecast.transpose("year", "member", "lat", "lon")
    h = training.forecast.transpose("year", "member", "lat", "lon")
    obs = training.observed.transpose("year", "lat", "lon")
    for coord in ("year", "lat", "lon"):
        if not np.array_equal(p[coord], y[coord]) or not np.array_equal(estimate[coord], y[coord]):
            raise ValueError(f"Prediction coverage/order mismatch: {coord}")
    if list(p.tercile.values) != ["below", "near", "above"]:
        raise ValueError("Wrong tercile order")
    for a in (p, estimate, y, f, h, obs):
        if not np.isfinite(a).all():
            raise ValueError("Nonfinite values; partial coverage cannot receive full scores")
    if (p.values < 0).any() or (p.values > 1).any() or not np.allclose(p.sum("tercile"), 1, atol=1e-6, rtol=0):
        raise ValueError("Invalid probabilities")
    if estimate.attrs.get("units") != "mm" or (estimate.values < 0).any():
        raise ValueError("Rainfall must be nonnegative mm")
    for a in (y, f, h, obs):
        if a.attrs.get("units") != "mm":
            raise ValueError("Reference rainfall must be in mm")
    thresholds = np.quantile(obs.values, [1/3, 2/3], axis=0, method="linear")
    category = np.where(y < thresholds[0], 0, np.where(y > thresholds[1], 2, 1))
    outcome = np.eye(3)[category].transpose(0, 3, 1, 2)
    model_thresholds = np.quantile(h.values.reshape(-1, *y.shape[1:]), [1/3, 2/3], axis=0)
    candidates = {"submitted": p.values,
                  "raw": np.stack([probabilities(v, thresholds) for v in f.values]),
                  "model_climate": np.stack([probabilities(v, model_thresholds) for v in f.values]),
                  "climatology": np.broadcast_to(probabilities(obs.values, thresholds), p.shape)}
    weights = np.cos(np.deg2rad(y.lat.values))[:, None] * np.ones((1, y.sizes["lon"]))
    weights /= weights.sum()
    per_year = {k: (((v.cumsum(1)[:, :2] - outcome.cumsum(1)[:, :2]) ** 2).sum(1) * weights).sum((1, 2))
                for k, v in candidates.items()}
    means = {k: float(v.mean()) for k, v in per_year.items()}
    skill = {k: 1 - means["submitted"]/v if v > 0 else None for k, v in means.items() if k != "submitted"}
    reliability = {}
    event = category == 2
    mass = np.broadcast_to(weights, event.shape)
    for name, pp in candidates.items():
        bins = np.minimum((pp[:, 2] * 5).astype(int), 4)
        rows = []
        for b in range(5):
            mask = bins == b
            if mask.any():
                rows.append(dict(bin=b, probability=float(np.average(pp[:, 2][mask], weights=mass[mask])),
                                 frequency=float(np.average(event[mask], weights=mass[mask])),
                                 cell_years=int(mask.sum()), years=int(mask.any((1, 2)).sum()),
                                 weight=float(mass[mask].sum()/mass.sum())))
        reliability[name] = {"bins": rows, "gap": sum(r["weight"]*abs(r["probability"]-r["frequency"]) for r in rows)}
    draws = np.random.default_rng(20261001).integers(0, len(y.year), (2000, len(y.year)))
    intervals = {}
    for k in skill:
        denominator = per_year[k][draws].mean(1)
        intervals[k] = np.quantile(1-per_year["submitted"][draws].mean(1)/denominator, [.025, .975]).tolist() if (denominator > 0).all() else None
    return {"RPS": means, "skill_vs": skill,
            "RMSE_mm": {"submitted": float(np.sqrt((((estimate.values-y.values)**2)*weights).sum((1, 2)).mean())),
                        "raw": float(np.sqrt((((f.mean("member").values-y.values)**2)*weights).sum((1, 2)).mean()))},
            "reliability": reliability, "paired_year_bootstrap_95pct": intervals,
            "years": len(y.year), "uncertainty_note": "Descriptive whole-year resampling; spatial cells are not independent years."}


def evaluate(name, submission, reference, replay=None, prediction_path=None):
    spec = task(name)
    submission, reference = Path(submission), Path(reference)
    inventory(submission)  # refuse symlinks before any reads
    manifest = read(reference / "reference.json")
    if manifest["task"] != name:
        raise ValueError("Wrong reference task")
    checks, metrics = [], {}
    def record(label, passed, detail="", mandatory=True):
        checks.append(dict(id=label, passed=bool(passed), detail=detail, mandatory=mandatory))
    answer = {}
    try:
        answer = json.loads((submission / "answer.json").read_text())
        record("answer_json", isinstance(answer, dict))
    except (OSError, ValueError):
        record("answer_json", False, "Missing or malformed answer.json")
    if not isinstance(answer, dict):
        answer = {}
    for filename in ("report.txt", "provenance.json", "handoff.txt", "solve.py"):
        p = submission / filename
        record("artifact:"+filename, p.is_file() and p.stat().st_size > 0)
    try:
        with Image.open(submission / "outlook.png") as img:
            img.verify()
        record("figure_readable", True, "Visual content assessed separately by judge")
    except (OSError, ValueError):
        record("figure_readable", False)
    source = answer.get("source_url", [])
    source = [source] if isinstance(source, str) else source
    record("source_coverage", isinstance(source, list) and all(s in source for s in manifest["sources"]),
           "Exact raw stores required; request details assessed in provenance.json")
    if name in ("iod", "kenya"):
        for key, expected in manifest["expected"].items():
            if key != "source_url":
                record("value:"+key, compare(answer.get(key), expected, **spec["numeric"]))
        if name == "iod" and all(c["passed"] for c in checks if c["id"].startswith("value:")):
            errors = np.array(answer["error_dmi_c"])
            metrics = {"forecast_error_C": errors.tolist(), "MAE_C": float(abs(errors).mean()),
                       "RMSE_C": float(np.sqrt((errors**2).mean())), "calibration": "not_estimable_from_two_windows"}
        elif name == "kenya":
            metrics = {"forecast_skill": "not_measured_without_observations", "calibration": "not_applicable"}
    else:
        try:
            actual = xr.load_dataset(submission / "training.nc")
            expected = xr.load_dataset(reference / "training.nc")
            # The contract requires these two fields; additional diagnostics and
            # auxiliary metadata are allowed and must not cause a false failure.
            fields = ['forecast', 'observed']
            xr.testing.assert_allclose(actual[fields].reset_coords(drop=True),
                                       expected[fields].reset_coords(drop=True),
                                       atol=1e-4, rtol=1e-6)
            record("training_aggregation", all(actual[v].attrs.get("units") == "mm" for v in ["forecast", "observed"]))
        except (OSError, ValueError, KeyError, AssertionError) as exc:
            record("training_aggregation", False, type(exc).__name__)
        try:
            metrics = seasonal_scores(xr.load_dataset(prediction_path or submission / "predictions.nc"),
                                      xr.load_dataset(reference / "verification.nc"),
                                      xr.load_dataset(reference / "training.nc"))
            record("prediction_validity_and_coverage", True)
        except (OSError, ValueError, KeyError, AssertionError) as exc:
            record("prediction_validity_and_coverage", False, str(exc)[:300])
        try:
            dev = xr.load_dataset(submission / "development.nc")
            expected = xr.load_dataset(reference / "training.nc")
            p = dev.probability.transpose('year', 'tercile', 'lat', 'lon')
            m = dev.rainfall_mm.transpose('year', 'lat', 'lon')
            valid = all(np.array_equal(p[c], expected[c]) and np.array_equal(m[c], expected[c]) for c in ('year','lat','lon'))
            valid &= list(p.tercile.values) == ['below','near','above']
            valid &= bool(np.isfinite(p).all() and np.isfinite(m).all() and (m >= 0).all())
            valid &= bool((p >= 0).all() and (p <= 1).all() and np.allclose(p.sum('tercile'), 1, atol=1e-6, rtol=0))
            valid &= m.attrs.get('units') == 'mm'
            record('development_predictions', valid, 'LOYO method assessed from code by judge; schema/coverage checked numerically')
        except (OSError, ValueError, KeyError):
            record('development_predictions', False)
        record("prediction_entrypoint", (submission / "predict.py").is_file())
    record("independent_replay", replay is not None and replay.get("passed") is True,
           "Missing replay is unresolved, never a pass" if replay is None else replay.get("detail", ""))
    passed = sum(c["passed"] for c in checks)
    return {"task": name, "reference_status": manifest.get("status", "unreviewed"), "checks": checks,
            "all_mandatory_pass": all(c["passed"] for c in checks if c["mandatory"]),
            "passed_checks": passed, "total_checks": len(checks), "metrics": metrics,
            "completion": "pending_judge", "integrity": "requires_run_manifest_and_audit"}
