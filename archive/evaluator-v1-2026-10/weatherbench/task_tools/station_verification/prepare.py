"""Audit frozen station inputs without downloading; initialization is explicit."""
from pathlib import Path
import hashlib
import json
import numpy as np
import xarray as xr
from .reference import build, independent

TASK="station-verification"
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(repo=None,initialize=False):
    repo=Path(repo) if repo else Path(__file__).resolve().parents[3]
    private=repo/"var/private/tasks"/TASK;controller=private/"controller";inputs=private/"agent-inputs"
    gold=build(inputs);other=independent(inputs);maximum={}
    for name in gold.data_vars:
        np.testing.assert_allclose(gold[name],other[name],atol=1e-11,rtol=1e-11,equal_nan=True)
        finite=np.isfinite(gold[name].values)&np.isfinite(other[name].values)
        maximum[name]=float(abs(gold[name].values[finite]-other[name].values[finite]).max()) if finite.any() else 0.0
    manifest=json.loads((inputs/"source-manifest.json").read_text())
    for source in manifest["station_sources"]:
        if digest(private/source["controller_file"])!=source["source_sha256"]:raise ValueError("Original NOAA source changed")
    if digest(inputs/"hres.nc")!=manifest["forecast_source"]["sha256"]:raise ValueError("Original HRES subset changed")
    if initialize:
        if (controller/"scores.nc").exists():raise ValueError("Controller reference already exists")
        gold.to_netcdf(controller/"scores.nc")
    else:
        with xr.open_dataset(controller/"scores.nc") as frozen:xr.testing.assert_allclose(gold,frozen,atol=1e-12,rtol=1e-12)
    audit={"task":TASK,"reference_agreement":True,"source_weather_is_synthetic":False,
           "reference_methods":["Original-field CSV parser, literal bilinear weights, explicit pooled station sums", "Independent CSV selection, SciPy RegularGridInterpolator and labeled xarray reductions"],
           "maximum_absolute_crosscheck_errors":maximum,"public_download_bytes":manifest["public_download_bytes"],
           "stations":int(gold.sizes["station"]),"zero_support_stations":[s for s in gold.station.values.tolist() if int(gold.station_count.sel(station=s).sum())==0],
           "station_sample_counts":gold.station_count.values.tolist(),"native_forecast_grid":[64,32],"cases":20,"leads":4,
           "published_scores_reproduced":False,"method_adaptation":True,"constructed_faults":True,"constructed_availability":True,
           "training":False,"human_scientific_approval":False,"human_judge_labels":False}
    if initialize:
        (controller/"reference-audit.json").write_text(json.dumps(audit,indent=2)+"\n")
        write_manifest(repo,private)
    return audit


def write_manifest(repo,private):
    package=repo/"tasks"/TASK;rows=[]
    for path in sorted(private.rglob("*")):
        if not path.is_file():continue
        relative=str(path.relative_to(private))
        row={"file":relative,"sha256":digest(path),"bytes":path.stat().st_size,"visibility":"agent" if relative.startswith("agent-inputs/") else "controller_only"}
        if path.suffix==".nc":
            with xr.open_dataset(path) as ds:
                row["dimensions"]=dict(ds.sizes)
                row["variables"]={k:{"dimensions":list(v.dims),"units":v.attrs.get("units")} for k,v in ds.data_vars.items()}
        rows.append(row)
    code=repo/"weatherbench/task_tools/station_verification"
    sourcepaths=[p for p in package.rglob("*") if p.is_file() and p.name not in ("input-manifest.json","review.html")]
    record={"schema_version":1,"task":TASK,"status":"local_development_snapshot","local_storage":str(private.relative_to(repo)),"files":rows,
            "reference_code_path":str((code/"reference.py").relative_to(repo)),"reference_code_sha256":digest(code/"reference.py"),
            "reference_validation":"Independent NOAA parsing, grid-to-station interpolation and all case/station/lead score arrays crosschecked; consequential controls and changed-input mask/value probe",
            "code_records":[{"path":str(p.relative_to(repo)),"sha256":digest(p)} for p in sorted(code.glob("*.py"))],
            "source_records":[{"path":str(p.relative_to(repo)),"sha256":digest(p)} for p in sorted(sourcepaths)]}
    (package/"input-manifest.json").write_text(json.dumps(record,indent=2)+"\n")

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--initialize",action="store_true")
    print(json.dumps(prepare(initialize=p.parse_args().initialize),indent=2))
