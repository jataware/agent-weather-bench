"""Build the control submissions used to certify this template's spec.

Each control is a known-correct solution or one deliberate defect. `expect` names
the checks whose outcome the control exists to demonstrate. Every computed check
not named is expected to pass, or to fail where the control says `otherwise: fail`.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

CONTROLS = {
    "correct": {"kind": "known_correct", "variant": {}, "expect": {}},
    "accepted_unclipped": {"kind": "accepted_alternative", "variant": {"keep_negative": True}, "expect": {},
                           "matched": {"negative_increments": ["unclipped"]}},
    "accepted_rearranged_arrays": {"kind": "accepted_alternative", "variant": {"rearranged": True}, "expect": {}},
    # the task parameters may be written into the code: a second instance is a second episode, not a rerun
    "accepted_hardcoded_parameters": {"kind": "accepted_alternative", "variant": {"hardcode_instance": True}, "expect": {}},
    "pitfall_summed_cumulative": {"kind": "pitfall", "variant": {"sum_cumulative": True}, "expect": {"variant": "fail"}, "pitfall": "summed_cumulative"},
    "pitfall_same_lead": {"kind": "pitfall", "variant": {"same_lead": True}, "expect": {"variant": "fail"}, "pitfall": "same_lead"},
    "pitfall_unweighted": {"kind": "pitfall", "variant": {"unweighted": True}, "expect": {"variant": "fail"}, "pitfall": "unweighted"},
    "pitfall_exclusive_boundary": {"kind": "pitfall", "variant": {"exclusive_boundary": True}, "expect": {"variant": "fail"}, "pitfall": "exclusive"},
    "pitfall_window_shift": {"kind": "pitfall", "variant": {"shift_window": True}, "expect": {"variant": "fail"}, "pitfall": "shifted_one_day_early"},
    # In this equatorial region a weighted and an unweighted mean agree within rounding on the submitted data, so the numbers
    # alone fit both. The changed-data probe tells them apart; where it cannot run, the variant stays open.
    "cached_output": {"kind": "incorrect", "variant": {}, "post": "cache", "expect": {"probe.changed_data": "fail", "variant": "unresolved"},
                      "reasons": {"variant": "ambiguous_variant"}},
    "overclaim": {"kind": "incorrect", "variant": {"wrong_claims": True}, "expect": {"claim.direction": "fail"}},
    "edited_numbers": {"kind": "incorrect", "variant": {}, "post": "edit",
                       "expect": {"variant": "unresolved", "invariant.change_equals_current_minus_previous": "fail", "probe.replay": "fail",
                                  # with no reading matched, the changed-data probe can show the code follows its inputs but not that it is right
                                  "probe.changed_data": "unresolved"}},
    # one broken part fails the checks that rest on it, and the rest is assessed on its merits
    "missing_result": {"kind": "incorrect", "variant": {}, "post": "drop_regional",
                       "expect": {"envelope": "fail", "variant": "fail", "claim.direction": "fail", "invariant.regional_change_within_cell_range": "fail"},
                       "blocked": ["variant", "claim.direction", "invariant.regional_change_within_cell_range"]},
    "no_run_command": {"kind": "incorrect", "variant": {}, "post": "drop_run",
                       "expect": {"envelope": "fail", "probe.replay": "fail", "probe.changed_data": "fail", "variant": "unresolved"},
                       "reasons": {"variant": "ambiguous_variant"}, "blocked": ["probe.replay", "probe.changed_data"]},
    "no_answer": {"kind": "incorrect", "variant": {}, "post": "delete", "expect": {"envelope": "fail"}, "otherwise": "fail"},
}
NOT_APPLICABLE = {"leak": "A product-mode task has no held-out targets to leak.",
                  "skipped_process_step": "A product-mode task has no process checklist.",
                  "false_method_pointer": "A product-mode task has no method statement."}


def build(name, inputs, params, destination):
    """Write the control's submission folder, as an agent would have left it."""
    import xarray as xr
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
    answer_path, store, post = destination / "answer.json", destination / "results.zarr", control.get("post")
    answer = json.loads(answer_path.read_text())
    if post == "cache":
        shutil.copyfile(HERE / "cached.py", destination / "cached.py")
        shutil.copyfile(answer_path, destination / "cached-answer.json")
        shutil.copytree(store, destination / "cached-results.zarr")
        answer["run"]["argv"][1] = "cached.py"
    elif post in ("edit", "drop_regional"):
        arrays = xr.open_zarr(store, chunks=None).load()
        if post == "edit":
            arrays.change_mm[dict(period=0, latitude=0, longitude=0)] += 5.0
        else:
            arrays = arrays.drop_vars("regional_change_mm")
        shutil.rmtree(store)
        arrays.to_zarr(store, mode="w", zarr_format=3, consolidated=False)
    elif post == "drop_run":
        del answer["run"]
    elif post == "delete":
        answer_path.unlink()
        shutil.rmtree(store)
        return destination
    answer_path.write_text(json.dumps(answer, allow_nan=False) + "\n")
    return destination
