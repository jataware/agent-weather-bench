"""Construct numerical positive/defect controls; never solver or human labels."""
from pathlib import Path
import inspect
import json
import shutil
import numpy as np
import xarray as xr

from .checks import answer_from,submission_checks
from . import reference
from .prepare import digest


def controls(repo=None):
    repo=Path(repo) if repo else Path(__file__).resolve().parents[3]
    private=repo/"var/private/tasks/weatherbench-verification"
    audit=repo/"var/calibration/weatherbench-verification-controls"
    audit.mkdir(parents=True,exist_ok=True)
    positive=audit/"correct"
    if positive.exists():shutil.rmtree(positive)
    positive.mkdir();shutil.copytree(private/"agent-inputs",positive/"retained")
    with xr.open_dataset(private/"controller/scores.nc") as source:scores=source.load()
    scores.to_netcdf(positive/"scores.nc")
    (positive/"answer.json").write_text(json.dumps(answer_from(scores),indent=2,allow_nan=False)+"\n")
    script=Path(reference.__file__).read_text()+"\nimport json\n"+inspect.getsource(answer_from)+'''
if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",required=True);parser.add_argument("--outputs",required=True)
    args=parser.parse_args();out=Path(args.outputs);out.mkdir(parents=True,exist_ok=True)
    scores=build(args.inputs);scores.to_netcdf(out/"scores.nc")
    (out/"answer.json").write_text(json.dumps(answer_from(scores),indent=2,allow_nan=False)+"\\n")
'''
    (positive/"workflow.py").write_text(script)
    (positive/"execution.json").write_text(json.dumps({"schema_version":1,"replay":{"argv":["python","workflow.py","--inputs","{input_dir}","--outputs","{output_dir}"]},"retained_files":["workflow.py"],"dependencies":["numpy and xarray: supplied content-pinned runtime"]},indent=2)+"\n")
    (positive/"report.txt").write_text("Constructed known-correct numerical control, not an autonomous attempt or expert-approved scientific interpretation. Real retrospective ERA5/HRES/climatology temperature fields. Comparison faults and availability mask explicitly curator-created. Spherical common-support MSE averaged over cases before square root; per-case ACC averaged over time; climatology ACC undefined. This January subset cannot reproduce annual rankings. No pristine holdout or station truth. Paired uncertainty interpretation remains a human/expert-review item.\n")
    (positive/"handoff.txt").write_text("Offline: python workflow.py --inputs retained --outputs new-output. Controller may supply alternative inputs.\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots()
    for s in reference.SYSTEMS:ax.plot([24,72,120,168],scores.rmse.sel(system=s,region="global"),label=s)
    ax.set(xlabel="Lead (hours)",ylabel="Global common-support RMSE (K)");ax.legend();fig.tight_layout();fig.savefig(positive/"outlook.png");plt.close(fig)
    needed=json.loads((private/"agent-inputs/source-manifest.json").read_text())["sources"]
    records=[{"path":str(p.relative_to(positive)),"sha256":digest(p),"source_ids":needed if str(p.relative_to(positive)).startswith("retained/") else []} for p in sorted(positive.rglob("*")) if p.is_file()]
    provenance={"schema_version":1,"sources":[{"id":s,"product_version":"Frozen WeatherBench2 development subset and pinned source context","access":"supplied","request":{"source":s},"retrieved_at":None} for s in needed],"files":records,"transformations":[{"operation":"Offline common-support verification and controlled comparison-fault isolation","inputs":["retained/hres.nc","retained/era5.nc","retained/climatology.nc","retained/availability.nc"],"outputs":["scores.nc","answer.json"],"parameters":{"units":"K","area":"spherical cell bounds","valid_time":"init+lead","support":"all-system intersection","rmse":"sqrt time-mean caseMSE","acc":"time-mean spatialACC"}}]}
    (positive/"provenance.json").write_text(json.dumps(provenance,indent=2)+"\n")
    results={"correct":submission_checks(positive,private)}
    def refresh_hashes(dest):
        path=dest/"provenance.json"
        record=json.loads(path.read_text())
        for entry in record["files"]:entry["sha256"]=digest(dest/entry["path"])
        path.write_text(json.dumps(record,indent=2)+"\n")
    for variant in ("init-time-truth","uniform-weight","own-support"):
        dest=audit/variant
        if dest.exists():shutil.rmtree(dest)
        shutil.copytree(positive,dest)
        wrong=scores.copy(deep=True)
        wrong.rmse.values[:]=scores.diagnostic_rmse.sel(variant=variant).values
        wrong.to_netcdf(dest/"scores.nc",mode="w")
        (dest/"answer.json").write_text(json.dumps(answer_from(wrong),indent=2,allow_nan=False)+"\n")
        refresh_hashes(dest)
        results[variant]=submission_checks(dest,private)
    cached=audit/"cached-replay"
    if cached.exists():shutil.rmtree(cached)
    shutil.copytree(positive,cached)
    (cached/"workflow.py").write_text('import argparse,shutil\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument("--inputs");p.add_argument("--outputs");a=p.parse_args();o=Path(a.outputs);o.mkdir(parents=True,exist_ok=True)\nfor n in ("scores.nc","answer.json"):shutil.copy2(n,o/n)\n')
    refresh_hashes(cached)
    results["cached-replay"]=submission_checks(cached,private)
    (audit/"static-control-results.json").write_text(json.dumps({"task":"weatherbench-verification","fixture_controls":True,"human_labels":False,"judge_calls":0,"checks":results},indent=2)+"\n")
    return audit


if __name__=="__main__":print(controls())
