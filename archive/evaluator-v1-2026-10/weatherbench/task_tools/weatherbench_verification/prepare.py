"""Recompute/audit existing frozen inputs; initial construction is explicit."""
from pathlib import Path
import hashlib
import json
import shutil
import numpy as np
import xarray as xr

from .reference import build,independent

TASK="weatherbench-verification"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(repo=None,initialize=False):
    repo=Path(repo) if repo is not None else Path(__file__).resolve().parents[3]
    private=repo/"var/private/tasks"/TASK
    controller,inputs=private/"controller",private/"agent-inputs"
    expected=build(inputs)
    other=independent(inputs)
    maximum={}
    for k in other.data_vars:
        a,b=expected[k].values,other[k].transpose(*expected[k].dims).values
        np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-10,equal_nan=True)
        maximum[k]=float(np.nanmax(abs(a-b)))
    target=controller/"scores.nc"
    if initialize:
        if target.exists():
            raise ValueError("Controller reference already exists")
        expected.to_netcdf(target)
    else:
        with xr.open_dataset(target) as frozen:
            xr.testing.assert_allclose(expected,frozen,rtol=1e-12,atol=1e-12)
    audit={"task":TASK,"source_weather_is_synthetic":False,
           "reference_methods":["NumPy exact spherical area sums","independent labeled xarray reductions with equivalent cosine weights"],
           "maximum_absolute_crosscheck_errors":maximum,
           "reference_agreement":True,"published_annual_scores_reproduced":False,
           "undefined_climatology_acc":bool(np.isnan(expected.acc.sel(system="climatology")).all()),
           "cases":20,"leads":4,"native_grid":[64,32],"training":False,
           "human_scientific_approval":False,"human_judge_labels":False}
    if initialize:
        (controller/"reference-audit.json").write_text(json.dumps(audit,indent=2)+"\n")
        write_manifest(repo,private)
    return audit


def write_manifest(repo,private):
    package=repo/"tasks"/TASK
    rows=[]
    for path in sorted(private.rglob("*")):
        if not path.is_file():continue
        relative=str(path.relative_to(private))
        row={"file":relative,"sha256":digest(path),"bytes":path.stat().st_size,
             "visibility":"agent" if relative.startswith("agent-inputs/") else "controller_only"}
        if path.suffix==".nc":
            with xr.open_dataset(path) as ds:
                row["dimensions"]=dict(ds.sizes)
                row["variables"]={k:{"dimensions":list(v.dims),"units":v.attrs.get("units")} for k,v in ds.data_vars.items()}
        rows.append(row)
    code=repo/"weatherbench/task_tools/weatherbench_verification/reference.py"
    sourcepaths=[p for p in package.rglob("*") if p.is_file() and p.name not in ("input-manifest.json","review.html")]
    manifest={"schema_version":1,"task":TASK,"status":"local_development_snapshot",
              "local_storage":str(private.relative_to(repo)),"files":rows,
              "reference_code_path":str(code.relative_to(repo)),"reference_code_sha256":digest(code),
              "reference_validation":"Independent NumPy/xarray crosscheck on every case/region/lead; real public source chunks hashed; known-correct and constructed-fault controls",
              "source_records":[{"path":str(p.relative_to(repo)),"sha256":digest(p)} for p in sorted(sourcepaths)]}
    (package/"input-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("--initialize",action="store_true")
    print(json.dumps(prepare(initialize=parser.parse_args().initialize),indent=2))
