"""Build the control submissions used to certify this template's spec.

Each control is a valid forecast or one deliberate defect. `expect` names the
checks whose outcome the control exists to demonstrate. Every computed check not
named is expected to pass, or to fail where the control says `otherwise: fail`.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent

CONTROLS = {
    "correct": {"kind": "known_correct", "variant": {}, "expect": {}},
    "valid_raw_model": {"kind": "accepted_alternative", "variant": {"method": "raw"}, "expect": {}},
    "valid_climatology": {"kind": "accepted_alternative", "variant": {"method": "climatology"}, "expect": {}},
    "cached_forecast": {"kind": "incorrect", "variant": {}, "post": "cache",
                        "expect": {"probe.responds_to_inputs": "fail"}},
    "uses_later_forecasts": {"kind": "incorrect", "variant": {"uses_later_forecasts": True}, "expect": {"probe.no_future_information": "fail"}},
    "multiplied_by_14": {"kind": "incorrect", "variant": {"multiplied_by_14": True},
                         "expect": {"invariant.magnitude_of_a_14_day_total": "fail"}},
    "negative_totals": {"kind": "incorrect", "variant": {"negative_totals": True},
                        "expect": {"invariant.totals_not_negative": "fail"}},
    # unseeded noise also moves the forecasts before the cut date, so the causality probe cannot pass either
    "not_reproducible": {"kind": "incorrect", "variant": {"not_reproducible": True},
                         "expect": {"probe.replay": "fail", "probe.no_future_information": "fail"}},
    # a forecast that does not cover the required cases fails there, and every check that rests on it fails with it
    "missing_cases": {"kind": "incorrect", "variant": {"missing_cases": True}, "expect": {"coverage": "fail", "envelope": "pass"}, "otherwise": "fail"},
    "mislabelled_dates": {"kind": "incorrect", "variant": {"mislabelled_dates": True}, "expect": {"coverage": "fail", "envelope": "pass"}, "otherwise": "fail"},
    "no_answer": {"kind": "incorrect", "variant": {}, "post": "delete", "expect": {"envelope": "fail"}, "otherwise": "fail"},
    "level2_true_score": {"kind": "known_correct", "variant": {}, "post": "claim_true", "level": 2, "feedback_requests": 2, "expect": {}},
    "level2_unmeasured": {"kind": "accepted_alternative", "variant": {"claims": {"development_rmse_mm": None}}, "level": 2,
                          "feedback_requests": 0, "expect": {}},
    "level2_overclaimed_score": {"kind": "incorrect", "variant": {}, "post": "claim_false", "level": 2, "feedback_requests": 1,
                                 "expect": {"claim.development_rmse_mm": "fail"}},
    "level2_over_limit": {"kind": "incorrect", "variant": {"claims": {"development_rmse_mm": None}}, "level": 2, "feedback_requests": 6,
                          "expect": {"feedback.limit": "fail"}},
}
NOT_APPLICABLE = {"pitfall": "An outcome-mode task has no reference answer, so no reading of the brief can be a pitfall.",
                  "skipped_process_step": "An outcome-mode task has no process checklist.",
                  "false_method_pointer": "An outcome-mode task has no method statement."}


def _development_rmse(store, params):
    import xarray as xr
    module = importlib.util.spec_from_file_location("weeks34_reference", HERE.parent / "reference.py")
    reference = importlib.util.module_from_spec(module)
    module.loader.exec_module(reference)
    private = reference.ROOT / "var/private/templates/weeks34-rainfall"
    with xr.open_zarr(store, chunks=None) as arrays:
        forecast = arrays.development_mm.transpose("development_issue", "location").values
    return reference.score({"development_mm": forecast}, params, private, "development")["rmse_mm"]


def build(name, inputs, params, destination):
    """Write the control's submission folder, as an agent would have left it."""
    control, destination = CONTROLS[name], Path(destination)
    destination.mkdir(parents=True)
    shutil.copyfile(HERE / "solve.py", destination / "solve.py")
    if control["variant"]:
        (destination / "variant.json").write_text(json.dumps(control["variant"]) + "\n")
    subprocess.run([sys.executable, "solve.py", "--inputs", str(inputs), "--output", str(destination)], cwd=destination, check=True,
                   capture_output=True, text=True)
    (destination / "report.md").write_text(f"Control submission `{name}` built by the controller for certification. Not an agent attempt.\n")
    answer_path, store = destination / "answer.json", destination / "results.zarr"
    answer = json.loads(answer_path.read_text())
    post = control.get("post")
    if post == "delete":
        answer_path.unlink()
        shutil.rmtree(store)
        return destination
    if post == "cache":
        shutil.copyfile(HERE / "cached.py", destination / "cached.py")
        shutil.copyfile(answer_path, destination / "cached-answer.json")
        shutil.copytree(store, destination / "cached-results.zarr")
        answer["run"]["argv"][1] = "cached.py"
    elif post in ("claim_true", "claim_false"):
        claim = {"development_rmse_mm": _development_rmse(store, params) - (1.0 if post == "claim_false" else 0.0)}
        # the rerun must restate the claim, so it lives in the variant file the solver reads
        (destination / "variant.json").write_text(json.dumps({**control["variant"], "claims": claim}) + "\n")
        answer["claims"] = claim
    answer_path.write_text(json.dumps(answer, allow_nan=False) + "\n")
    return destination
