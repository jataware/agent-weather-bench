"""Trusted original/changed-input replay, with private independent scoring."""
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
    trusted=destination/"_controller_inputs"
    shutil.copytree(inputs,trusted)
    return trusted


def change_inputs(inputs):
    """Deliberate verification-sensitivity probe, not a forecast skill target."""
    inputs=Path(inputs)
    path=inputs/"hres.nc"
    with xr.open_dataset(path) as source:
        changed=source.load()
    changed.temperature.values[2:7,1,10:20,15:30] += 3.25
    changed.to_netcdf(path,mode="w")
    path=inputs/"availability.nc"
    with xr.open_dataset(path) as source:
        changed=source.load()
    changed.available.values[0,4:9,2,12:22,20:40]=0
    changed.to_netcdf(path,mode="w")


def matching(actual,expected):
    with xr.open_dataset(Path(actual)/"scores.nc") as a,xr.open_dataset(Path(expected)/"scores.nc") as b:
        passed,detail=comparison(a,b)
    answer=submission_checks(actual,expected)
    passed &= answer["answer_schema"]["state"]=="pass" and answer["answer_metrics"]["state"]=="pass"
    return passed,detail+"; regenerated answer schema and numerical metrics checked"


def evaluate(run,output):
    run,output=Path(run),Path(output)
    config=read(run/"system.json");frozen=run/"frozen"
    if inventory(frozen)!=read(run/"artifacts.json"):
        raise ValueError("Frozen submission changed")
    from weatherbench.task_tools.checks import check
    result={"static":check("weatherbench-verification",frozen),"integrity":read(run/"controller/integrity.json"),
            "replay":{"state":"unresolved","passed":False},"counterfactual":{"state":"unresolved","passed":False},
            "prediction":{"state":"not_applicable","passed":True},"acquisition":{"state":"not_applicable","passed":True},"forecast_outcomes":{}}
    output.mkdir(parents=True,exist_ok=True)
    try:
        manifest=json.loads((frozen/"execution.json").read_text())
        argv=manifest["replay"]["argv"]
        if not isinstance(argv,list) or not argv or not all(isinstance(a,str) for a in argv):
            raise ValueError("replay.argv must be a nonempty string array")
        if not all(any(p in a for a in argv) for p in ("{input_dir}","{output_dir}")):
            raise ValueError("replay.argv needs {input_dir} and {output_dir}")
        actual=[a.replace("{input_dir}","/work/_controller_inputs").replace("{output_dir}","/output") for a in argv]
        def execute(stagepath,outpath):
            record=offline(config["runtime"]["image"],stagepath,outpath,actual,
                           seconds=config["budget"]["command_seconds"],memory=config["runtime"]["memory"],cpus=config["runtime"]["cpus"])
            if record.get("infrastructure_unavailable"):
                raise InfrastructureUnavailable(record.get("stderr","Docker unavailable"))
            return record
        private=PRIVATE/"weatherbench-verification"
        replay_stage=output/"replay-stage";stage(frozen,replay_stage,private/"agent-inputs")
        replay=execute(replay_stage,output/"replay")
        ok,detail=matching(output/"replay",frozen) if replay["exit_code"]==0 else (False,replay.get("stderr","Replay failed"))
        replay.update(state="pass" if ok else "fail",passed=ok,detail=detail);result["replay"]=replay
        probe_stage=output/"counterfactual-stage";probe=stage(frozen,probe_stage,private/"agent-inputs");change_inputs(probe)
        expected=output/"counterfactual-reference";expected.mkdir();build(probe).to_netcdf(expected/"scores.nc")
        counter=execute(probe_stage,output/"counterfactual")
        ok,detail=matching(output/"counterfactual",expected) if counter["exit_code"]==0 else (False,counter.get("stderr","Replay failed"))
        counter.update(state="pass" if ok else "fail",passed=ok,detail=detail,
                       probe="Controller changes actual HRES slice and supplied availability mask; independent metric recomputation")
        result["counterfactual"]=counter
    except InfrastructureUnavailable as e:
        for key in ("replay","counterfactual"):
            if result[key]["state"]=="unresolved":result[key]["detail"]="Infrastructure unavailable: "+str(e)
    except (OSError,ValueError,KeyError,TypeError) as e:
        for key in ("replay","counterfactual"):
            if result[key]["state"]=="unresolved":result[key].update(state="fail",passed=False,detail=str(e))
    (output/"controller-validation.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    return result
