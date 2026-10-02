"""Static submission checks. Human and execution leaves remain unresolved."""
import json
import re
from pathlib import Path

import numpy as np
import yaml

from weatherbench.storage import inventory
from .prepare import ROOT, PACKAGES, PRIVATE, TASKS, digest
from .references import load, same_array, TERCILES
from .contracts import provenance, execution


def leaves(node, mass=1.):
    if "children" not in node:
        yield node, mass
        return
    total = sum(child["weight"] for child in node["children"])
    for child in node["children"]:
        yield from leaves(child, mass * child["weight"] / total)


def validate_packages(metadata_only=False):
    reports = []
    for task in TASKS:
        root = PACKAGES / task
        spec = yaml.safe_load((root / "task.yaml").read_text())
        rubric = yaml.safe_load((root / "rubric.yaml").read_text())
        manifest = json.loads((root / "input-manifest.json").read_text())
        assert spec["id"] == task == manifest["task"]
        assert spec["version"] == rubric["task_version"]
        assert not spec["review"]["launch_enabled"]
        assert "successor" not in spec and "phases" not in spec
        for name in ("prompt", "source_record", "rubric", "review_sheet"):
            assert (root / spec[name]).is_file()
        leaf_rows = list(leaves(rubric["tree"]))
        ids = [leaf["id"] for leaf, _ in leaf_rows]
        assert len(ids) == len(set(ids))
        all_ids = set()
        def validate_node(node):
            assert node["id"] not in all_ids
            all_ids.add(node["id"])
            for child in node.get("children", []):
                assert child["weight"] > 0
                validate_node(child)
        validate_node(rubric["tree"])
        assert abs(sum(weight for _, weight in leaf_rows) - 1) < 1e-12
        assert all(leaf["required"] and leaf["evaluator"] in ("deterministic", "expert", "execution", "mixed")
                   and leaf["criterion"] and leaf["evidence"] for leaf, _ in leaf_rows)
        assert all(weight > 0 for _, weight in leaf_rows)
        assert all(leaf.get("checks") for leaf, _ in leaf_rows if leaf["evaluator"] == "deterministic")
        assert not rubric["basic_validity"]["weighted"]
        assert rubric["basic_validity"]["integrity"]
        for filename in spec["artifact_contracts"].values():
            assert (root / filename).is_file()
        for row in manifest["files"]:
            path = PRIVATE / task / row["file"]
            if not metadata_only:
                if not path.is_file():
                    raise ValueError("Internal task data bundle missing: " + str(path) +
                                     ". See docs/internal-setup.md; use tasks validate --metadata-only to inspect packages without data.")
                assert path.stat().st_size == row["bytes"] and digest(path) == row["sha256"]
            assert row["visibility"] == ("agent" if row["file"].startswith("agent-inputs/") else "controller_only")
        assert digest(Path(__file__).with_name("references.py")) == manifest["reference_code_sha256"]
        for row in manifest["source_records"]:
            source = ROOT / row["path"]
            if Path(row["path"]).is_absolute() or ".." in Path(row["path"]).parts or not source.resolve().is_relative_to(ROOT.resolve()):
                raise ValueError("Source records must stay inside this repository")
            assert digest(source) == row["sha256"]
        if task == "seasonal-calibration":
            plan = json.loads((root / spec["source_plan"]).read_text())
            assert spec["input_contract"]["mode"] == "agent_acquisition"
            assert spec["input_contract"]["normalized_fixture_mount"] is False
            assert plan["forecast"]["request"]["year"] == list(map(str, range(1993, 2005)))
            assert len(plan["observations"]["urls"]) == 36
            assert all(re.search(r"\.20(?:05|06)\.", url) is None for url in plan["sources"])
            if not metadata_only:
                assert set(load(PRIVATE / task / "agent-inputs/forecast-development.nc").init_time.dt.year.values) == set(range(1993, 2005))
                assert set(load(PRIVATE / task / "agent-inputs/observations-development.nc").time.dt.year.values) == set(range(1993, 2005))
                assert load(PRIVATE / task / "controller/forecast.nc").data_vars.keys() == {"forecast"}
        reports.append({"task": task, "files_verified": 0 if metadata_only else len(manifest["files"]), "rubric_leaves": len(ids),
                        "private_data_validation": "not_checked" if metadata_only else "passed",
                        "task_sha256": digest(root / "task.yaml"), "prompt_sha256": digest(root / "prompt.md"),
                        "rubric_sha256": digest(root / "rubric.yaml"),
                        "input_mode": spec["input_contract"]["mode"],
                        "acquisition_runtime_validated": False if task == "seasonal-calibration" else None,
                        "expert_approval": False, "launch_enabled": False,
                        "reference_validation": manifest["reference_validation"]})
    return {"validation": "metadata_passed" if metadata_only else "passed", "packages": reports, "agent_attempts": 0, "model_calls": 0}


def check(task, submission):
    if task not in TASKS:
        raise ValueError("Unknown review package")
    submission = Path(submission)
    if not submission.is_dir():
        raise ValueError("Submission must be a directory")
    inventory(submission)  # submissions are data, not commands; refuse symlinks
    root, private = PACKAGES / task, PRIVATE / task
    spec = yaml.safe_load((root / "task.yaml").read_text())
    rubric = yaml.safe_load((root / "rubric.yaml").read_text())
    results = {}

    def record(name, passed, evidence, detail=""):
        results[name] = {"state": "pass" if bool(passed) else "fail", "evidence": evidence, "detail": detail}

    def array(name, filename, fields):
        try:
            actual, expected = load(submission / filename), load(private / "controller" / filename)
            ok = all(same_array(actual[v], expected[v])
                     and actual[v].attrs.get("units") == expected[v].attrs.get("units") for v in fields)
            record(name, ok, [filename, "controller-reference"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            record(name, False, [filename], f"{type(exc).__name__}: {str(exc)[:150]}")

    record("delivery", all((submission / name).is_file() and (submission / name).stat().st_size > 0
                            for name in spec["outputs"]), ["submission-inventory"])
    try:
        execution(submission, needs_prediction=task == "seasonal-calibration")
        record("execution_schema", True, ["execution.json", "retained-inventory"])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        record("execution_schema", False, ["execution.json"], str(exc)[:150])
    try:
        source_record = provenance(submission)
        record("provenance_fields", True, ["provenance.json", "retained-inventory"])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        source_record = {}
        record("provenance_fields", False, ["provenance.json"], str(exc)[:150])
    if task == "seasonal-calibration":
        needed = json.loads((root / spec["source_plan"]).read_text())["sources"]
    else:
        needed = json.loads((private / "agent-inputs/source-manifest.json").read_text())["sources"]
    declared = {s["id"] for s in source_record.get("sources", [])}
    record("source_coverage", set(needed).issubset(declared), ["provenance.json", "source-plan-or-manifest"])
    try:
        answer = json.loads((submission / "answer.json").read_text())
        if not isinstance(answer, dict):
            raise ValueError("answer.json must be an object")
    except (OSError, ValueError, TypeError) as exc:
        answer = {}

    if task == "seasonal-calibration":
        array("aggregation", "training.nc", ["forecast", "observed"])
        record("answer_schema", all(answer.get(k) for k in ("method", "limitations"))
               and isinstance(answer.get("development_validation"), dict), ["answer.json"])
        try:
            d, expected = load(submission / "development.nc"), load(private / "controller/training.nc")
            p = d.probability.transpose("year", "tercile", "lat", "lon")
            m = d.rainfall_mm.transpose("year", "lat", "lon")
            valid = all(np.array_equal(p[c], expected[c]) and np.array_equal(m[c], expected[c]) for c in ("year", "lat", "lon"))
            valid &= list(p.tercile.values) == TERCILES
            valid &= bool(np.isfinite(p).all() and np.isfinite(m).all() and (m >= 0).all()
                          and (p >= 0).all() and (p <= 1).all())
            valid &= bool(np.allclose(p.sum("tercile"), 1, atol=1e-6, rtol=0))
            valid &= m.attrs.get("units") == "mm"
            record("development_schema", valid, ["development.nc"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            record("development_schema", False, ["development.nc"], str(exc)[:150])
    elif task == "acmad-objective":
        for key, fields in {"objective": ["probability"], "support": ["available_components"],
                            "sensitivity": ["nominal_weighted_probability"], "disagreement": ["disagreement_pp"]}.items():
            array(key, "objective.nc", fields)
        expected = load(private / "controller/objective.nc")
        values = {"supported_cells": int((expected.available_components > 0).sum()),
                  "fully_supported_cells": int((expected.available_components == 3).sum()),
                  "single_component_cells": int((expected.available_components == 1).sum()),
                  "maximum_weighting_difference_pp": float(abs(expected.probability - expected.nominal_weighted_probability).max() * 100)}
        record("answer_schema", all(type(answer.get(k)) is int for k in list(values)[:3])
               and type(answer.get("maximum_weighting_difference_pp")) in (float, int), ["answer.json"])
        record("summary_metrics", all(type(answer.get(k)) in (float, int) and np.isfinite(answer[k])
               and np.isclose(answer[k], v, atol=1e-6, rtol=1e-6) for k, v in values.items()), ["answer.json", "controller-reference"])
    else:
        array("box_means", "indices.nc", ["box_temperature_c", "western_v_c"])
        array("standardization", "indices.nc", ["nino34_z", "western_v_z"])
        array("indices", "indices.nc", ["wvg"])
        x = load(private / "controller/indices.nc").wvg.values
        values = {"index_correlation": float(np.corrcoef(x)[0, 1]),
                  "mean_absolute_difference": float(abs(x[0] - x[1]).mean()),
                  "maximum_absolute_difference": float(abs(x[0] - x[1]).max())}
        record("answer_schema", all(type(answer.get(k)) in (float, int) for k in values), ["answer.json"])
        record("summary_metrics", all(type(answer.get(k)) in (float, int) and np.isfinite(answer[k])
               and np.isclose(answer[k], v, atol=1e-6, rtol=1e-6) for k, v in values.items()), ["answer.json", "controller-reference"])

    weighted = list(leaves(rubric["tree"]))
    basic_ids = set(rubric["basic_validity"]["checks"])
    expected_ids = basic_ids | {name for leaf, _ in weighted for name in leaf.get("checks", [])}
    if set(results) != expected_ids:
        raise ValueError(f"Rubric/checker mismatch: {set(results) ^ expected_ids}")
    outcomes = {}
    for leaf, _ in weighted:
        known = [results[name] for name in leaf.get("checks", [])]
        state = "fail" if any(c["state"] == "fail" for c in known) else (
            "pass" if leaf["evaluator"] == "deterministic" and known else "unresolved")
        outcomes[leaf["id"]] = {"state": state, "evidence": leaf["evidence"],
                                "detail": "Requires trusted execution or expert evidence" if state == "unresolved" else "Aggregated numerical checks"}
    lower = sum(weight for leaf, weight in weighted if outcomes[leaf["id"]]["state"] == "pass")
    upper = sum(weight for leaf, weight in weighted if outcomes[leaf["id"]]["state"] != "fail")
    mandatory_pass = all(results[name]["state"] == "pass" for name in expected_ids)
    return {"task": task, "task_version": spec["version"], "scope": "static_checks_only",
            "completion": "pending_execution_and_expert_review" if mandatory_pass else "incomplete_required_checks_failed",
            "all_deterministic_checks_pass": mandatory_pass, "leaves": outcomes,
            "check_results": results, "basic_validity": {name: results[name] for name in sorted(basic_ids)},
            "integrity": {"state": "unresolved", "detail": "Requires trusted run, network and retained-inventory evidence"},
            "weighted_score_bounds": [100 * lower, 100 * upper], "model_calls": 0,
            "submitted_code_executed": False}
