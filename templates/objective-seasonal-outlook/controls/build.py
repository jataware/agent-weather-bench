"""Controls obtain their inputs through the same HTTP catalogue as agents, then run science.py with a declared defect."""
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
CONTROLS = {
    "correct": {"kind": "known_correct", "expect": {}},
    "independent": {"kind": "known_correct", "expect": {}},
    "reordered": {"kind": "accepted_alternative", "expect": {}},
    "bilinear_residual": {"kind": "accepted_alternative", "expect": {}, "matched": {"obs_regridding": ["bilinear"], "ereg_variance": ["residual"]}},
    # one planted fault per stage
    # a result that matches no listed reading leaves the variant match and the changed-data probe unresolved; the fault is caught elsewhere
    "wrong_initialization": {"kind": "incorrect", "expect": {"invariant.cca_agreement": "fail", "variant": "unresolved", "probe.changed_data": "unresolved"}},  # acquire
    "thirty_days": {"kind": "pitfall", "pitfall": "thirty_days", "expect": {"variant": "fail"}},                         # prepare
    "wvg_leak": {"kind": "incorrect", "expect": {"probe.held_out_year_isolation": "fail", "variant": "unresolved", "probe.changed_data": "unresolved"}},  # WVG
    "ereg_no_cross_validation": {"kind": "incorrect", "expect": {"probe.held_out_year_isolation": "fail", "variant": "unresolved", "probe.changed_data": "unresolved"}},  # eReg
    "cca_future_training": {"kind": "incorrect", "expect": {"probe.held_out_year_isolation": "fail"}},                   # CCA
    "unequal_weights": {"kind": "incorrect", "expect": {"invariant.equal_stream_combination": "fail"}},                 # combine
    "wrong_climatology_score": {"kind": "incorrect", "expect": {"invariant.score_identity": "fail"}},                   # verify
    "issue_mismatch": {"kind": "incorrect", "expect": {"invariant.issue_identity": "fail"}},                            # issue
    "full_record": {"kind": "pitfall", "pitfall": "full_record", "expect": {"variant": "fail", "probe.held_out_year_isolation": "fail"}},
    "cached": {"kind": "incorrect", "expect": {"probe.changed_data": "fail"}},
}
NOT_APPLICABLE = {}


def build(name, inputs, params, destination):
    destination = Path(destination).resolve()
    inputs = Path(inputs).resolve()
    destination.mkdir(parents=True)
    for source in (HERE / "solve.py", HERE.parent / "science.py", HERE.parent / "reference_independent.py"):
        shutil.copyfile(source, destination / source.name)
    (destination / "variant.json").write_text(json.dumps({"defect": name}) + "\n")
    spec = importlib.util.spec_from_file_location("outlook_control_acquisition", HERE.parent / "acquisition.py")
    acquisition = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(acquisition)
    scratch = destination.parent / "initial-acquisition"
    result = acquisition.AcquisitionLocal().run(destination, inputs,
        ["python", "solve.py", "--inputs", "{input_dir}", "--output", "{output_dir}"], scratch, seconds=1800)
    if result["exit_code"] != 0:
        raise RuntimeError("Initial outlook control failed: " + result.get("stderr", ""))
    output = Path(result["output"])
    for name_ in ("results.zarr", "answer.json", "report.md"):
        source, target = output / name_, destination / name_
        shutil.copytree(source, target) if source.is_dir() else shutil.copyfile(source, target)
    if name == "cached":
        shutil.copytree(destination / "results.zarr", destination / "cached-results.zarr")
        shutil.copyfile(destination / "answer.json", destination / "cached-answer.json")
        shutil.copyfile(destination / "report.md", destination / "cached-report.md")
    return destination
