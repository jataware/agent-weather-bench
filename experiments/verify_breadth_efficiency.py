"""Join independently reviewed native use with the frozen breadth ledger; no inference."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template


def read(path):
    return json.loads((ROOT / path).read_text())


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def interpretation(base_valid, tool_valid, substantive):
    eligible = base_valid and tool_valid and substantive
    if eligible:
        detail = "Both completed validly and native dataflow is verified; descriptive resource comparison only."
    elif tool_valid and not base_valid and substantive:
        detail = "Exploratory valid-versus-incomplete completion difference; not a speedup or efficiency percentage claim."
    elif base_valid and not tool_valid:
        detail = "Python completed and guided did not; guided resource differences are not savings at valid completion."
    else:
        detail = "Valid completion/native use prerequisites are not all met; no tooling efficiency claim."
    return eligible, detail


def main():
    plan_path = "experiments/tooling-breadth-plan-2026-10-08.json"
    raw_path = "experiments/tooling-breadth-results-2026-10-08.json"
    plan, raw = read(plan_path), read(raw_path)
    assert raw["plan_sha256"] == digest(plan_path)
    assert digest("experiments/breadth_efficiency.py") == plan["launcher_sha256"]
    assert not raw["pending"] and not raw["unlaunched_cells"]
    assert raw["assessed_attempts"] == raw["launched_cells"] == plan["max_new_agent_attempts"] == 6
    assert all(row["usage"] is not None for row in raw["rows"]), "Unknown usage must not silently disappear from totals"
    for system, assigned in plan["systems"].items():
        for name, expected in assigned["files"].items():
            assert digest(f"systems/{system}/{name}") == expected
    reviews = {}
    review_paths = []
    for pair_id, pair in plan["pairs"].items():
        assert Template(pair["template"]).fingerprint() == pair["fingerprint"]
        path = f"experiments/breadth-{pair_id.replace('_', '-')}-native-use-review-2026-10-08.json"
        review = read(path)
        for relative, expected in review["reviewfileshashes"].items():
            assert digest(relative) == expected, relative
        reviews[review["run"]] = review
        review_paths.append(path)
    verified = copy.deepcopy(raw)
    verified["verified_at"] = datetime.now(timezone.utc).isoformat()
    verified["state"] = "pass: evidence accounting verified; individual failed attempts remain failures"
    verified["raw_summary_sha256"] = digest(raw_path)
    verified["resource_totals_complete_for_all_six_assigned_attempts"] = True
    for row in verified["rows"]:
        if row["arm"] == "python":
            continue
        review = reviews[row["run"]]
        row["tool_compliance"] = review["status"]
        row["native_use_review"] = review
    for pair_id, comparison in verified["paired_comparisons"].items():
        pair_rows = [r for r in verified["rows"] if r["pair"] == pair_id]
        base = next(r for r in pair_rows if r["arm"] == "python")
        tool = next(r for r in pair_rows if r["arm"] != "python")
        review = reviews[tool["run"]]
        substantive = review["status"] == "pass" and review["actual_execution"] and not review["import_or_toy_only"]
        eligible, detail = interpretation(base["computed"] == "pass", tool["computed"] == "pass", substantive)
        raw_delta = comparison.pop("tool_relative_resource_reductions")
        comparison.update(efficiency_comparison_eligible=eligible, substantive_native_use=substantive,
                          raw_descriptive_resource_reductions=raw_delta,
                          eligible_efficiency_resource_reductions=raw_delta if eligible else None,
                          interpretation=detail)
    old_path = "experiments/efficiency_precision_results_2026-10-08.json"
    old = read(old_path)
    original_rows = old["rows"]
    repeat_rows = [r for r in verified["rows"] if r["pair"] == "mam_replication"]
    pooled = {}
    for arm in ("python", "guided_accord"):
        prior = [r for r in original_rows if r["assigned_arm"] == arm]
        repeat = [r for r in repeat_rows if r["arm"] == arm]
        assert len(prior) == len(repeat) == 1
        valid = sum(r["computed"] == "pass" for r in prior + repeat)
        fresh = sum(r["fresh_input_plus_output_tokens"] for r in prior + repeat)
        seconds = sum(r["agent_seconds"] for r in prior + repeat)
        pooled[arm] = {"attempts": 2, "computed_valid_completions": valid,
                       "fresh_input_plus_output_including_failures": fresh,
                       "agent_seconds_including_failures": seconds,
                       "fresh_input_plus_output_per_valid_completion": fresh / valid if valid else None,
                       "agent_seconds_per_valid_completion": seconds / valid if valid else None}
    verified["mam_same_condition_two_pair_ledger"] = {
        "original_precision_results_sha256": digest(old_path), "by_arm": pooled,
        "interpretation": "Two fresh matched pairs on one historical instance. Original v1 failures excluded from this same-condition comparison but preserved in their own ledger. No statistical confidence or cross-task generalization."}
    diagnostic_path = "experiments/breadth-consolidation-portability-diagnostic-2026-10-08.json"
    verified["separate_diagnostic"] = {"path": diagnostic_path, "sha256": digest(diagnostic_path),
                                       "original_guided_failure_remains_failure": True}
    verified["evidence_sha256"] = {p: digest(p) for p in [plan_path, raw_path, old_path, *review_paths, diagnostic_path]}
    verified["verification_model_calls"] = 0
    verified["verification_scientific_binary_decoding"] = False
    destination = ROOT / "experiments/tooling-breadth-verified-results-2026-10-08.json"
    destination.write_text(json.dumps(verified, indent=2) + "\n")
    print(json.dumps({"state": verified["state"], "comparisons": verified["paired_comparisons"],
                      "mam_two_pair_ledger": pooled}, indent=2))


if __name__ == "__main__":
    # Explicit gate checks cover the scientific-failure case as well as native-use absence.
    assert interpretation(True, True, True)[0]
    assert not interpretation(True, False, True)[0]
    assert not interpretation(False, True, True)[0]
    assert not interpretation(True, True, False)[0]
    main()
