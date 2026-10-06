"""Deterministic station alignment and metric checking with explicit missingness."""
from pathlib import Path
import json
import numpy as np
import xarray as xr
from .reference import FIELDS, METHODS, VARIANTS


def comparison(actual, expected, names=FIELDS):
    for name in names:
        if name not in actual:return False,"Missing "+name
        a,b=actual[name],expected[name]
        if a.dims!=b.dims or any(d not in a.coords or not np.array_equal(a[d],b[d]) for d in b.dims):
            return False,name+": dimensions or exact coordinate order differs"
        if a.attrs.get("units")!=b.attrs.get("units"):return False,name+": incorrect units"
        if not np.array_equal(np.isnan(a),np.isnan(b)) or np.isinf(a.values).any():
            return False,name+": finite/undefined mask differs"
        exact = name in ("common_support","support_count","station_count")
        equal = np.array_equal(a,b) if exact else np.allclose(a,b,atol=2e-6,rtol=2e-7,equal_nan=True)
        if not equal:return False,name+": numerical discrepancy"
    for name in ("init_time","lead_time","valid_time"):
        if name not in actual.coords or not np.array_equal(actual[name],expected[name]):
            return False,name+": UTC verification alignment differs"
    return True,"Independent station truth, interpolation, exact support, units and metrics agree"


def answer_from(scores):
    def values(a):return [float(v) if np.isfinite(v) else None for v in a]
    return {"task":"station-verification","units":"K","truth":"NOAA ISD station air temperature",
            "case_count":20,"lead_hours":[24,72,120,168],"methods":["bilinear","nearest"],
            "station_ids":scores.station.values.tolist(),"constructed_faults":True,"constructed_availability":True,
            "published_scores_reproduced":False,"method_adaptation":True,
            "metrics":{m:{"rmse":values(scores.rmse.sel({"method":m}).values),
                          "equal_station_rmse":values(scores.equal_station_rmse.sel({"method":m}).values)} for m in ["bilinear","nearest"]},
            "station_sample_count":{s:[int(v) for v in scores.station_count.sel(station=s).values] for s in scores.station.values.tolist()},
            "limitations":["Short retrospective East Africa airport sample with unequal coverage and coarse-grid representativeness; not WeatherReal 2023 rank reproduction", "No forecast training, station lapse-rate correction or pristine prospective evaluation"],
            "diagnosis":["Constructed initialization-time truth mismatch", "Constructed Celsius-versus-Kelvin mismatch", "Constructed separate-method support"]}


def submission_checks(submission,private):
    submission,private=Path(submission),Path(private)
    controller=private/"controller" if (private/"controller").is_dir() else private
    groups={"station_alignment":["forecast_temperature","observed_temperature"],
            "support_alignment":["common_support","support_count","station_count"],
            "metric_values":["rmse","station_rmse","equal_station_rmse"],"fault_contrasts":["diagnostic_rmse"]}
    checks={}
    for group,names in groups.items():
        try:
            with xr.open_dataset(submission/"scores.nc") as a,xr.open_dataset(controller/"scores.nc") as b:
                checks[group]=comparison(a,b,names)
        except (OSError,ValueError,KeyError,TypeError) as e:checks[group]=(False,str(e))
    try:
        answer=json.loads((submission/"answer.json").read_text())
        with xr.open_dataset(controller/"scores.nc") as b:gold=answer_from(b)
        fixed=("task","units","truth","case_count","lead_hours","methods","station_ids","constructed_faults","constructed_availability","published_scores_reproduced","method_adaptation")
        schema=all(answer.get(k)==gold[k] and type(answer.get(k)) is type(gold[k]) for k in fixed)
        schema &= isinstance(answer.get("limitations"),list) and bool(answer["limitations"])
        schema &= isinstance(answer.get("diagnosis"),list) and len(answer["diagnosis"])>=3
        checks["answer_schema"]=(bool(schema),"Declared NOAA truth, method adaptation and constructed controls checked")
        metrics=True
        for method in gold["methods"]:
            for field in ("rmse","equal_station_rmse"):
                vals=answer["metrics"][method][field]
                if not isinstance(vals,list) or len(vals)!=4:metrics=False;continue
                for value,target in zip(vals,gold["metrics"][method][field]):
                    metrics &= value is None if target is None else type(value) in (int,float) and np.isfinite(value) and np.isclose(value,target,atol=2e-6,rtol=2e-7)
        metrics &= answer.get("station_sample_count")==gold["station_sample_count"]
        checks["answer_metrics"]=(bool(metrics),"Independent RMSE curves and station-support counts checked")
    except (OSError,ValueError,KeyError,TypeError) as e:
        checks["answer_schema"]=(False,str(e));checks["answer_metrics"]=(False,str(e))
    return {k:{"state":"pass" if ok else "fail","detail":detail,"evidence":["Independent NOAA station verification reference"]} for k,(ok,detail) in checks.items()}
