"""Trusted planted faults: unit metadata and numerical groups stay separate."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
CONTROLS={
    "correct":{"kind":"known_correct","expect":{}},
    "wrong_production":{"kind":"incorrect","expect":{"variant":"unresolved","invariant.production":"fail","probe.changed_data":"unresolved","probe.saved_state_prediction":"fail"}},
    "missing_units":{"kind":"incorrect","expect":{"claim.rainfall_units":"fail"}},
    "missing_units_and_wrong_production":{"kind":"incorrect","expect":{"variant":"unresolved","invariant.production":"fail","claim.rainfall_units":"fail","probe.changed_data":"unresolved","probe.saved_state_prediction":"fail"}},
    "saved_model_needs_observations":{"kind":"incorrect","expect":{"probe.saved_state_prediction":"fail"}},
    "cached_inference":{"kind":"incorrect","expect":{"probe.saved_state_prediction":"fail"}},
    "cached":{"kind":"incorrect","expect":{"probe.changed_data":"fail","probe.saved_state_prediction":"fail"}},
    "month_only_year_leak":{"kind":"incorrect","expect":{"variant":"unresolved","invariant.fitted":"fail","invariant.verification":"fail","probe.changed_data":"unresolved","probe.whole_year_isolation":"fail"}},
}
NOT_APPLICABLE={"optimized_forecast":"A fixed procedure is reproduced; positive rainfall forecasting skill is not a completion gate."}


def build(name,inputs,params,destination):
    destination=Path(destination)
    destination.mkdir(parents=True)
    for source in (HERE/"solve.py",HERE.parent/"science.py",HERE.parent/"envelope.py"):
        shutil.copyfile(source,destination/source.name)
    (destination/"variant.json").write_text(json.dumps({"variant":name})+"\n")
    done=subprocess.run([sys.executable,"solve.py","--inputs",str(inputs),"--output",str(destination)],
                        cwd=destination,capture_output=True,text=True,check=True)
    if name=="cached":
        shutil.copytree(destination/"results.zarr",destination/"cached-results.zarr")
        shutil.copyfile(destination/"answer.json",destination/"cached-answer.json")
    return destination
