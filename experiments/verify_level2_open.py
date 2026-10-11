"""Read-only independent verification of the two completed Level 2 attempts.

Run only after the parent reserves one scientific worker. Never execute actor
code, score an intermediate final-period candidate, or change a comparator.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys

# Set these before importing any scientific library, in a fresh interpreter.
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PLAN = ROOT / "experiments/level2-open-plan-2026-10-08.json"
OUTPUT = ROOT / "experiments/level2-open-numeric-verification-2026-10-08.json"
REVIEW = ROOT / "var/review/level2-open-20261008"


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def frozen_store_hash(source):
    """Reproduce feedback.freeze_store's traversal digest without copying."""
    source = Path(source)
    assert source.is_dir() and not source.is_symlink()
    result, total, count = hashlib.sha256(), 0, 0
    pending = [source]
    while pending:
        for entry in sorted(os.scandir(pending.pop()), key=lambda value: value.name):
            assert not entry.is_symlink(), entry.path
            if entry.is_dir(follow_symlinks=False):
                pending.append(Path(entry.path))
            else:
                assert stat.S_ISREG(entry.stat(follow_symlinks=False).st_mode), entry.path
                data = Path(entry.path).read_bytes()
                total += len(data)
                count += 1
                result.update(str(Path(entry.path).relative_to(source)).encode() + b"\0" + hashlib.sha256(data).digest())
    assert count
    return {"sha256": result.hexdigest(), "bytes": total, "files": count}


def metric_comparison(independent, recorded):
    """Score arithmetic agreement, separate from whether a forecast is valid."""
    rows = {}
    for key, expected in independent.items():
        actual = recorded.get(key)
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            ok = isinstance(actual, (int, float)) and math.isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-9)
            rows[key] = {"independent": expected, "recorded": actual, "agrees": ok,
                         "absolute_gap": abs(expected-actual) if isinstance(actual, (int, float)) else None}
        elif key in recorded:
            rows[key] = {"independent": expected, "recorded": actual, "agrees": actual == expected}
    return {"agrees": all(row["agrees"] for row in rows.values()), "metrics": rows}


def read_aligned(spec, store, frame):
    from assessment.compare import align, read_results
    results, problems = read_results(spec, None, store=store)
    if problems:
        raise ValueError(str(problems))
    return align(spec, results, frame)


def final_truth_and_baselines(task, params, frame):
    """Independent scalar-date split and fixed training-only harmonic baseline."""
    import netCDF4
    import numpy as np
    def dates(variable):
        unit, _, origin = variable.units.partition(" since ")
        base = date.fromisoformat(origin.strip()[:10])
        step = {"days": 1., "hours": 1/24, "seconds": 1/86400}[unit.strip()]
        return [base + timedelta(days=round(float(value)*step)) for value in variable[:]]
    def design(day):
        angle = 2*math.pi*(day.timetuple().tm_yday+14)/365.25
        return [1., math.sin(angle), math.cos(angle), math.sin(2*angle), math.cos(2*angle)]
    with netCDF4.Dataset(task.private / "source-subset.nc") as source:
        issues, starts = dates(source["issue_time"]), dates(source["target_start"])
        locations = np.asarray(source["location"][:])
        latitudes = np.asarray(source["latitude"][:], dtype="float64")
        longitudes = np.asarray(source["longitude"][:], dtype="float64")
        observed = np.asarray(source["precipitation"][:], dtype="float64")
        raw = np.asarray(source["raw_cfsv2"][:], dtype="float64")
    cells = [i for i, lon in enumerate(longitudes) if params["longitude_limit"] is None or lon <= params["longitude_limit"]]
    first, second, third = [date.fromisoformat(params[name]) for name in ("training_boundary", "development_boundary", "final_boundary")]
    train = [i for i, day in enumerate(starts) if day+timedelta(days=14) < first]
    rows = [i for i, day in enumerate(issues) if second <= day < third]
    assert np.array_equal(locations[cells], frame["location"])
    assert [issues[i].isoformat() for i in rows] == list(frame["final_issue"])
    matrix = np.array([design(issues[i]) for i in train])
    seasonal = np.empty((len(rows), len(cells)), dtype="float64")
    for column, cell in enumerate(cells):
        beta = np.linalg.solve(matrix.T @ matrix, matrix.T @ observed[train, cell])
        seasonal[:, column] = [max(float(np.dot(design(issues[i]), beta)), 0.) for i in rows]
    return {"truth": observed[np.ix_(rows, cells)], "raw_model": raw[np.ix_(rows, cells)],
            "climatology": seasonal, "latitude": latitudes[cells], "years": [issues[i].year for i in rows]}


def yearwise(prediction, source):
    import numpy as np
    weights = np.cos(np.deg2rad(source["latitude"]))
    errors = (np.asarray(prediction, dtype="float64")-source["truth"])**2
    output = {}
    for year in sorted(set(source["years"])):
        mask = np.array([value == year for value in source["years"]])
        mse = float(np.sum(errors[mask]*weights[None, :])/(int(mask.sum())*float(weights.sum())))
        output[str(year)] = {"rmse_mm": math.sqrt(mse), "mse_mm_squared": mse,
                             "issues": int(mask.sum()), "cells": len(weights)}
    mse = float(np.sum(errors*weights[None, :])/(len(errors)*float(weights.sum())))
    return {"pooled_rmse_mm": math.sqrt(mse), "years": output}


def verify_run(task, params, system, invocation):
    import numpy as np
    from assessment.storage import digest, inventory, read
    folder = ROOT / invocation["result"]["directory"]
    meta, assessment = read(folder/"run.json"), read(folder/"assessment.json")
    assert meta["system"] == system
    assert meta["fingerprint"] == assessment["fingerprint"] == task.fingerprint()
    original = {child: inventory(folder/child) for child in ("frozen", "inputs", "controller/development-feedback")}
    assert original["frozen"] == read(folder/"artifacts.json")
    assert original["inputs"] == read(folder/"input-manifest.json")
    frame = task.hooks.expected_coordinates(folder/"inputs", params)
    spec = task.spec["results"]
    result = {"run": meta["id"], "system": system, "status": meta["status"],
              "original_computed_outcome": assessment["computed_outcome"],
              "original_outcome": assessment["outcome"], "original_verdict_preserved": True,
              "assessment_sha256": digest(folder/"assessment.json"), "frozen_inventory_sha256": canonical_sha(original["frozen"])}
    try:
        arrays = read_aligned(spec, folder/"frozen/results.zarr", frame)
    except ValueError as error:
        result.update(final_artifacts_usable=False, artifact_error=str(error), independent_scores=None)
        arrays = None
    else:
        result["final_artifacts_usable"] = True
        result["independent_scores"] = {}
        for split in ("development", "final"):
            independent = task.hooks.independent_score(arrays, params, task.private, split)
            result["independent_scores"][split] = metric_comparison(independent, (assessment.get("skill") or {}).get(split, {}))
    feedback = folder/"controller/development-feedback"
    ledger, public = read(feedback/"ledger.json"), read(folder/"controller/feedback-public.json")
    assert ledger["scope"] == public["scope"] == "development_only"
    assert not ledger["final_score_exposed"] and not ledger["final_observations_exposed"]
    assert len(ledger["attempts"]) <= ledger["max_submissions"] == 5
    public_fields = ("query", "prediction_file", "status", "prediction_sha256", "bytes", "metrics", "seconds", "error_type")
    assert public["requests"] == [{key: row[key] for key in public_fields if key in row} for row in ledger["attempts"]]
    queries, matching = [], []
    devspec = {name: row for name, row in spec.items() if not name.startswith("final")}
    devframe = {name: value for name, value in frame.items() if name in devspec}
    for row in ledger["attempts"]:
        item = {"query": row["query"], "status": row["status"], "prediction_file": row["prediction_file"]}
        if "snapshot" in row:
            snapshot = feedback/row["snapshot"]
            assert snapshot.parent == feedback and snapshot.name == f'prediction-{row["query"]:03d}.zarr'
            manifest = inventory(snapshot)
            hashed = frozen_store_hash(snapshot)
            assert hashed["sha256"] == row["prediction_sha256"] and hashed["bytes"] == row["bytes"]
            item.update(snapshot=row["snapshot"], **hashed, inventory=manifest, inventory_sha256=canonical_sha(manifest))
            if row["status"] == "scored":
                # Deliberately read and score development keys only, even when
                # a frozen query also happened to contain final arrays.
                candidate = read_aligned(devspec, snapshot, devframe)
                independent = task.hooks.independent_score(candidate, params, task.private, "development")
                # The public feedback deliberately omits issue/cell counts and
                # the historical-source caveat; verify its six-field contract.
                feedback_keys = ("split", "rmse_mm", "raw_model_rmse_mm", "climatology_rmse_mm",
                                 "skill_vs_raw_model", "skill_vs_climatology")
                assert set(row["metrics"]) == set(feedback_keys)
                item["independent_development_score"] = metric_comparison(
                    {key: independent[key] for key in feedback_keys}, row["metrics"])
                if arrays is not None:
                    gap = float(np.max(np.abs(candidate["development_mm"]-arrays["development_mm"])))
                    exact = bool(np.array_equal(candidate["development_mm"], arrays["development_mm"]))
                    bound = spec["development_mm"]["tolerance"]["atol"]
                    item["final_submitted_development_match"] = {"exact": exact, "maximum_absolute_gap_mm": gap,
                                                                 "within_rerun_tolerance": gap <= bound, "tolerance_mm": bound}
                    if exact:
                        matching.append(row["query"])
        queries.append(item)
    result["development_feedback"] = {"ledger_sha256": digest(feedback/"ledger.json"),
        "public_summary_sha256": digest(folder/"controller/feedback-public.json"), "requests": queries,
        "max_submissions": ledger["max_submissions"], "limit_denials": ledger["limit_denials"],
        "exact_matching_final_development_queries": matching,
        "selection_evidence": "Final submitted development values match these frozen queries; this does not infer selection intent.",
        "no_intermediate_final_scores_computed": True}
    if arrays is not None:
        source = final_truth_and_baselines(task, params, frame)
        result["final_yearwise"] = yearwise(arrays["final_mm"], source)
        assert math.isclose(result["final_yearwise"]["pooled_rmse_mm"], result["independent_scores"]["final"]["metrics"]["rmse_mm"]["independent"], abs_tol=1e-9)
    assert original == {child: inventory(folder/child) for child in original}
    result["original_artifacts_unchanged"] = True
    return result, frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--science-slot-released", action="store_true", help="Parent has explicitly released one scientific slot")
    args = parser.parse_args()
    if not args.science_slot_released:
        parser.error("Wait for the parent's explicit scientific slot release")
    from assessment.spec import Template
    from assessment.storage import digest, inventory, read, write
    plan = read(PLAN)
    invocations = {system: read(REVIEW/system/"invocation.json") for system in plan["systems"]}
    assert all(row["status"] == "finished" for row in invocations.values()), "Both attempts must finish before verification"
    assert not OUTPUT.exists(), "Do not overwrite verification evidence"
    manifest = ROOT/plan["contract_manifest"]
    assert digest(manifest) == plan["contract_manifest_sha256"]
    for relative, expected in read(manifest).items():
        assert digest(ROOT/relative) == expected, relative
    task = Template(plan["template"])
    assert task.fingerprint() == plan["fingerprint"]
    params = task.instance(plan["instance"])
    sources = read(task.folder/"sources.json")["files"]
    assert digest(task.private/"source-subset.nc") == sources["source-subset.nc"]["sha256"]
    rows, frame = [], None
    # Serial loop: scientific data is never opened by a thread.
    for system, invocation in invocations.items():
        if invocation.get("exit_code") != 0:
            rows.append({"system": system, "invocation_exit_code": invocation.get("exit_code"),
                         "numeric_verification": "unavailable: assigned invocation did not complete"})
            continue
        row, frame = verify_run(task, params, system, invocation)
        rows.append(row)
    preflight_path = ROOT/plan["preflight_evidence"][0]["path"]
    assert digest(preflight_path) == plan["preflight_evidence"][0]["sha256"]
    preflight = read(preflight_path)
    control_folder = ROOT/preflight["evidence"]["folder"]
    assert inventory(control_folder/"frozen") == preflight["evidence"]["frozen_manifest"]
    assert digest(ROOT/preflight["assessment"]["path"]) == preflight["assessment"]["sha256"]
    if frame is None:
        frame = task.hooks.expected_coordinates(control_folder/"inputs", params)
    control = read_aligned(task.spec["results"], control_folder/"frozen/results.zarr", frame)
    control_scores = {split: metric_comparison(task.hooks.independent_score(control, params, task.private, split),
        preflight["assessment"]["skill"][split]) for split in ("development", "final")}
    source = final_truth_and_baselines(task, params, frame)
    fixed = {name: yearwise(prediction, source) for name, prediction in (("raw_model", source["raw_model"]),
        ("seasonal_climatology", source["climatology"]), ("trusted_correct_control", control["final_mm"]))}
    checks = [value["agrees"] for value in control_scores.values()]
    for row in rows:
        checks.extend(value["agrees"] for value in (row.get("independent_scores") or {}).values())
        checks.extend(item["independent_development_score"]["agrees"] for item in row.get("development_feedback", {}).get("requests", []) if "independent_development_score" in item)
    output = {"schema_version": 1, "verified_at": datetime.now(timezone.utc).isoformat(),
        "state": "pass" if all(checks) else "fail", "plan_sha256": digest(PLAN), "script_sha256": digest(Path(__file__)),
        "template": task.name, "fingerprint": task.fingerprint(), "instance": params,
        "private_source_sha256": digest(task.private/"source-subset.nc"), "runs": rows,
        "fixed_comparators": fixed, "trusted_control_independent_scores": control_scores,
        "fixed_control_assessment_sha256": preflight["assessment"]["sha256"],
        "scientific_workers": 1, "thread_environment": {name: os.environ[name] for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
        "model_calls": 0, "actor_code_executed": False, "intermediate_final_candidates_scored": False,
        "comparators_retuned": False, "original_assessments_modified": False,
        "interpretation": "Independent arithmetic and frozen-query consistency verification, not a new grading verdict. Annual errors are descriptive: overlapping periods and neighbouring cells are dependent; this is an already-inspected public historical split."}
    write(OUTPUT, output)
    print(json.dumps({"state": output["state"], "path": str(OUTPUT.relative_to(ROOT)), "runs": [row.get("run", row["system"]) for row in rows]}))
    return 0 if output["state"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
