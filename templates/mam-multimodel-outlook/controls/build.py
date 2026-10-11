"""Controls obtain initial answers through the same HTTP catalogue as agents."""
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
CONTROLS = {
    "correct": {"kind": "known_correct", "expect": {}},
    "independent": {"kind": "known_correct", "expect": {}},
    "reordered": {"kind": "accepted_alternative", "expect": {}},
    "thirty_days": {"kind": "pitfall", "pitfall": "thirty_days", "expect": {"variant": "fail"}},
    "full_record_thresholds": {"kind": "pitfall", "pitfall": "full_record_thresholds", "expect": {"variant": "fail", "probe.held_out_year_isolation": "fail"}},
    "member_weighted": {"kind": "pitfall", "pitfall": "member_weighted", "expect": {"variant": "fail", "invariant.equal_model_combination": "fail"}},
    "missing_seconds": {"kind": "pitfall", "pitfall": "missing_seconds", "expect": {"variant": "fail"}},
    "missing_millimetres": {"kind": "pitfall", "pitfall": "missing_millimetres", "expect": {"variant": "fail"}},
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
    spec = importlib.util.spec_from_file_location("mam_control_acquisition", HERE.parent / "acquisition.py")
    acquisition = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(acquisition)
    scratch = destination.parent / "initial-acquisition"
    result = acquisition.AcquisitionLocal().run(destination, inputs,
        ["python", "solve.py", "--inputs", "{input_dir}", "--output", "{output_dir}"], scratch, seconds=180)
    if result["exit_code"] != 0:
        raise RuntimeError("Initial MAM control failed: " + result.get("stderr", ""))
    output = Path(result["output"])
    for name_ in ("results.zarr", "answer.json", "report.md"):
        source, target = output / name_, destination / name_
        shutil.copytree(source, target) if source.is_dir() else shutil.copyfile(source, target)
    if name == "cached":
        shutil.copytree(destination / "results.zarr", destination / "cached-results.zarr")
        shutil.copyfile(destination / "answer.json", destination / "cached-answer.json")
        shutil.copyfile(destination / "report.md", destination / "cached-report.md")
    return destination
