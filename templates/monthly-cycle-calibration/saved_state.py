"""Template-owned saved-inference instrument, wrapping the existing executor.

Actor code always runs through the supplied Docker executor (Local only for
trusted controls). Private targets never enter the actor stage. A separate
controller FFT/scalar reference checks each production field after changing SST.
Rejected raw outputs remain untouched in scratch; the generic probe receives an
empty deciding-output folder and the explicit independent rejection diagnostic.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import yaml
from assessment.compare import align,compare,read_results,tolerance
from assessment.execute import valid_argv
from assessment.storage import digest,inventory,write

HERE=Path(__file__).resolve().parent
PRIVATE=HERE.parents[1]/"var/private/templates/monthly-cycle-calibration"


def load(name):
    spec=importlib.util.spec_from_file_location("saved_monthly_"+name,HERE/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SavedStateExecutor:
    def __init__(self,base):
        self.base=base
        self.name=base.name+"+monthly-saved-state"

    def run(self,submission,inputs,argv,scratch,seconds=120):
        submission,inputs,scratch=map(Path,(submission,inputs,scratch))
        if not (inputs/"saved-inference.json").is_file():
            return self.base.run(submission,inputs,argv,scratch,seconds)
        scratch.mkdir(parents=True,exist_ok=False)
        sanitized=scratch/"target-free-submission"
        diagnosis={"instrument":"saved_state_prediction","state":"fail","actor_raw_outputs_modified":False,
                   "private_targets_mounted":False,"removed_known_target_and_result_files":True}
        record=None
        try:
            inventory(submission)  # Reject links/special files before copying.
            shutil.copytree(submission,sanitized,symlinks=True)
            for file in list(sanitized.rglob("*")):
                if file.name in ("targets.nc","hindcasts.nc","results.zarr"):
                    shutil.rmtree(file) if file.is_dir() else file.unlink()
            answer=json.loads((submission/"answer.json").read_text())
            model=answer["model_path"]
            if not isinstance(model,str) or Path(model).is_absolute() or ".." in Path(model).parts or not (sanitized/model).exists():
                raise ValueError("model_path must name retained fitted state inside the submission")
            command=answer["predict"]["argv"]
            if not valid_argv(command) or not any("{model_path}" in arg for arg in command):
                raise ValueError("predict.argv needs {input_dir}, {output_dir} and {model_path}")
            command=[arg.replace("{model_path}",model) for arg in command]
            record=self.base.run(sanitized,inputs,command,scratch/"actor",seconds)
            if record.get("infrastructure_unavailable"):
                diagnosis.update(state="unresolved",reason="Actor executor infrastructure unavailable")
                write(scratch/"saved-state-decision.json",diagnosis)
                return record
            if record.get("crashed_by_signal") and not (Path(record["output"])/"results.zarr").is_dir():
                diagnosis.update(state="unresolved",reason="Actor runtime crashed before producing results")
                write(scratch/"saved-state-decision.json",diagnosis)
                return record
            names=load("envelope").PRODUCTION
            original=yaml.safe_load((HERE/"spec.yaml").read_text())["results"]
            keys=set(names)|{dim for name in names for dim in original[name].get("dims",[])}
            spec={name:{**row,"tolerance":{**row["tolerance"],"atol":tolerance(row["tolerance"])}}
                  for name,row in original.items() if name in keys}
            actual,problems=read_results(spec,None,store=Path(record["output"])/"results.zarr")
            if problems:
                raise ValueError("Saved prediction output: "+json.dumps(problems,sort_keys=True))
            try:
                expected=load("reference_independent").reference(inputs,target_path=PRIVATE/"agent-inputs/targets.nc")
            except OSError as error:
                diagnosis.update(state="unresolved",reason="Controller cannot read its independent-reference inputs: "+str(error))
                write(scratch/"saved-state-decision.json",diagnosis)
                return {**record,"infrastructure_unavailable":True,"stderr":diagnosis["reason"]}
            frame={name:expected[name] for name,row in spec.items() if row.get("kind")=="coordinate"}
            actual=align(spec,actual,frame)
            ok,details=compare(spec,actual,{name:expected[name] for name in spec})
            diagnosis.update(state="pass" if ok else "fail",numeric_fields=details,
                expected_targets_sha256=digest(PRIVATE/"agent-inputs/targets.nc"),
                expected_predictors_sha256=digest(inputs/"predictors.nc"),
                reference_implementation_sha256=digest(HERE/"reference_independent.py"),
                raw_actor_output=record["output"])
            if not ok:
                raise ValueError("Independent saved-state production mismatch: "+json.dumps(details,sort_keys=True))
        except (OSError,ValueError,KeyError,TypeError) as error:
            diagnosis["reason"]=str(error)
            guard=scratch/"controller-rejected-output"
            guard.mkdir()
            record={**(record or {}),"exit_code":1,"executor":self.name,"infrastructure_unavailable":False,
                    "output":str(guard),"answer":None,"crashed_by_signal":False,
                    "stderr":"Template saved-state instrument rejected inference: "+str(error),"stdout":""}
        write(scratch/"saved-state-decision.json",diagnosis)
        return record
