import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTROLS = {
    "correct": {"kind": "known_correct", "expect": {}},
    "edge_geometry": {"kind": "known_correct", "expect": {}, "note": "Compute longitude width from pixel edges; equivalent algebra must survive cancellation roundoff."},
    "full_training": {"kind": "pitfall", "pitfall": "full_training", "expect": {"variant": "fail", "probe.held_out_year_isolation": "fail"}},
    "break_conservation": {"kind": "incorrect", "expect": {"variant": "unresolved", "probe.changed_data": "unresolved", "invariant.conservation": "fail"}},
    "negative": {"kind": "incorrect", "expect": {"variant": "unresolved", "probe.changed_data": "unresolved", "invariant.conservation": "fail", "invariant.nonnegative": "fail"}},
    "false_claim": {"kind": "incorrect", "expect": {"claim.raw_unit_status": "fail"}},
    "cached": {"kind": "incorrect", "expect": {"probe.changed_data": "fail"}},
}
NOT_APPLICABLE = {"optimized_forecast": "This task prescribes a specific mapping; skill optimization is a separate task."}


def build(name, inputs, params, destination):
    destination = Path(destination)
    destination.mkdir(parents=True)
    for source in (HERE / "solve.py", HERE.parent / "science.py"):
        shutil.copyfile(source, destination / source.name)
    if name == "edge_geometry":
        science = destination / "science.py"
        text = science.read_text()
        assert text.count("np.deg2rad(.05)") == 1
        science.write_text(text.replace("np.deg2rad(.05)", "np.deg2rad((lon+.025)-(lon-.025))[None,:]"))
    (destination / "variant.json").write_text(json.dumps({"defect": name if name not in ("correct", "cached") else None}))
    subprocess.run([sys.executable, "solve.py", "--inputs", str(inputs), "--output", str(destination)], cwd=destination, check=True, capture_output=True, text=True)
    if name == "cached":
        shutil.copytree(destination / "results.zarr", destination / "cached-results.zarr")
        shutil.copyfile(destination / "answer.json", destination / "cached-answer.json")
        (destination / "cached.py").write_text("import argparse,shutil\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--inputs');p.add_argument('--output');a=p.parse_args();o=Path(a.output);o.mkdir(parents=True,exist_ok=True);shutil.copytree('cached-results.zarr',o/'results.zarr');shutil.copyfile('cached-answer.json',o/'answer.json')\n")
        answer = json.loads((destination / "answer.json").read_text())
        answer["run"]["argv"][1] = "cached.py"
        (destination / "answer.json").write_text(json.dumps(answer))
    return destination
