"""Task-specific static scientific checks, independent of shared aggregation."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr


def comparison(actual, expected, names):
    details = []
    for name in names:
        if name not in actual:
            return False, f"Missing variable {name}"
        a, b = actual[name], expected[name]
        if a.dims != b.dims or any(d not in a.coords or not np.array_equal(a[d], b[d]) for d in b.dims):
            return False, f"{name}: dimensions/coordinate values or order differ"
        if not np.isfinite(a.values).all():
            return False, f"{name}: nonfinite values on complete-support target"
        if name in ("seasonal_total", "threshold") and a.attrs.get("units") != "mm":
            return False, f"{name}: units must be mm"
        delta = float(np.max(np.abs(a.values - b.values)))
        atol = 1e-5 if name in ("seasonal_total", "threshold") else 2e-7
        passed = np.array_equal(a.values, b.values) if name == "selected_candidate" else np.allclose(a.values, b.values, rtol=1e-7, atol=atol)
        details.append(f"{name}: maximum absolute error {delta:.6g}, absolute tolerance {atol:g}")
        if not passed:
            return False, "; ".join(details)
    return True, "; ".join(details)


def submission_checks(submission, private):
    """Return named check records; private may be task root or controller."""
    submission, private = Path(submission), Path(private)
    controller = private / "controller" if (private / "controller").is_dir() else private
    checks = {}
    groups = {
        "seasonal_totals": ("seasonal.nc", ["seasonal_total"]),
        "hindcast_probabilities": ("hindcasts.nc", ["probability"]),
        "inner_selection": ("hindcasts.nc", ["selected_candidate", "inner_rps"]),
        "production_probabilities": ("forecast.nc", ["probability", "selected_candidate", "inner_rps"]),
        "thresholds": ("hindcasts.nc", ["threshold"]),
        "verification_arithmetic": ("hindcasts.nc", ["rps", "rpss"]),
    }
    for name, (file, fields) in groups.items():
        try:
            with xr.open_dataset(submission / file) as a, xr.open_dataset(controller / file) as b:
                checks[name] = comparison(a, b, fields)
            if name == "thresholds":
                with xr.open_dataset(submission / "forecast.nc") as a, xr.open_dataset(controller / "forecast.nc") as b:
                    p, detail = comparison(a, b, ["threshold"])
                checks[name] = (checks[name][0] and p, checks[name][1] + "; " + detail)
        except (OSError, ValueError, KeyError, TypeError) as e:
            checks[name] = (False, str(e))
    checks["units_and_coordinates"] = (checks["seasonal_totals"][0] and checks["hindcast_probabilities"][0] and checks["production_probabilities"][0] and checks["thresholds"][0], "Scientific checks enforce fixed dimensions, order, finite support and mm target/threshold units")
    try:
        answer = json.loads((submission / "answer.json").read_text())
        fields = ("task", "training_years", "verification_years", "prediction_years", "region_order", "system_order", "rainfall_units", "rainfall_recovery_factor", "issue_time", "observed_sst_cutoff", "metrics", "forecast_skill_claim", "limitations")
        valid = all(k in answer for k in fields)
        checks["answer_schema"] = (valid, "Required scientific answer fields present" if valid else "Missing required scientific answer fields")
        with xr.open_dataset(controller / "hindcasts.nc") as gold:
            agree = True
            for region in gold.region.values:
                for system in gold.system.values:
                    recorded = answer["metrics"][str(region)][str(system)]
                    rp = float(gold.rps.sel(region=region, system=system).mean())
                    skill = float(gold.rpss.sel(region=region, system=system))
                    agree &= bool(np.isclose(recorded["mean_rps"], rp, atol=2e-7, rtol=1e-7) and np.isclose(recorded["rpss"], skill, atol=2e-7, rtol=1e-7))
        # The prompt specifies the period but not endpoint-vs-enumerated JSON
        # notation. Both accurately describe the prescribed training record.
        def period(value,start,end):
            return (isinstance(value,list) and all(type(y) is int for y in value)
                    and value in ([start,end],list(range(start,end+1))))
        contract = (answer["task"] == "short-rains-workflow" and period(answer['training_years'],1993,2019)
                    and period(answer['verification_years'],2005,2019) and period(answer['prediction_years'],2020,2023)
                    and answer["region_order"] == ["somalia", "kenya", "eastern-horn"]
                    and answer["system_order"] == ["climatology", "antecedent-iod", "forecast-iod", "nested-search"]
                    and answer["rainfall_units"] == "mm" and answer["rainfall_recovery_factor"] == 30)
        checks["answer_schema"] = (valid and contract, "Required answer fields and declared experiment boundaries checked")
        passed, detail = checks["verification_arithmetic"]
        checks["verification_arithmetic"] = (passed and agree, detail + "; per-region/system answer metrics checked")
    except (OSError, ValueError, KeyError, TypeError) as e:
        checks["answer_schema"] = (False, str(e))
        passed, detail = checks["verification_arithmetic"]
        checks["verification_arithmetic"] = (False, detail + "; " + str(e))
    return {name:{"state":"pass" if passed else "fail", "detail":detail,
                  "evidence":["independent short-rains controller reference"]}
            for name,(passed,detail) in checks.items()}
