"""Scientific comparisons with exact coordinates and explicit NaN semantics."""
from pathlib import Path
import json
import numpy as np
import xarray as xr

from .reference import SYSTEMS, REGIONS

FIELDS = ["case_mse", "case_acc", "rmse", "acc", "support_count", "support_area_fraction", "diagnostic_rmse"]


def comparison(actual, expected, names=FIELDS):
    for name in names:
        if name not in actual:
            return False, "Missing " + name
        a,b=actual[name],expected[name]
        if a.dims != b.dims or any(d not in a.coords or not np.array_equal(a[d],b[d]) for d in b.dims):
            return False, name + ": dimension/coordinate order differs"
        if a.attrs.get("units") != b.attrs.get("units"):
            return False, name + ": incorrect units"
        if not np.array_equal(np.isnan(a.values),np.isnan(b.values)) or np.isinf(a.values).any():
            return False, name + ": finite/undefined support differs"
        if name == "support_count":
            same=np.array_equal(a.values,b.values)
        else:
            same=np.allclose(a.values,b.values,rtol=2e-7,atol=2e-6,equal_nan=True)
        if not same:
            return False,name+": numerical discrepancy"
    for coord in ("init_time","lead_time","valid_time"):
        if coord not in actual.coords or not np.array_equal(actual[coord],expected[coord]):
            return False,coord+": verification alignment differs"
    return True,"Scientific values, exact coordinates, units and undefined-ACC mask agree"


def answer_from(scores):
    metrics={}
    for region in REGIONS:
        metrics[region]={}
        for system in SYSTEMS:
            record={}
            for key in ("rmse","acc"):
                record[key]=[float(v) if np.isfinite(v) else None for v in scores[key].sel(region=region,system=system).values]
            metrics[region][system]=record
    return {"task":"weatherbench-verification","units":"K","truth":"ERA5","case_count":20,
            "lead_hours":[24,72,120,168],"systems":SYSTEMS,"regions":REGIONS,
            "constructed_faults":True,"published_scores_reproduced":False,"metrics":metrics,
            "limitations":["Public retrospective January reanalysis comparison, not annual published rankings"],
            "diagnosis":["Constructed init-time truth mismatch","Constructed uniform spatial weighting","Constructed individual support comparison"]}


def submission_checks(submission,private):
    submission,private=Path(submission),Path(private)
    controller=private/"controller" if (private/"controller").is_dir() else private
    groups={"support_alignment":["support_count","support_area_fraction"],
            "metric_values":["case_mse","case_acc","rmse","acc"],
            "fault_contrasts":["diagnostic_rmse"]}
    checks={}
    for name,fields in groups.items():
        try:
            with xr.open_dataset(submission/"scores.nc") as a,xr.open_dataset(controller/"scores.nc") as b:
                checks[name]=comparison(a,b,fields)
        except (OSError,ValueError,KeyError,TypeError) as e:
            checks[name]=(False,str(e))
    try:
        answer=json.loads((submission/"answer.json").read_text())
        with xr.open_dataset(controller/"scores.nc") as b:
            expected=answer_from(b)
        fixed=("task","units","truth","case_count","lead_hours","systems","regions","constructed_faults","published_scores_reproduced")
        correct=all(answer.get(k)==expected[k] for k in fixed) and type(answer.get("case_count")) is int
        correct &= answer.get("constructed_faults") is True and answer.get("published_scores_reproduced") is False
        correct &= isinstance(answer.get("limitations"),list) and bool(answer["limitations"])
        correct &= isinstance(answer.get("diagnosis"),list) and len(answer["diagnosis"])>=3
        checks["answer_schema"]=(correct,"Declared benchmark boundaries and constructed-fault status checked")
        same=True
        for region in REGIONS:
            for system in SYSTEMS:
                for field in ("rmse","acc"):
                    actual=answer["metrics"][region][system][field]
                    gold=expected["metrics"][region][system][field]
                    if not isinstance(actual,list) or len(actual)!=4:
                        same=False;continue
                    for a,b in zip(actual,gold):
                        same &= a is None if b is None else type(a) in (int,float) and np.isfinite(a) and np.isclose(a,b,atol=2e-6,rtol=2e-7)
        checks["answer_metrics"]=(bool(same),"Answer metrics compared independently, undefined climatology ACC requires JSON null")
    except (OSError,ValueError,KeyError,TypeError) as e:
        checks["answer_schema"]=(False,str(e));checks["answer_metrics"]=(False,str(e))
    return {k:{"state":"pass" if ok else "fail","detail":detail,"evidence":["independent WeatherBench2 controller reference"]} for k,(ok,detail) in checks.items()}
