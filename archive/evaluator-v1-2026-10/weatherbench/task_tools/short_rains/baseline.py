"""Internal accepted execution example; excluded from agent task resources.

Copy this file and reference.py to a temporary reference submission to test the
controller. This is a task-development example, not a model attempt.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import xarray as xr
from scipy.stats import t

try:
    from .reference import CANDIDATES, SYSTEMS, build, components, feature
except ImportError:
    from reference import CANDIDATES, SYSTEMS, build, components, feature


def state(inputs, seasonal, production):
    sst = xr.open_dataset(inputs/"sst.nc").sst.load()
    gcm = xr.open_dataset(inputs/"forecast-index.nc").gcm_iod.load()
    years = np.arange(1993,2020)
    saved = {"systems":list(SYSTEMS),"regions":list(seasonal.region.values),"fits":{},"thresholds":production.threshold.values.tolist()}
    for ri,r in enumerate(saved["regions"]):
        saved["fits"][r] = []
        winner = int(production.selected_candidate.sel(region=r))
        specs = [("iod",0,2,"identity"),("forecast-iod",0,0,"identity"),CANDIDATES[winner]]
        for spec in specs:
            x = feature(sst,gcm,years,years,spec)
            y = seasonal.seasonal_total.sel(region=r).values
            if spec[3] == "log1p":
                y = np.log1p(y)
            mx, my = float(x.mean()),float(y.mean())
            sx = float(np.sum((x-mx)**2))
            beta = float(np.sum((x-mx)*(y-my))/sx)
            var = float(np.sum((y-my-beta*(x-mx))**2)/(len(x)-2))
            fit = {"spec":list(spec),"n":len(x),"mx":mx,"my":my,"sxx":sx,"beta":beta,"variance":var}
            if spec[0] in ("wpg","wvg"):
                raw = components(sst,years,spec[1],spec[2])
                fit["box_mean"],fit["box_sd"] = raw.mean(axis=0).tolist(),raw.std(axis=0,ddof=1).tolist()
            saved["fits"][r].append(fit)
    return saved


def inference(inputs,saved):
    sst = xr.open_dataset(inputs/"sst.nc").sst.load()
    gcm = xr.open_dataset(inputs/"forecast-index.nc").gcm_iod.load()
    years = np.arange(2020,2024)
    p = np.full((4,4,3,3),1/3.)
    bounds = np.asarray(saved["thresholds"])
    boxes = list(sst.box.values)
    for ri,r in enumerate(saved["regions"]):
        for si,fit in enumerate(saved["fits"][r],1):
            name,gap,width,transform = fit["spec"]
            if name == "forecast-iod":
                x = gcm.sel(year=years).values
            else:
                raw = components(sst,years,gap,width)
                vals = {str(b):raw[:,i] for i,b in enumerate(boxes)}
                if name in vals:
                    x = vals[name]
                elif name == "iod":
                    x = vals["iod_w"]-vals["iod_e"]
                else:
                    zz = (raw-np.asarray(fit["box_mean"]))/np.asarray(fit["box_sd"])
                    z = {str(b):zz[:,i] for i,b in enumerate(boxes)}
                    x = z["wpac"]-z["nino34"] if name == "wpg" else z["nino34"]-z["wv"]
            mu = fit["my"]+fit["beta"]*(x-fit["mx"])
            scale = np.sqrt(fit["variance"]*(1+1/fit["n"]+(x-fit["mx"])**2/fit["sxx"]))
            cuts = np.log1p(bounds[ri]) if transform=="log1p" else bounds[ri]
            cdf = t.cdf((cuts[None,:]-mu[:,None])/scale[:,None],df=fit["n"]-2)
            p[si,:,ri] = np.column_stack([cdf[:,0],cdf[:,1]-cdf[:,0],1-cdf[:,1]])
    result = xr.Dataset({"probability":(("system","year","region","tercile"),p),"threshold":(("region","boundary"),bounds)},
                        coords={"system":saved["systems"],"year":years,"region":saved["regions"],"tercile":["below","normal","above"],"boundary":["lower","upper"]})
    result.threshold.attrs["units"] = "mm"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--outputs",type=Path,required=True)
    parser.add_argument("--model",type=Path)
    args = parser.parse_args()
    args.outputs.mkdir(parents=True,exist_ok=True)
    if args.model:
        inference(args.inputs,json.loads(args.model.read_text())).to_netcdf(args.outputs/"forecast.nc")
        return
    seasonal,cv,prod = build(args.inputs)
    for name,ds in (("seasonal.nc",seasonal),("hindcasts.nc",cv),("forecast.nc",prod)):
        ds.to_netcdf(args.outputs/name)
    (args.outputs/"model.json").write_text(json.dumps(state(args.inputs,seasonal,prod),indent=2)+"\n")
    metrics = {str(r):{str(s):{"mean_rps":float(cv.rps.sel(region=r,system=s).mean()),"rpss":float(cv.rpss.sel(region=r,system=s))} for s in cv.system.values} for r in cv.region.values}
    answer = {"task":"short-rains-workflow","training_years":[1993,2019],"verification_years":list(range(2005,2020)),"prediction_years":list(range(2020,2024)),
              "region_order":list(cv.region.values),"system_order":list(cv.system.values),"rainfall_units":"mm","rainfall_recovery_factor":30,
              "issue_time":"September 30","observed_sst_cutoff":"August 31","metrics":metrics,"forecast_skill_claim":"Controller-only independent targets; no local holdout skill claim","limitations":["15 dependent outer years","retrospective final products","one GCM forecast index","source retrieval boxes have margins"]}
    (args.outputs/"answer.json").write_text(json.dumps(answer,indent=2)+"\n")


if __name__ == "__main__":
    main()
