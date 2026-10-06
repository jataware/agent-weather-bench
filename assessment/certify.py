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
from .spec import ROOT


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


def reference_agreement(template, inputs_for, instances):
    """Test 1: implementations A and B over every instance and every combination."""
    compared, worst, problems = 0, 0.0, []
    for params in instances:
        for combination in template.combinations():
            outcomes = []
            for function in (template.hooks.reference, template.hooks.independent):
                try:
                    outcomes.append(function(inputs_for(params), params, combination))
                except ValueError:
                    outcomes.append(None)
            a, b = outcomes
            if (a is None) != (b is None):
                problems.append({"instance": params["id"], "conventions": combination, "problem": "one implementation has no answer"})
            elif a is not None:
                if any(a[name].shape != b[name].shape for name in a):
                    problems.append({"instance": params["id"], "conventions": combination, "problem": "shapes differ"})
                else:
                    worst = max(worst, max(float(np.max(np.abs(a[name] - b[name]))) for name in a))
                compared += 1
    extra = template.hooks.regression_checks(inputs_for(instances[0])) if hasattr(template.hooks, "regression_checks") else []
    passed = not problems and worst <= 1e-9 and all(row["passed"] for row in extra)
    return {"passed": passed, "instances": len(instances), "combinations": len(template.combinations()), "comparisons": compared,
            "largest_difference": worst, "problems": problems[:10], "regression_checks": extra}


def separability(template, inputs_for, perturbed_for, instances):
    """Test 4: on how many instances does each pitfall give different numbers from the accepted readings?"""
    conventions, results_spec = template.spec["conventions"], template.spec["results"]
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

    def differs(inputs, params, a, b):
        try:
            return not compare(results_spec, template.hooks.reference(inputs, params, b), template.hooks.reference(inputs, params, a))[0]
        except ValueError:
            return True                                           # a reading with no answer cannot be confused with one that has
    table = []
    for name, dimension, combos, kind in pairs:
        apart = [params["id"] for params in instances if all(differs(inputs_for(params), params, a, b) for a, b in combos)]
        row = {"pair": name, "convention": dimension, "kind": kind, "separated_on": len(apart), "instances": len(instances)}
        if len(apart) == len(instances):
            row["status"] = "separated by the numbers on every instance"
        elif apart:
            row["status"] = "separated by the numbers on some instances; the changed-instance probe covers the rest"
            row["not_separated_on"] = [params["id"] for params in instances if params["id"] not in apart][:12]
        else:
            probe = [params["id"] for params in instances[:6] if all(differs(perturbed_for(params), params, a, b) for a, b in combos)]
            row["status"] = "separated only by the changed-data probe" if probe else "not separable: a known ambiguity"
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
            computed = {check: row for check, row in result["checks"].items() if not check.startswith("interpretation.")}
            expect, problems, note = control["expect"], [], None
            stopped = next((check for check in ("envelope", "coverage") if expect.get(check) == "fail"), None)
            if stopped:
                unassessed = [check for check, row in computed.items() if row.get("reason") == "not_assessed"]
                if computed[stopped]["state"] != "fail" or result["computed_outcome"] != "fail" or not unassessed:
                    problems.append(f"an unusable answer was not failed at {stopped} with the remaining checks left unassessed")
            else:
                for check, row in computed.items():
                    wanted = expect.get(check, "pass")
                    if row["state"] == wanted:
                        continue
                    if check == "variant" and control["kind"] == "pitfall" and row.get("reason") == "ambiguous_variant":
                        note = "the pitfall coincides with an accepted reading on this instance and on its probe instance"
                        continue
                    problems.append(f"{check}: expected {wanted}, got {row['state']} ({row['detail'][:120]})")
                if control["kind"] == "pitfall" and computed["variant"]["state"] == "fail" and control["pitfall"] not in computed["variant"].get("pitfalls_certain", []):
                    problems.append(f"variant failed without naming {control['pitfall']}")
                for dimension, values in control.get("matched", {}).items():
                    if (result.get("matched_conventions") or {}).get(dimension) != values:
                        problems.append(f"matched {dimension} = {(result.get('matched_conventions') or {}).get(dimension)}, expected {values}")
            rows.append({"control": name, "kind": control["kind"], "instance": params["id"], "as_expected": not problems, "problems": problems,
                         "note": note, "level": level, "computed_outcome": result["computed_outcome"],
                         "skill": (result.get("skill") or {}).get("final"),
                         "states": {check: row["state"] for check, row in computed.items()},
                         "variant_detail": computed["variant"]["detail"] if "variant" in computed else None})
            shutil.rmtree(folder / "assessment", ignore_errors=True)
    return rows, controls.NOT_APPLICABLE


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
            "5_model_attempts": {"passed": None, "status": "not_run", "detail": "No agent attempts have been run against this spec version."},
        },
    }
    report["automatic_tests_passed"] = all(report["tests"][name]["passed"] for name in list(report["tests"])[:4])
    report["certified"] = False                                    # test 5 and human approval are still outstanding
    (scratch / "certification.json").write_text(json.dumps(report, indent=2) + "\n")
    summary = json.loads(json.dumps(report))
    for test in ("2_known_correct_solutions_pass", "3_incorrect_solutions_are_caught"):
        summary["tests"][test]["controls"] = [{key: row[key] for key in ("control", "kind", "instance", "level", "as_expected", "problems", "note", "computed_outcome", "skill")}
                                              for row in summary["tests"][test]["controls"]]
    (template.folder / "certification.json").write_text(json.dumps(summary, indent=1) + "\n")
    for name in ("inputs", "controls", "regression"):
        shutil.rmtree(scratch / name, ignore_errors=True)
    return report
