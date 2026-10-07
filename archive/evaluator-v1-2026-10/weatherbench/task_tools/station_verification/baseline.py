"""Executable curator control and consequential defects; no human judge labels."""
from pathlib import Path
import inspect
import json
import shutil
import subprocess
import sys
import numpy as np
import xarray as xr
from . import reference
from .checks import answer_from, submission_checks, comparison
from .prepare import digest
from .evaluation import change_inputs


def controls(repo=None):
    repo=Path(repo) if repo else Path(__file__).resolve().parents[3]
    private=repo/"var/private/tasks/station-verification"
    audit=repo/"var/calibration/station-verification";audit.mkdir(parents=True,exist_ok=True)
    positive=audit/"correct"
    if positive.exists():shutil.rmtree(positive)
    positive.mkdir();shutil.copytree(private/"agent-inputs",positive/"retained")
    script=Path(reference.__file__).read_text()+"\n"+inspect.getsource(answer_from)+'''
if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("--inputs",required=True);parser.add_argument("--outputs",required=True)
    args=parser.parse_args();out=Path(args.outputs);out.mkdir(parents=True,exist_ok=True)
    scores=build(args.inputs);scores.to_netcdf(out/"scores.nc")
    (out/"answer.json").write_text(json.dumps(answer_from(scores),indent=2,allow_nan=False)+"\\n")
'''
    (positive/"workflow.py").write_text(script)
    subprocess.run([sys.executable,str(positive/"workflow.py"),"--inputs",str(positive/"retained"),"--outputs",str(positive)],check=True)
    with xr.open_dataset(positive/"scores.nc") as src:scores=src.load()
    (positive/"execution.json").write_text(json.dumps({"schema_version":1,"replay":{"argv":["python","workflow.py","--inputs","{input_dir}","--outputs","{output_dir}"]},"retained_files":["workflow.py"],"dependencies":["numpy, xarray, scipy: supplied pinned runtime"]},indent=2)+"\n")
    (positive/"report.txt").write_text("Curator known-correct numerical control, not an autonomous attempt or expert approval. Real NOAA ISD instantaneous station temperature and real HRES coarse-grid forecasts; source-backed WeatherReal-inspired 2020 adaptation, not native 2023 rank reproduction. Exact UTC station matching; strict real flags 1/5 and +9999 rejection; FM-12 then FM-15 then FM-16 source-row tie break; tenths Celsius converted to Kelvin. Same-method common support and pooled station-sample MSE before square root. Arua has no exact midnight support, so station RMSE stays undefined. Equal-station sensitivity exposes uneven station coverage. Mask and time/unit/support faults are deliberately constructed. Short January airport sample, coarse-grid/elevation mismatch, duplicate reports and variable station coverage constrain representativeness. Paired bilinear/nearest comparisons share forecasts, stations and observations; overlapping valid dates and temporal/spatial dependence preclude treating all observation samples as independent. Physical mechanisms and generalized model rank cannot be established by these scores. Expert uncertainty reasoning remains pending human review.\n")
    (positive/"handoff.txt").write_text("Offline: python workflow.py --inputs retained --outputs fresh-output. Read alternate input_dir to rerun. No network, fitting or training.\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots()
    for method in ["bilinear","nearest"]:
        ax.plot([24,72,120,168],scores.rmse.sel({"method":method}),marker="o",label=method)
    ax.set(xlabel="Forecast lead (hours)",ylabel="Common station-sample RMSE (K)",title="Actual East Africa ISD observations; January 2020")
    ax.legend();fig.tight_layout();fig.savefig(positive/"outlook.png");plt.close(fig)
    sources=["weatherreal-paper","weatherreal-code","noaa-isd","weatherbench2-hres"]
    files=[{"path":str(p.relative_to(positive)),"sha256":digest(p),"source_ids":sources if str(p.relative_to(positive)).startswith("retained/") else []} for p in sorted(positive.rglob("*")) if p.is_file()]
    provenance={"schema_version":1,"sources":[{"id":s,"product_version":"Frozen station-verification development subset and pinned source context","access":"supplied","request":{"source":s},"retrieved_at":None} for s in sources],"files":files,
                "transformations":[{"operation":"Offline exact-time QC station matching, bilinear/nearest interpolation, common support and fault isolation","inputs":["retained/hres.nc","retained/observations.csv","retained/stations.json","retained/availability.nc"],"outputs":["scores.nc","answer.json"],"parameters":{"units":"K","truth":"NOAA ISD","support":"all-method intersection","rmse":"pooled station-sample MSE square root","constructed_availability":True}}]}
    (positive/"provenance.json").write_text(json.dumps(provenance,indent=2)+"\n")
    results={"correct":submission_checks(positive,private)}
    def refresh(dest):
        path=dest/"provenance.json";value=json.loads(path.read_text())
        for row in value["files"]:row["sha256"]=digest(dest/row["path"])
        path.write_text(json.dumps(value,indent=2)+"\n")
    for variant in ("init-time-truth","celsius-as-kelvin","own-support"):
        dest=audit/variant
        if dest.exists():shutil.rmtree(dest)
        shutil.copytree(positive,dest);wrong=scores.copy(deep=True)
        wrong.rmse.values[:]=scores.diagnostic_rmse.sel(variant=variant).values
        wrong.to_netcdf(dest/"scores.nc",mode="w")
        (dest/"answer.json").write_text(json.dumps(answer_from(wrong),indent=2,allow_nan=False)+"\n")
        refresh(dest);results[variant]=submission_checks(dest,private)
    cached=audit/"cached-replay"
    if cached.exists():shutil.rmtree(cached)
    shutil.copytree(positive,cached)
    (cached/"workflow.py").write_text('import argparse,shutil\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument("--inputs");p.add_argument("--outputs");a=p.parse_args();o=Path(a.outputs);o.mkdir(parents=True,exist_ok=True)\nfor n in ("scores.nc","answer.json"):shutil.copy2(n,o/n)\n')
    refresh(cached);results["cached-replay"]=submission_checks(cached,private)
    probe=audit/"changed-inputs"
    if probe.exists():shutil.rmtree(probe)
    shutil.copytree(private/"agent-inputs",probe);change_inputs(probe)
    expected=reference.independent(probe);expected.to_netcdf(audit/"changed-reference.nc")
    replay=audit/"changed-control-output"
    if replay.exists():shutil.rmtree(replay)
    subprocess.run([sys.executable,str(positive/"workflow.py"),"--inputs",str(probe),"--outputs",str(replay)],check=True)
    with xr.open_dataset(replay/"scores.nc") as actual:ok,detail=comparison(actual,expected)
    # Score and answer validation against the independent changed reference.
    changed_private=audit/"changed-controller";changed_private.mkdir(exist_ok=True)
    expected.to_netcdf(changed_private/"scores.nc")
    changed_checks=submission_checks(replay,changed_private)
    audit_record={"task":"station-verification","fixture_controls":True,"human_labels":False,"judge_calls":0,
                  "checks":results,"changed_input_replay":{"passed":ok and all(v["state"]=="pass" for v in changed_checks.values()),"detail":detail,"checks":changed_checks,
                  "maximum_rmse_change_K":float(abs(expected.rmse-scores.rmse).max()),"mask_changes":int((expected.common_support!=scores.common_support).sum()),
                  "cached_output_rejected":not comparison(scores,expected)[0]}}
    (audit/"static-control-results.json").write_text(json.dumps(audit_record,indent=2)+"\n")
    assert all(v["state"]=="pass" for v in results["correct"].values())
    assert all(results[v]["metric_values"]["state"]=="fail" for v in ("init-time-truth","celsius-as-kelvin","own-support"))
    assert audit_record["changed_input_replay"]["passed"] and audit_record["changed_input_replay"]["cached_output_rejected"]
    return audit

if __name__=="__main__":print(controls())
