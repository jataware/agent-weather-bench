"""Build the control submissions used to certify this template's spec.

Each control is a known-correct solution or one deliberate defect. `expect` names
the checks whose outcome the control exists to demonstrate; every check not named
is expected to pass, apart from the judge-only interpretation checks.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES_PASS = {"probe.replay": "pass", "probe.changed_data": "pass", "probe.changed_instance": "pass"}

CONTROLS = {
    "correct": {"kind": "known_correct", "variant": {}, "expect": {}},
    "accepted_unclipped": {"kind": "accepted_alternative", "variant": {"keep_negative": True}, "expect": {},
                           "matched": {"negative_increments": ["unclipped"]}},
    "accepted_ascending_latitude": {"kind": "accepted_alternative", "variant": {"ascending_latitude": True}, "expect": {}},
    "pitfall_summed_cumulative": {"kind": "pitfall", "variant": {"sum_cumulative": True}, "expect": {"variant": "fail"}, "pitfall": "summed_cumulative"},
    "pitfall_same_lead": {"kind": "pitfall", "variant": {"same_lead": True}, "expect": {"variant": "fail"}, "pitfall": "same_lead"},
    "pitfall_unweighted": {"kind": "pitfall", "variant": {"unweighted": True}, "expect": {"variant": "fail"}, "pitfall": "unweighted"},
    "pitfall_exclusive_boundary": {"kind": "pitfall", "variant": {"exclusive_boundary": True}, "expect": {"variant": "fail"}, "pitfall": "exclusive"},
    "pitfall_window_shift": {"kind": "pitfall", "variant": {"shift_window": True}, "expect": {"variant": "fail"}, "pitfall": "shifted_one_day_early"},
    "cached_output": {"kind": "incorrect", "variant": {}, "post": "cache",
                      "expect": {"probe.changed_data": "fail", "probe.changed_instance": "fail"}},
    "hardcoded_instance": {"kind": "incorrect", "variant": {"hardcode_instance": True}, "expect": {"probe.changed_instance": "fail"}},
    "overclaim": {"kind": "incorrect", "variant": {"wrong_claims": True}, "expect": {"claim.direction": "fail"}},
    "edited_numbers": {"kind": "incorrect", "variant": {}, "post": "edit",
                       "expect": {"variant": "unresolved", "invariant.change_equals_current_minus_previous": "fail", "probe.replay": "fail",
                                  # with no reading matched, the changed-input probes can show the code follows its inputs but not that it is right
                                  "probe.changed_data": "unresolved", "probe.changed_instance": "unresolved"}},
    "no_answer": {"kind": "incorrect", "variant": {}, "post": "delete", "expect": {"envelope": "fail"}},
}
NOT_APPLICABLE = {"leak": "A product-mode task has no held-out targets to leak.",
                  "skipped_process_step": "A product-mode task has no process checklist.",
                  "false_method_pointer": "A product-mode task has no method statement."}


def build(name, inputs, params, destination):
    """Write the control's submission folder, as an agent would have left it."""
    control, destination = CONTROLS[name], Path(destination)
    destination.mkdir(parents=True)
    shutil.copyfile(HERE / "solve.py", destination / "solve.py")
    variant = dict(control["variant"])
    if variant.get("hardcode_instance"):
        variant["hardcode_instance"] = params
    if variant:
        (destination / "variant.json").write_text(json.dumps(variant) + "\n")
    subprocess.run([sys.executable, "solve.py", "--inputs", str(inputs), "--output", str(destination)], cwd=destination, check=True,
                   capture_output=True, text=True)
    (destination / "report.md").write_text(f"Control submission `{name}` built by the controller for certification. Not an agent attempt.\n")
    answer_path = destination / "answer.json"
    answer = json.loads(answer_path.read_text())
    if control.get("post") == "cache":
        shutil.copyfile(HERE / "cached.py", destination / "cached.py")
        shutil.copyfile(answer_path, destination / "cached-answer.json")
        answer["run"]["argv"][1] = "cached.py"
    elif control.get("post") == "edit":
        answer["results"]["change_mm"][0][0][0] += 5.0
    elif control.get("post") == "delete":
        answer_path.unlink()
        return destination
    answer_path.write_text(json.dumps(answer, allow_nan=False) + "\n")
    return destination
