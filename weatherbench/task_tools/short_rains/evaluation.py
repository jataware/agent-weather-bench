"""Trusted offline replay and counterfactual execution for this task only."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import xarray as xr

from weatherbench.runtime import offline
from weatherbench.runtime import InfrastructureUnavailable
from weatherbench.storage import PRIVATE, inventory, read
from .checks import comparison, submission_checks
from .reference import CANDIDATES, forecast

SCIENTIFIC = {"seasonal.nc":["seasonal_total"], "hindcasts.nc":["probability","threshold","selected_candidate","inner_rps","rps","rpss"], "forecast.nc":["probability","threshold","selected_candidate","inner_rps"]}


def matching(actual, expected, fields=SCIENTIFIC):
    for file, names in fields.items():
        with xr.open_dataset(actual/file) as a, xr.open_dataset(expected/file) as b:
            passed, detail = comparison(a,b,names)
            if not passed:
                return False, detail
    return True, "Required scientific arrays agree"


def expected_changed_forecast(private, probe):
    controller = private / "controller"
    training = xr.open_dataset(controller / "seasonal.nc").seasonal_total.load()
    original = xr.open_dataset(controller / "forecast.nc").load()
    sst = xr.open_dataset(probe / "sst.nc").sst.load()
    gcm = xr.open_dataset(probe / "forecast-index.nc").gcm_iod.load()
    for ri, region in enumerate(original.region.values):
        winner = int(original.selected_candidate.sel(region=region))
        specs = [("iod",0,2,"identity"), ("forecast-iod",0,0,"identity"), CANDIDATES[winner]]
        for si, spec in enumerate(specs,1):
            pp, _ = forecast(sst,gcm,training.sel(region=region),np.arange(1993,2020),np.arange(2020,2024),spec)
            original.probability.values[si,:,ri] = pp
    return original


def stage(frozen, destination, inputs, remove_targets=False):
    shutil.copytree(frozen,destination)
    # Always override supplied input paths with trusted bytes, not retained data.
    for p in destination.rglob("rainfall.nc"):
        if remove_targets:
            p.unlink()
    if remove_targets:
        for name in ("seasonal.nc","hindcasts.nc"):
            for p in destination.rglob(name):
                p.unlink()
    target = destination / "_controller_inputs"
    shutil.copytree(inputs,target)
    if remove_targets:
        (target / "rainfall.nc").unlink(missing_ok=True)
    return target


def evaluate(run, output):
    run, output = Path(run), Path(output)
    meta, config = read(run/"run.json"), read(run/"system.json")
    frozen = run/"frozen"
    if inventory(frozen) != read(run/"artifacts.json"):
        raise ValueError("Frozen submission changed")
    private = PRIVATE / "short-rains-workflow"
    from weatherbench.task_tools.checks import check
    result = {"static":check("short-rains-workflow",frozen), "integrity":read(run/"controller/integrity.json"),
              "replay":{"state":"unresolved","passed":False}, "prediction":{"state":"unresolved","passed":False},
              "counterfactual":{"state":"unresolved","passed":False}, "acquisition":{"state":"not_applicable","passed":True}, "forecast_outcomes":{}}
    output.mkdir(parents=True,exist_ok=True)
    try:
        manifest = json.loads((frozen/"execution.json").read_text())
        for name in ("replay","predict"):
            argv = manifest[name]["argv"]
            if not all(any(p in a for a in argv) for p in ("{input_dir}","{output_dir}")):
                raise ValueError(f"{name}.argv needs {{input_dir}} and {{output_dir}}")
        def execute(name,stagepath,outpath):
            model = manifest.get("model_path", "model.json")
            if not isinstance(model,str) or Path(model).is_absolute() or ".." in Path(model).parts:
                raise ValueError("model_path must be a retained relative fitted-state path")
            argv = [a.replace("{input_dir}","/work/_controller_inputs").replace("{output_dir}","/output").replace("{model_path}",str(Path('/work')/model)) for a in manifest[name]["argv"]]
            record = offline(config["runtime"]["image"],stagepath,outpath,argv,
                             seconds=config["budget"]["command_seconds"],memory=config["runtime"]["memory"],cpus=config["runtime"]["cpus"])
            if record.get("infrastructure_unavailable"):
                raise InfrastructureUnavailable(record.get("stderr","Docker runtime unavailable"))
            return record
        replay_stage = output/"replay-stage"
        stage(frozen,replay_stage,private/"agent-inputs")
        replay = execute("replay",replay_stage,output/"replay")
        agreement, detail = matching(output/"replay",frozen) if replay["exit_code"]==0 else (False,replay["stderr"])
        replay.update(passed=agreement,state="pass" if agreement else "fail",detail=detail)
        result["replay"] = replay
        # Change a held-out target, all later targets, and all SST unavailable at
        # the 2011 issue time. Predictions through 2011 must be unchanged.
        perturb_stage = output/"counterfactual-stage"
        probe = stage(frozen,perturb_stage,private/"agent-inputs")
        rain = xr.open_dataset(probe/"rainfall.nc").load()
        rain.close()
        mask = rain.time.dt.year >= 2011
        rain.monthly_rainfall_scaled.values[mask.values] *= 1.7
        rain.to_netcdf(probe/"rainfall.nc",mode="w")
        sst = xr.open_dataset(probe/"sst.nc").load()
        sst.close()
        mask = sst.time >= np.datetime64("2011-09-01")
        sst.sst.values[mask.values] += np.array([2.,-.3,.7,-1.,.2])
        sst.to_netcdf(probe/"sst.nc",mode="w")
        gc = xr.open_dataset(probe/"forecast-index.nc").load()
        gc.close()
        gc.gcm_iod.values[gc.year.values > 2011] += 1
        gc.to_netcdf(probe/"forecast-index.nc",mode="w")
        counter = execute("replay",perturb_stage,output/"counterfactual")
        if counter["exit_code"] == 0:
            a = xr.open_dataset(output/"counterfactual/hindcasts.nc").sel(year=slice(None,2011))
            b = xr.open_dataset(frozen/"hindcasts.nc").sel(year=slice(None,2011))
            passed, detail = comparison(a,b,["probability","threshold","selected_candidate","inner_rps"])
        else:
            passed, detail = False,counter["stderr"]
        counter.update(passed=passed,state="pass" if passed else "fail",detail=detail)
        result["counterfactual"] = counter
        # Inference sees no original rainfall or seasonal artifacts; changed
        # independent-test predictors must affect forecasts according to saved fit.
        inference_stage = output/"prediction-stage"
        probe = stage(frozen,inference_stage,private/"agent-inputs",remove_targets=True)
        sst = xr.open_dataset(probe/"sst.nc").load()
        sst.close()
        mask = sst.time.dt.year >= 2020
        sst.sst.values[mask.values] += np.array([1.2,.4,-.5,-.3,.6])
        sst.to_netcdf(probe/"sst.nc",mode="w")
        gc = xr.open_dataset(probe/"forecast-index.nc").load()
        gc.close()
        gc.gcm_iod.values[gc.year.values >= 2020] += .8
        gc.to_netcdf(probe/"forecast-index.nc",mode="w")
        expected = expected_changed_forecast(private,probe)
        prediction = execute("predict",inference_stage,output/"prediction")
        if prediction["exit_code"] == 0:
            with xr.open_dataset(output/"prediction/forecast.nc") as actual:
                passed, detail = comparison(actual,expected,["probability","threshold"])
        else:
            passed, detail = False,prediction["stderr"]
        prediction.update(passed=passed,state="pass" if passed else "fail",detail=detail,
                          saved_fit_behavior="Changed allowed predictors, no rainfall inputs or seasonal artifacts; saved-state code still requires review")
        result["prediction"] = prediction
        result["replay"]["passed"] = agreement and result["counterfactual"]["passed"] and prediction["passed"]
        result["replay"]["state"] = "pass" if result["replay"]["passed"] else "fail"
        if prediction["passed"]:
            p = xr.open_dataset(frozen/"forecast.nc").load()
            obs = xr.open_dataset(private/"controller/private-targets.nc").monthly_total
            obs = obs.sel(time=obs.time.dt.month.isin([10,11,12])).groupby("time.year").sum("time")
            cases = {}
            for region in p.region.values:
                y = obs.sel(region=region).values
                b = p.threshold.sel(region=region).values
                target = np.column_stack((y < b[0],y < b[1]))
                pp = p.probability.sel(region=region).values
                loss = ((np.cumsum(pp,axis=-1)[:,:,:2]-target[None])**2).mean(axis=-1)
                cases[str(region)] = {str(s):{"mean_rps":float(loss[i].mean()),"rpss":float(1-loss[i].sum()/loss[0].sum())} for i,s in enumerate(p.system.values)}
            result["forecast_outcomes"] = {"independent_holdout":cases,"years":[2020,2021,2022,2023],"skill_gate":False,
                                          "withheld_from_agent_and_fit":True,"retrospective_independent_holdout":True,"untouched_evaluation":False}
    except InfrastructureUnavailable as e:
        result["replay"].update(state="unresolved",passed=False,reason=str(e)[:1500],infrastructure_unavailable=True)
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as e:
        result["replay"].update(state="fail",passed=False,reason=str(e)[:1500])
    return result
