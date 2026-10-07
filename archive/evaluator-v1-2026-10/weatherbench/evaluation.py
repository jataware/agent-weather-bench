"""Numerical checks, independent offline replay and frozen prediction evidence."""
import json
from pathlib import Path

import numpy as np

from .storage import PRIVATE, read, inventory, write
from .runtime import offline, InfrastructureUnavailable
from .task_tools.checks import check
from .task_tools.contracts import execution
from .task_tools.references import load, same_array, TERCILES
from .verification import development, scores
from .acquisition import assess_acquisition

ARRAYS = {"acmad-objective":{"objective.nc":["probability","nominal_weighted_probability","available_components","disagreement_pp"]},
          "wvg-definition-audit":{"indices.nc":["box_temperature_c","western_v_c","nino34_z","western_v_z","wvg"]},
          "seasonal-calibration":{"training.nc":["forecast","observed"],"development.nc":["probability","rainfall_mm"]}}
ANSWERS = {"acmad-objective":["supported_cells","fully_supported_cells","single_component_cells","maximum_weighting_difference_pp"],
           "wvg-definition-audit":["index_correlation","mean_absolute_difference","maximum_absolute_difference"],
           "seasonal-calibration":["method","development_validation","limitations"]}


def json_agreement(a,b):
    if type(a) in (int,float) and type(b) in (int,float): return bool(np.isfinite(a) and np.isfinite(b) and np.isclose(a,b,atol=1e-6,rtol=1e-6))
    if type(a) is not type(b): return False
    if isinstance(a,dict): return set(a)==set(b) and all(json_agreement(a[k],b[k]) for k in a)
    if isinstance(a,list): return len(a)==len(b) and all(json_agreement(x,y) for x,y in zip(a,b))
    return a==b


def replay_agreement(task,original,replayed):
    inventory(replayed)
    for filename,fields in ARRAYS[task].items():
        actual,expected = load(replayed / filename),load(original / filename)
        for field in fields:
            if not same_array(actual[field],expected[field]) or actual[field].attrs.get("units")!=expected[field].attrs.get("units"):
                return False
    actual,expected = read(replayed / "answer.json"),read(original / "answer.json")
    return all(k in actual and k in expected and json_agreement(actual[k],expected[k]) for k in ANSWERS[task])


def evaluate(run,output):
    meta,config = read(run / "run.json"),read(run / "system.json")
    frozen = run / "frozen"
    if inventory(frozen)!=read(run / "artifacts.json"): raise ValueError("Frozen submission changed")
    task = meta["task"]
    from .task_tools.prepare import TASK_MODULES
    if task in TASK_MODULES:
        from importlib import import_module
        module = import_module(f"weatherbench.task_tools.{TASK_MODULES[task]}.evaluation")
        return module.evaluate(run, output)
    result = {"static":check(task,frozen),"integrity":read(run / "controller/integrity.json"),
              "replay":{"state":"unresolved","passed":False},"prediction":{"state":"unresolved","passed":False},
              "acquisition":assess_acquisition(run) if task=="seasonal-calibration" else {"state":"unresolved","reason":"Acquisition is not required for supplied-input tasks"},"forecast_outcomes":{}}
    # Scientific verification remains inspectable when delivery/replay fails.
    if task=='seasonal-calibration' and result['static']['basic_validity']['development_schema']['state']=='pass':
        try:
            result['forecast_outcomes']['development']=development(load(frozen/'development.nc'),load(PRIVATE/task/'controller/training.nc'))
        except (OSError,ValueError,KeyError,RuntimeError,TypeError) as error:
            result['forecast_outcomes']['development_error']=str(error)[:1500]
    try:
        manifest = execution(frozen,needs_prediction=task=="seasonal-calibration")
    except (OSError,ValueError,TypeError,KeyError) as error:
        result["replay"].update(state="fail",reason=str(error))
        return result
    argv = [arg.replace("{output_dir}","/output") for arg in manifest["replay"]["argv"]]
    try:
        replay = offline(config["runtime"]["image"],frozen,output / "replay",argv,
                         seconds=config["budget"]["command_seconds"],memory=config["runtime"]["memory"],cpus=config["runtime"]["cpus"])
        replay["passed"] = replay["exit_code"]==0 and replay_agreement(task,frozen,output / "replay")
        replay["state"] = 'unresolved' if replay.get('infrastructure_unavailable') else ("pass" if replay["passed"] else "fail")
        result["replay"] = replay
    except InfrastructureUnavailable as error:
        result['replay'].update(state='unresolved',reason=str(error)[:1500],failure_origin='controller_infrastructure')
    except (OSError,ValueError,KeyError,RuntimeError,TypeError) as error:
        result["replay"].update(state="fail",reason=str(error)[:1500])
    if task=="seasonal-calibration":
        try:
            substitutions = {"{forecast_path}":"/inputs/forecast.nc","{output_path}":"/output/predictions.nc"}
            argv = manifest["predict"]["argv"]
            for key,value in substitutions.items(): argv=[arg.replace(key,value) for arg in argv]
            prediction = offline(config["runtime"]["image"],frozen,output / "prediction",argv,
                                 forecast=PRIVATE / task / "controller/forecast.nc",seconds=config["budget"]["command_seconds"],
                                 memory=config["runtime"]["memory"],cpus=config["runtime"]["cpus"])
            if prediction.get('infrastructure_unavailable'):
                raise InfrastructureUnavailable('Docker could not start saved-fit inference')
            inventory(output / "prediction")
            d = load(output / "prediction/predictions.nc")
            f = load(PRIVATE / task / "controller/forecast.nc")
            p,m = d.probability.transpose("year","tercile","lat","lon"),d.rainfall_mm.transpose("year","lat","lon")
            valid = (prediction["exit_code"]==0 and list(p.tercile.values)==TERCILES and m.attrs.get("units")=="mm"
                     and all(np.array_equal(p[c],f[c]) and np.array_equal(m[c],f[c]) for c in ("year","lat","lon"))
                     and bool(np.isfinite(p).all() and np.isfinite(m).all() and (m>=0).all() and (p>=0).all() and (p<=1).all())
                     and bool(np.allclose(p.sum("tercile"),1,atol=1e-6,rtol=0)))
            prediction.update(passed=valid,state="pass" if valid else "fail",saved_fit_behavior="Requires code/state evidence; schema alone is insufficient")
            result["prediction"] = prediction
            if valid:
                obs = load(PRIVATE / task / "controller/verification.nc").observed.transpose("year","lat","lon").values
                training = load(PRIVATE / task / "controller/training.nc").observed.transpose("year","lat","lon").values
                metrics,_ = scores(p.values,m.values,obs,training)
                result["forecast_outcomes"]["inspected_prediction_years"] = {**metrics,"untouched_evaluation":False,"skill_gate":False}
        except InfrastructureUnavailable as error:
            result['prediction'].update(state='unresolved',reason=str(error)[:1500],failure_origin='controller_infrastructure')
        except (OSError,ValueError,KeyError,RuntimeError,TypeError) as error:
            result["prediction"].update(state="fail",reason=str(error)[:1500])
    return result
