"""Freeze a causal observation-release study from the existing real CPC/CFSv2 source.

Publication dates are simulated, not reconstructed operational vintages. The
private fixture is controller-only; public research data contains no final truth
or future final-period predictors. Scientific decoding is single-process.
"""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys

for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "var/private/experiments/sequential-forecast-20261008"
PUBLIC = ROOT / "var/review/sequential-forecast-data-20261008/public"
EVIDENCE = ROOT / "experiments/sequential-forecast-data-2026-10-08.json"


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False)+"\n")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def score_predictions(episode, predictions):
    """Independent scalar area-weighted metric; never execute a forecast program."""
    if not isinstance(episode, dict):
        episode = json.loads(Path(episode).read_text())
    if isinstance(predictions, list):
        assert len({row["case_id"] for row in predictions}) == len(predictions), "Duplicate cases"
        predictions = {row["case_id"]: row["prediction_mm"] for row in predictions}
    assert set(predictions) == {row["case_id"] for row in episode["cases"]}, "Exact case coverage required"
    weights = [math.cos(math.radians(row["latitude"])) for row in episode["locations"]]
    # Fixed monthly climatology fitted once to only the episode's initial
    # released history. It never consumes streamed updates or final outcomes.
    monthly = {}
    for row in episode["training"]:
        monthly.setdefault(row["target_start"][5:7], []).append(row["observed_mm"])
    climate = {month: [math.fsum(row[j] for row in rows)/len(rows) for j in range(len(weights))]
               for month, rows in monthly.items()}
    assert len(climate) == 12
    squared, raw_squared, climo_squared = [], [], []
    annual = {}
    for case in episode["cases"]:
        values = predictions[case["case_id"]]
        assert len(values) == len(weights) and all(math.isfinite(value) and value >= 0 for value in values)
        errors = [weight*(prediction-truth)**2 for weight, prediction, truth in zip(weights, values, case["observed_mm"])]
        raw = [weight*(prediction-truth)**2 for weight, prediction, truth in zip(weights, case["raw_mm"], case["observed_mm"])]
        squared.extend(errors)
        raw_squared.extend(raw)
        climo_squared.extend(weight*(prediction-truth)**2 for weight, prediction, truth in
                             zip(weights, climate[case["target_start"][5:7]], case["observed_mm"]))
        bucket = annual.setdefault(case["issue_time"][:4], {"squared": [], "raw_squared": [], "issues": 0})
        bucket["squared"].extend(errors)
        bucket["raw_squared"].extend(raw)
        bucket["issues"] += 1
    denominator = len(episode["cases"])*math.fsum(weights)
    rmse, raw, climo = [math.sqrt(math.fsum(values)/denominator) for values in (squared, raw_squared, climo_squared)]
    return {"rmse_mm": rmse, "raw_model_rmse_mm": raw, "climatology_rmse_mm": climo,
            "skill_vs_raw_model": 1-rmse/raw, "skill_vs_climatology": 1-rmse/climo,
            "issues": len(episode["cases"]), "cells": len(weights),
            "yearwise": {year: {"rmse_mm": math.sqrt(math.fsum(row["squared"])/(row["issues"]*math.fsum(weights))),
                                 "raw_model_rmse_mm": math.sqrt(math.fsum(row["raw_squared"])/(row["issues"]*math.fsum(weights))),
                                 "issues": row["issues"]} for year, row in sorted(annual.items())}}


def build():
    import netCDF4
    import numpy as np
    assert not PRIVATE.exists() and not PUBLIC.exists() and not EVIDENCE.exists(), "Never overwrite frozen study evidence"
    source = ROOT / "var/private/templates/weeks34-rainfall/source-subset.nc"
    provenance = json.loads((ROOT / "templates/weeks34-rainfall/sources.json").read_text())
    assert digest(source) == provenance["files"]["source-subset.nc"]["sha256"]
    with netCDF4.Dataset(source) as ds:
        def dates(name):
            variable = ds[name]
            decoded = netCDF4.num2date(variable[:], variable.units, only_use_cftime_datetimes=False)
            return [date(v.year, v.month, v.day) for v in decoded]
        issues, targets = dates("issue_time"), dates("target_start")
        raw, obs = (np.asarray(ds[name][:], dtype="float64") for name in ("raw_cfsv2", "precipitation"))
        locations = [{"id": int(loc), "latitude": float(lat), "longitude": float(lon)}
                     for loc, lat, lon in zip(ds["location"][:], ds["latitude"][:], ds["longitude"][:])]
    assert np.isfinite(raw).all() and np.isfinite(obs).all() and raw.shape == obs.shape
    assert all(target == issue+timedelta(days=14) for issue, target in zip(issues, targets))
    records = []
    for index, (issue, target) in enumerate(zip(issues, targets)):
        release = target+timedelta(days=14+7)
        assert release == issue+timedelta(days=35)
        records.append({"case_id": issue.isoformat(), "issue_time": issue.isoformat(),
                        "target_start": target.isoformat(), "target_end_exclusive": (target+timedelta(days=14)).isoformat(),
                        "release_time": release.isoformat(), "raw_mm": raw[index].tolist(), "observed_mm": obs[index].tolist()})
    train_cutoff, final_cutoff, final_end = "2012-01-01", "2015-01-01", "2022-01-01"
    training = [row for row in records if row["release_time"] <= train_cutoff]
    def make_stream(first, last):
        cases = [row for row in records if first <= row["issue_time"] < last]
        assert cases
        # Seed records released by the first prediction, including bridge cases.
        initial = [row for row in records if row["release_time"] <= cases[0]["issue_time"]]
        pending = [row for row in records if row["issue_time"] < cases[0]["issue_time"] < row["release_time"]]
        return {"locations": locations, "training": initial, "pending": pending, "cases": cases}
    streams = {"development": make_stream(train_cutoff, final_cutoff), "final": make_stream(final_cutoff, final_end)}
    metadata = {"schema_version": 1, "task_set_row": 23, "units": "mm per14-day window", "locations": locations,
        "training_release_cutoff": train_cutoff, "research_development_release_cutoff": final_cutoff,
        "publication_lag_days": 7, "release_rule": "target_end_exclusive+7days = issue_time+35days; observation available when release_time<=current issue_time",
        "source_sha256": digest(source), "source_provenance": provenance["origin"],
        "caveats": ["Retrospective source snapshot; release dates are an explicit simulation, not historical real-time vintages.",
                    "Final observations are public history but private to the frozen program during the stream.",
                    "Weekly14-day targets overlap; nine nearby cells and annual errors are dependent.",
                    "Late2014 labels released after2015-01-01 are excluded from public research and released causally during final stream."]}
    metadata["caveats"][3] = "All development labels stay controller-private; five aggregate development evaluations may guide program selection."
    metadata["split_metadata"] = {name: {"first_issue": stream["cases"][0]["issue_time"],
        "last_issue": stream["cases"][-1]["issue_time"], "cases": len(stream["cases"])} for name, stream in streams.items()}
    public = {"locations": locations, "training": training}
    write(PUBLIC / "training.json", public)
    write(PUBLIC / "metadata.json", metadata)
    for name, episode in streams.items():
        write(PRIVATE / (name+".json"), episode)
    write(PRIVATE / "study.json", metadata)
    evidence = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "state": "pass",
        "source": str(source.relative_to(ROOT)), "source_sha256": digest(source),
        "private_episodes": {name: {"path": str((PRIVATE/(name+".json")).relative_to(ROOT)),
            "sha256": digest(PRIVATE/(name+".json"))} for name in streams},
        "public_training": str((PUBLIC/"training.json").relative_to(ROOT)), "public_training_sha256": digest(PUBLIC/"training.json"),
        "public_metadata": str((PUBLIC/"metadata.json").relative_to(ROOT)), "public_metadata_sha256": digest(PUBLIC/"metadata.json"),
        "training_cases": len(training),
        "streams": {name: {**metadata["split_metadata"][name], "initial_available_observations": len(row["training"]),
                            "initial_pending_observations": len(row["pending"])} for name, row in streams.items()},
        "native_workers": 1, "development_truth_in_public_training": False,
        "final_truth_in_public_training": False, "future_final_predictors_in_public_training": False,
        "actor_code_executed": False, "model_calls": 0, "publication_dates_simulated": True,
        "script_sha256": digest(Path(__file__)), "caveats": metadata["caveats"]}
    write(EVIDENCE, evidence)
    print(json.dumps(evidence, indent=2))
    return evidence


if __name__ == "__main__":
    build()
