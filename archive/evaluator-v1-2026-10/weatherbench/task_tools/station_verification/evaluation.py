"""Trusted original/changed-input offline execution, private station reference."""
from pathlib import Path
import json
import shutil
import xarray as xr
from weatherbench.runtime import offline, InfrastructureUnavailable
from weatherbench.storage import PRIVATE, inventory, read
from .reference import build
from .checks import comparison, submission_checks


def stage(frozen,destination,inputs):
    shutil.copytree(frozen,destination)
    trusted=destination/"_controller_inputs";shutil.copytree(inputs,trusted)
    return trusted


def change_inputs(inputs):
    """Change actual station-neighbor forecast values and explicit supplied mask."""
    inputs=Path(inputs)
    with xr.open_dataset(inputs/"hres.nc") as f:changed=f.load()
    # East Africa station interpolation stencil (lat -8.4..8.4, lon 28..45).
    changed.temperature.values[2:10,1,14:18,5:9]+=3.25
    changed.to_netcdf(inputs/"hres.nc",mode="w")
    with xr.open_dataset(inputs/"availability.nc") as a:changed=a.load()
    changed.available.values[0,10:14,0,3]=0
    changed.to_netcdf(inputs/"availability.nc",mode="w")


def matching(actual,expected):
    with xr.open_dataset(Path(actual)/"scores.nc") as a,xr.open_dataset(Path(expected)/"scores.nc") as b:ok,detail=comparison(a,b)
    answer=submission_checks(actual,expected)
    ok &= answer["answer_schema"]["state"]=="pass" and answer["answer_metrics"]["state"]=="pass"
    return ok,detail+"; regenerated answer schema and numerical metrics checked"


def evaluate(run,output):
    run,output=Path(run),Path(output);config=read(run/"system.json");frozen=run/"frozen"
    if inventory(frozen)!=read(run/"artifacts.json"):raise ValueError("Frozen submission changed")
    from weatherbench.task_tools.checks import check
    result={"static":check("station-verification",frozen),"integrity":read(run/"controller/integrity.json"),
            "replay":{"state":"unresolved","passed":False},"counterfactual":{"state":"unresolved","passed":False},
            "prediction":{"state":"not_applicable","passed":True},"acquisition":{"state":"not_applicable","passed":True},"forecast_outcomes":{}}
    output.mkdir(parents=True,exist_ok=True)
    try:
        argv=json.loads((frozen/"execution.json").read_text())["replay"]["argv"]
        if not isinstance(argv,list) or not argv or not all(isinstance(v,str) for v in argv):raise ValueError("replay.argv must be a nonempty string array")
        if not all(any(p in a for a in argv) for p in ("{input_dir}","{output_dir}")):raise ValueError("Replay needs input/output placeholders")
        actual=[a.replace("{input_dir}","/work/_controller_inputs").replace("{output_dir}","/output") for a in argv]
        def execute(stagepath,outpath):
            record=offline(config["runtime"]["image"],stagepath,outpath,actual,seconds=config["budget"]["command_seconds"],memory=config["runtime"]["memory"],cpus=config["runtime"]["cpus"])
            if record.get("infrastructure_unavailable"):raise InfrastructureUnavailable(record.get("stderr","Docker unavailable"))
            return record
        private=PRIVATE/"station-verification"
        replay_stage=output/"replay-stage";stage(frozen,replay_stage,private/"agent-inputs")
        replay=execute(replay_stage,output/"replay")
        ok,detail=matching(output/"replay",frozen) if replay["exit_code"]==0 else (False,replay.get("stderr","Replay failed"))
        replay.update(state="pass" if ok else "fail",passed=ok,detail=detail);result["replay"]=replay
        probe_stage=output/"counterfactual-stage";probe=stage(frozen,probe_stage,private/"agent-inputs");change_inputs(probe)
        expected=output/"counterfactual-reference";expected.mkdir();build(probe).to_netcdf(expected/"scores.nc")
        counter=execute(probe_stage,output/"counterfactual")
        ok,detail=matching(output/"counterfactual",expected) if counter["exit_code"]==0 else (False,counter.get("stderr","Replay failed"))
        counter.update(state="pass" if ok else "fail",passed=ok,detail=detail,probe="Controller modifies actual HRES East Africa stencil and supplied method availability mask; independent station reference recomputation")
        result["counterfactual"]=counter
    except InfrastructureUnavailable as e:
        for key in ("replay","counterfactual"):
            if result[key]["state"]=="unresolved":result[key]["detail"]="Infrastructure unavailable: "+str(e)
    except (OSError,ValueError,KeyError,TypeError) as e:
        for key in ("replay","counterfactual"):
            if result[key]["state"]=="unresolved":result[key].update(state="fail",passed=False,detail=str(e))
    (output/"controller-validation.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    return result
