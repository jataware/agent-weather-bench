"""Build the control submissions used to certify this template's spec.

Each control is a conformant solution or one deliberate defect. `expect` names
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
    "accepted_plain_observation_mean": {"kind": "accepted_alternative", "variant": {"unweighted_observations": True}, "expect": {},
                                        "matched": {"observation_weighting": ["unweighted"]}},
    "accepted_training_frequencies": {"kind": "accepted_alternative", "variant": {"training_frequencies": True}, "expect": {},
                                      "matched": {"climatology_reference": ["training_frequencies"]}},
    "accepted_climatological_forecast": {"kind": "accepted_alternative", "variant": {"climatological_forecast": True}, "expect": {}},
    "pitfall_thirty_day_months": {"kind": "pitfall", "variant": {"month_lengths": "thirty_days"}, "pitfall": "thirty_days",
                                  "expect": {"variant": "fail", "process.model_forecast_prepared": "fail"}},
    "pitfall_rates_not_converted": {"kind": "pitfall", "variant": {"month_lengths": "rates_not_converted"}, "pitfall": "rates_not_converted",
                                    "expect": {"variant": "fail", "process.model_forecast_prepared": "fail"}},
    "pitfall_full_sample_thresholds": {"kind": "pitfall", "variant": {"full_sample_thresholds": True}, "pitfall": "full_sample",
                                       "expect": {"variant": "fail", "process.verification_categories": "fail", "process.historical_performance": "fail"}},
    "skipped_cross_validation": {"kind": "incorrect", "variant": {"not_cross_validated": True},
                                 "expect": {"probe.held_out_year_isolation": "fail", "process.cross_validated": "fail"}},
    "pooled_new_years": {"kind": "incorrect", "variant": {"pooled_new_batch": True},
                         "expect": {"probe.new_years_forecast_separately": "fail", "process.operational_application": "fail"}},
    "invalid_probabilities": {"kind": "incorrect", "variant": {"invalid_probabilities": True},
                              "expect": {"invariant.probabilities_valid": "fail", "process.probabilistic_format": "fail"}},
    "cached_output": {"kind": "incorrect", "variant": {}, "post": "cache",
                      "expect": {"probe.changed_data": "fail", "process.reproducible": "fail"}},
    # a piece the brief asks for and the answer omits is the submission's failure, not an open question
    "no_method_statement": {"kind": "incorrect", "variant": {"no_method_statement": True},
                            "expect": {"process.documented_calibration": "fail", "process.documented_cross_validation": "fail"}},
    "false_method_pointer": {"kind": "incorrect", "variant": {"false_method_pointer": True}, "expect": {"process.documented_calibration": "fail"}},
    "no_answer": {"kind": "incorrect", "variant": {}, "post": "delete", "expect": {"envelope": "fail"}, "otherwise": "fail"},
}
NOT_APPLICABLE = {"target_leak_at_level_2": "This template has no Level 2 submission yet."}


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
    if control.get("post") == "delete":
        answer_path.unlink()
        shutil.rmtree(store)
        return destination
    if control.get("post") == "cache":
        answer = json.loads(answer_path.read_text())
        shutil.copyfile(HERE / "cached.py", destination / "cached.py")
        shutil.copyfile(answer_path, destination / "cached-answer.json")
        shutil.copytree(store, destination / "cached-results.zarr")
        answer["run"]["argv"][1] = "cached.py"
        answer_path.write_text(json.dumps(answer, allow_nan=False) + "\n")
    return destination
