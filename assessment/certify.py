"""The five certification tests for a template's spec (docs/assessment-format.md).

1. Two independent reference implementations agree.
2. A known-correct solution passes every check.
3. Deliberately incorrect solutions are caught by the right check.
4. The separability of every accepted-pitfall pair is measured and recorded.
5. Model attempts are run and every unknown answer is ruled on.

Test 5 needs agent runs, so this module records it as not run.
"""
import importlib.util
import json
import shutil
from datetime import datetime, timezone

import numpy as np

from .assess import assess
from .compare import compare
from .outcomes import JUDGE
from .spec import ROOT
from .variant import _reference


def _controls(template):
    module = importlib.util.spec_from_file_location(f"controls_{template.name.replace('-', '_')}", template.folder / "controls/build.py")
    loaded = importlib.util.module_from_spec(module)
    module.loader.exec_module(loaded)
    return loaded


def scoring_agreement(template, instances, scratch):
    """Test 1 for outcome mode: two implementations of the metric and its baselines, on every instance and split."""
    compared, worst, hooks = 0, 0.0, template.hooks
    for params in instances:
        for which in template.spec["skill"]["baselines"]:
            forecast = hooks.baseline_results(template.private, params, which)
            for split in template.spec["skill"]["splits"]:
                a, b = hooks.score(forecast, params, template.private, split), hooks.independent_score(forecast, params, template.private, split)
                worst = max(worst, max(abs(a[key] - b[key]) for key in a if isinstance(a[key], float)))
                compared += 1
    scratch.mkdir(parents=True, exist_ok=True)
    extra = hooks.regression_checks(scratch) if hasattr(hooks, "regression_checks") else []
    return {"passed": worst <= 1e-9 and all(row["passed"] for row in extra), "instances": len(instances), "comparisons": compared,
            "largest_difference": worst, "problems": [], "regression_checks": extra}


def _given(template, inputs, params):
    """Stand-in free results, where a reference is derived from what the submission itself supplies."""
    if getattr(template.hooks, "REFERENCE_USES_SUBMISSION", False):
        return template.hooks.example_free_results(inputs, params)
    return None


def _gap(a, b):
    """Largest difference between two implementations' arrays; labels must be equal."""
    if a.dtype.kind in "US" or b.dtype.kind in "US":
        return 0.0 if np.array_equal(a, b) else float("inf")
    return float(np.max(np.abs(a - b))) if a.size else 0.0


def reference_agreement(template, inputs_for, instances):
    """Test 1: implementations A and B over every instance and every combination.

    Also checks each declared tolerance against the data: the largest reference value
    under an accepted reading must not exceed the magnitude the error bound assumes.
    """
    compared, worst, problems, largest = 0, 0.0, [], {}
    for params in instances:
        given = _given(template, inputs_for(params), params)
        for combination in template.combinations():
            outcomes = []
            for function in (template.hooks.reference, template.hooks.independent):
                try:
                    outcomes.append(function(inputs_for(params), params, combination, given) if given is not None
                                    else function(inputs_for(params), params, combination))
                except ValueError:
                    outcomes.append(None)
            a, b = outcomes
            if (a is None) != (b is None):
                problems.append({"instance": params["id"], "conventions": combination, "problem": "one implementation has no answer"})
            elif a is not None:
                if any(a[name].shape != b[name].shape for name in a):
                    problems.append({"instance": params["id"], "conventions": combination, "problem": "shapes differ"})
                else:
                    worst = max(worst, max(_gap(a[name], b[name]) for name in a))
                    if not template.pitfalls_in(combination):
                        for name in a:
                            if a[name].dtype.kind not in "US" and a[name].size:
                                largest[name] = max(largest.get(name, 0.0), float(np.max(np.abs(a[name]))))
                compared += 1
    extra = template.hooks.regression_checks(inputs_for(instances[0])) if hasattr(template.hooks, "regression_checks") else []
    bounds = {name: {"tolerance": row["tolerance"]["atol"], "declared": {key: value for key, value in row["tolerance"].items() if key != "atol"},
                     "largest_reference_value": largest.get(name),
                     "within_declared_magnitude": "magnitude" not in row["tolerance"] or largest.get(name, 0.0) <= row["tolerance"]["magnitude"]}
              for name, row in template.matched().items() if "tolerance" in row}
    passed = not problems and worst <= 1e-9 and all(row["passed"] for row in extra) and all(row["within_declared_magnitude"] for row in bounds.values())
    return {"passed": passed, "instances": len(instances), "combinations": len(template.combinations()), "comparisons": compared,
            "largest_difference": worst, "problems": problems[:10], "regression_checks": extra, "tolerances": bounds}


def separability(template, inputs_for, perturbed_for, instances):
    """Test 4: on how many instances does each pitfall give different numbers from the accepted readings?"""
    conventions, results_spec = template.spec["conventions"], template.matched()
    accepted = [c for c in template.combinations() if not template.pitfalls_in(c)]
    pairs = []
    for dimension, values in conventions.items():
        for value, label in values.items():
            if label == "pitfall":
                pairs.append((value, dimension, [(base, {**base, dimension: value}) for base in accepted], "accepted_vs_pitfall"))
        names = [value for value, label in values.items() if label == "accepted"]
        for i, first in enumerate(names):
            for second in names[i + 1:]:
                bases = [c for c in accepted if c[dimension] == first]
                pairs.append((f"{first} vs {second}", dimension, [(base, {**base, dimension: second}) for base in bases], "accepted_vs_accepted"))

    def apart(inputs, params, a, b):
        """How far two readings are apart, in units of the tolerance of the result that separates them most."""
        try:
            given = _given(template, inputs, params)
            first, second = _reference(template, inputs, params, a, given), _reference(template, inputs, params, b, given)
        except ValueError:
            return float("inf")                                   # a reading with no answer cannot be confused with one that has
        ratio = 0.0
        for name, detail in compare(results_spec, second, first)[1].items():
            if detail["largest_difference"] is None:
                ratio = float("inf") if not detail["agrees"] else ratio
            elif results_spec[name]["tolerance"]["atol"] == 0:
                ratio = float("inf") if detail["largest_difference"] > 0 else ratio
            else:
                ratio = max(ratio, detail["largest_difference"] / results_spec[name]["tolerance"]["atol"])
        return ratio
    table = []
    for name, dimension, combos, kind in pairs:
        ratios = {params["id"]: min(apart(inputs_for(params), params, a, b) for a, b in combos) for params in instances}
        separated = [identifier for identifier, ratio in ratios.items() if ratio > 1]
        row = {"pair": name, "convention": dimension, "kind": kind, "separated_on": len(separated), "instances": len(instances),
               # the closest any separated instance comes to the tolerance; 1 would be the edge
               "smallest_separation_in_tolerances": (lambda values: None if not values else "exact mismatch" if min(values) == float("inf") else round(min(values), 1))(
                   [ratios[identifier] for identifier in separated]),
               "largest_coincidence_in_tolerances": round(max((ratio for ratio in ratios.values() if ratio <= 1), default=0.0), 3)}
        if len(separated) == len(instances):
            row["status"] = "separated by the numbers on every instance"
        else:
            # where the submitted data cannot tell two readings apart, the controller's changed data may
            rest = [params for params in instances if params["id"] not in separated]
            probe = [params["id"] for params in rest if all(apart(perturbed_for(params), params, a, b) > 1 for a, b in combos)]
            row["separated_on_changed_data"], row["separated_by_neither"] = len(probe), len(rest) - len(probe)
            row["status"] = ("separated by the numbers or by the changed-data probe on every instance" if len(probe) == len(rest) else
                             "not separable on some instances: a known ambiguity there" if separated or probe else "not separable: a known ambiguity")
            row["not_separated_on"] = [params["id"] for params in rest if params["id"] not in probe][:12]
        table.append(row)
    return table


def run_controls(template, executor, instances, scratch, inputs_for):
    """Tests 2 and 3: every control must produce exactly the outcomes it exists to demonstrate."""
    controls, rows = _controls(template), []
    for name, control in controls.CONTROLS.items():
        for params in instances:
            folder = scratch / "controls" / name / params["id"]
            submission = controls.build(name, inputs_for(params), params, folder / "submission")
            level, requests = control.get("level", 1), control.get("feedback_requests")
            feedback = None if requests is None else {"scope": "development_only", "limit_denials": 0,
                                                      "requests": [{"query": i + 1, "status": "scored"} for i in range(requests)]}
            result = assess(template, params, submission, executor, folder / "assessment", level=level, feedback=feedback)
            computed = {check: row for check, row in result["checks"].items() if row.get("decided_by") != JUDGE}
            expect, problems, note, otherwise = control["expect"], [], None, control.get("otherwise", "pass")
            for check, row in {**computed, **{check: result["checks"][check] for check in expect}}.items():
                wanted = expect.get(check, otherwise)
                if row["state"] == wanted:
                    # a check that fails only because an earlier part is broken must say which part
                    if wanted == "fail" and (check in control.get("blocked", []) or (otherwise == "fail" and check not in expect)) and "blocked_by" not in row \
                            and not check.startswith("process."):
                        problems.append(f"{check}: failed without naming the part that blocks it")
                    continue
                if control["kind"] == "pitfall" and row.get("reason") == "ambiguous_variant":
                    note = "the pitfall coincides with an accepted reading on this instance, on the submitted data and on the changed data"
                    continue
                problems.append(f"{check}: expected {wanted}, got {row['state']} ({row['detail'][:120]})")
            if control["kind"] == "pitfall" and computed["variant"]["state"] == "fail" and control["pitfall"] not in computed["variant"].get("pitfalls_certain", []):
                problems.append(f"variant failed without naming {control['pitfall']}")
            for check, reason in control.get("reasons", {}).items():
                if result["checks"][check].get("reason") != reason:
                    problems.append(f"{check}: expected reason {reason}, got {result['checks'][check].get('reason')}")
            for dimension, values in control.get("matched", {}).items():           # the reading the control used must be among those matched
                if not set(values) <= set((result.get("matched_conventions") or {}).get(dimension) or []):
                    problems.append(f"matched {dimension} = {(result.get('matched_conventions') or {}).get(dimension)}, expected to include {values}")
            rows.append({"control": name, "kind": control["kind"], "instance": params["id"], "as_expected": not problems, "problems": problems,
                         "note": note, "level": level, "computed_outcome": result["computed_outcome"],
                         "skill": next(iter((result.get("skill") or {}).values()), None),
                         "states": {check: row["state"] for check, row in computed.items()},
                         "variant_detail": computed["variant"]["detail"] if "variant" in computed else None})
            shutil.rmtree(folder / "assessment", ignore_errors=True)
    return rows, controls.NOT_APPLICABLE


def model_attempts(template):
    """Test 5: agent attempts assessed under the current fingerprint, and whether any answer is still unknown."""
    from .runner import RUNS
    current, stale = [], 0
    for folder in sorted(RUNS.glob("*")) if RUNS.is_dir() else []:
        if not ((folder / "run.json").is_file() and (folder / "assessment.json").is_file()):
            continue
        meta, assessment = json.loads((folder / "run.json").read_text()), json.loads((folder / "assessment.json").read_text())
        if meta.get("template") != template.name or meta.get("kind") != "agent":
            continue
        if assessment.get("fingerprint") != template.fingerprint():
            stale += 1
            continue
        current.append({"run": meta["id"], "system": meta["system"], "instance": meta["instance"]["id"], "level": meta.get("level", 1),
                        "outcome": assessment["outcome"], "computed_outcome": assessment["computed_outcome"],
                        "judged_outcome": assessment.get("judged_outcome"), "supplied": meta.get("supplied", []), "parent": meta.get("parent"),
                        "unknown_answer_checks": ["variant"] if assessment["checks"].get("variant", {}).get("reason") == "unknown_answer" else [],
                        "ruling": (assessment["checks"].get("variant", {}).get("ruling") or {}).get("status")})
    unknown = sum(bool(row["unknown_answer_checks"]) for row in current)
    enough = len(current) >= 2
    return {"passed": (unknown == 0) if enough else None, "status": "run" if current else "not_run", "attempts": len(current),
            "systems": sorted({row["system"] for row in current}), "attempts_with_an_unruled_unknown_answer": unknown,
            "attempts_assessed_under_another_fingerprint": stale,
            "rulings_awaiting_confirmation": sum(row["ruling"] == "proposed" for row in current),
            "detail": ("Needs at least two agent attempts assessed under this fingerprint." if not enough else
                       "Every attempt's answer was classified." if unknown == 0 else "Some answers match no listed reading and await a ruling."),
            "runs": current}


def record_attempts(template):
    """Refresh test 5 in the tracked certification record, without rerunning the other four tests."""
    path = template.folder / "certification.json"
    record = json.loads(path.read_text())
    if record["fingerprint"] != template.fingerprint():
        raise ValueError("The certification record is for another fingerprint; run certify first")
    record["tests"]["5_model_attempts"] = model_attempts(template)
    path.write_text(json.dumps(record, indent=1) + "\n")
    return record["tests"]["5_model_attempts"]


def certify(template, executor, full=False, control_instances=2):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    scratch = ROOT / "var/certification" / template.name / stamp
    scratch.mkdir(parents=True)
    development, everything = template.development_instances(), template.hooks.candidate_instances()
    staged = {}

    shared = getattr(template.hooks, "INPUTS_SHARED_ACROSS_INSTANCES", False)

    def inputs_for(params, perturbed=False, exact=False):
        """Staged inputs. The reference ignores instance.json, so it may share one folder; a solution may not."""
        key = (params["id"] if exact or not shared else "shared", perturbed)
        if key not in staged:
            folder = scratch / "inputs" / f"{key[0]}{'-perturbed' if perturbed else ''}"
            template.hooks.stage_inputs(template.private, params, folder)
            if perturbed:
                template.hooks.perturb_inputs(folder, 20261006)
            staged[key] = folder
        return staged[key]

    outcome_mode = template.spec["mode"] == "outcome"
    if outcome_mode:
        agreement = scoring_agreement(template, everything, scratch / "regression")
    else:
        agreement = reference_agreement(template, inputs_for, everything if full else development)
    controls, not_applicable = run_controls(template, executor, development[:control_instances], scratch,
                                            lambda params: inputs_for(params, exact=True))
    pairs = [] if outcome_mode else separability(template, inputs_for, lambda params: inputs_for(params, perturbed=True), everything)
    correct = [row for row in controls if row["kind"] in ("known_correct", "accepted_alternative")]
    incorrect = [row for row in controls if row["kind"] in ("pitfall", "incorrect")]
    report = {
        "schema_version": 1, "template": template.name, "spec_version": template.spec["spec_version"], "fingerprint": template.fingerprint(),
        "certified_at": stamp, "executor": executor.name,
        "tests": {
            "1_reference_implementations_agree": agreement,
            "2_known_correct_solutions_pass": {"passed": all(row["as_expected"] for row in correct), "controls": correct},
            "3_incorrect_solutions_are_caught": {"passed": all(row["as_expected"] for row in incorrect), "controls": incorrect,
                                                 "not_applicable": not_applicable},
            "4_separability": {"passed": True, "pairs": pairs,
                               **({"not_applicable": "Outcome mode has no reference answer, so there are no readings to separate."} if outcome_mode else {}),
                               "known_ambiguities": [row["pair"] for row in pairs if row["status"].startswith("not separable") and row["kind"] == "accepted_vs_pitfall"]},
            "5_model_attempts": model_attempts(template),
        },
    }
    report["automatic_tests_passed"] = all(report["tests"][name]["passed"] for name in list(report["tests"])[:4])
    report["certified"] = False                                    # a domain scientist's approval is still outstanding
    (scratch / "certification.json").write_text(json.dumps(report, indent=2) + "\n")
    summary = json.loads(json.dumps(report))
    for test in ("2_known_correct_solutions_pass", "3_incorrect_solutions_are_caught"):
        summary["tests"][test]["controls"] = [{key: row[key] for key in ("control", "kind", "instance", "level", "as_expected", "problems", "note", "computed_outcome", "skill")}
                                              for row in summary["tests"][test]["controls"]]
    (template.folder / "certification.json").write_text(json.dumps(summary, indent=1) + "\n")
    for name in ("inputs", "controls", "regression"):
        shutil.rmtree(scratch / name, ignore_errors=True)
    return report
