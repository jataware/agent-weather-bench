"""One fixed cyclic-calibration recipe, with separately visible numeric groups."""
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import numpy as np
import xarray as xr
import yaml
from assessment.compare import compare,tolerance
from assessment.sources import restore

HERE=Path(__file__).resolve().parent


def module(name):
    spec=importlib.util.spec_from_file_location("monthly_cycle_"+name,HERE/(name+".py"))
    loaded=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def prepare(private,source_dir=None):
    return restore(HERE,private,source_dir)


def candidate_instances():
    return [{"id":"original-regional-monthly-1993-2023"}]


def brief_fields(params):
    return {}


def stage_inputs(private,params,destination):
    shutil.copytree(Path(private)/"agent-inputs",destination,
                    ignore=shutil.ignore_patterns("africas2s-smoothed-method.py.txt"))
    for name in ("algorithm.md","literature-notes.md","source-record.yaml"):
        shutil.copyfile(HERE/name,Path(destination)/name)
    (Path(destination)/"instance.json").write_text(json.dumps(params)+"\n")


def expected_coordinates(inputs,params):
    return module("envelope").COORDINATES


@lru_cache(maxsize=12)
def _computed(folder,predictor_sha,target_sha):
    hindcast,forecast,_=module("science").build(folder)
    return module("envelope").arrays(hindcast,forecast)


def reference(inputs,params,conventions):
    folder=Path(inputs)
    key=[hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in ("predictors.nc","targets.nc")]
    return _computed(str(folder),*key)


def independent(inputs,params,conventions):
    return module("reference_independent").reference(inputs,params,conventions)


def _rewrite(path,change):
    with xr.open_dataset(path) as source:
        result=source.load()
    change(result)
    temporary=path.with_suffix(".tmp")
    result.to_netcdf(temporary)
    temporary.replace(path)


def perturb_inputs(inputs,seed,kind="data"):
    folder=Path(inputs)
    if kind=="data":
        rng=np.random.default_rng(seed)
        _rewrite(folder/"targets.nc",lambda ds:ds.rainfall.values.__imul__(rng.uniform(1.2,1.6,(1,12,3))))
        _rewrite(folder/"predictors.nc",lambda ds:ds.iod.values.__iadd__(np.linspace(-.3,.5,12)[None,:]))
    elif kind=="whole_year":
        def targets(ds):
            ds.rainfall.values[ds.year.values>=2011]*=1.7
        def predictors(ds):
            ds.iod.values[ds.year.values>=2012]+=np.linspace(-.7,1.1,12)
        _rewrite(folder/"targets.nc",targets)
        _rewrite(folder/"predictors.nc",predictors)
    elif kind=="later_forecast":
        def predictors(ds):
            ds.iod.values[ds.year.values>=2022]+=np.linspace(.5,-.9,12)
        _rewrite(folder/"predictors.nc",predictors)
    elif kind=="saved_state":
        (folder/"targets.nc").unlink()
        def predictors(ds):
            ds.iod.values[ds.year.values>=2020]+=np.linspace(.8,-.6,12)
        _rewrite(folder/"predictors.nc",predictors)
        (folder/"saved-inference.json").write_text('{"mode":"saved_state_changed_sst_without_targets"}\n')
    else:
        raise ValueError(kind)


GROUPS={
    "fitted":("hindcast_coefficient","hindcast_standardized_coefficient","xmean","xstd","ymean","ystd"),
    "nested":("selected_candidate","inner_loss","final_candidate","final_inner_loss"),
    "verification":("hindcast_mm","squared_error","monthly_msss","msss"),
    "production":("forecast_mm","forecast_coefficient","forecast_standardized_coefficient"),
}


def _numeric_group(name):
    def check(results,params,inputs):
        expected=reference(inputs,params,{"recipe":"specified"})
        spec=yaml.safe_load((HERE/"spec.yaml").read_text())["results"]
        names=GROUPS[name]
        for key in names:
            if key not in results:
                raise KeyError(key)
        slim={key:{**spec[key],"tolerance":{**spec[key]["tolerance"],"atol":tolerance(spec[key]["tolerance"])}} for key in names}
        ok,detail=compare(slim,results,{key:expected[key] for key in names})
        return ok,json.dumps(detail,sort_keys=True)
    check.__doc__={"fitted":"Do expanding-fit moments and physical/standardized slopes follow the specified cyclic procedure?",
                   "nested":"Do whole-year inner losses, tie breaking and production selection follow the fixed candidates?",
                   "verification":"Are outer predictions, squared errors and monthly/pooled MSSS numerically correct?",
                   "production":"Are all four systems' production forecasts and coefficients correct, including the constant standardized-slope comparator?"}[name]
    return check


INVARIANTS={name:_numeric_group(name) for name in GROUPS}


def early_outer(results,inputs,params):
    keep=results["outer_year"]<=2011
    names=("hindcast_mm","hindcast_coefficient","hindcast_standardized_coefficient","selected_candidate","inner_loss","xmean","xstd","ymean","ystd")
    return {name:results[name][keep] for name in names}


def early_production(results,inputs,params):
    return {"forecast_mm":results["forecast_mm"][:,:2]}


def saved_fit_projection(results,inputs,params):
    # saved_state.py independently checks changed-SST predictions. This second
    # check ensures the retained fit/selection itself did not move.
    return {name:results[name] for name in ("forecast_coefficient","forecast_standardized_coefficient","final_candidate","final_inner_loss")}


INVARIANCE_PROBES={
    "whole_year_isolation":{"perturb":"whole_year","unchanged":early_outer,
        "passes":"All fit/prediction/selection diagnostics through2011 ignore targets from2011 onward and predictors from2012 onward.",
        "fails":"Earlier fit, prediction or selection uses its own or future target year."},
    "forecast_batch_isolation":{"perturb":"later_forecast","unchanged":early_production,
        "passes":"Production2020–2021 forecasts ignore changed2022–2023 predictors.",
        "fails":"An earlier production forecast depends on a later predictor batch."},
    "saved_state_prediction":{"perturb":"saved_state","unchanged":saved_fit_projection,
        "passes":"The declared predict command uses retained fitted state without targets or original result stores; independent FFT production values match changed SST and fit/selection remain fixed. Implemented by saved_state.py executor wrapper plus this projection.",
        "fails":"Target-free saved inference, changed-SST prediction or fixed fitted-state identity failed."},
}


def executor_factory(base):
    return module("saved_state").SavedStateExecutor(base)


def expected_claims(results,params):
    return {"rainfall_units":[["mm"]],"physical_coefficient_units":[["mm/degree_Celsius"]],
            "dynamical_hindcasts_used":[["no"]],"full_paper_reproduction":[["no"]]}


def regression_checks(inputs):
    """Preserved original archived outputs, beyond agreement of the new drivers."""
    private=HERE.parents[1]/"var/private/templates/monthly-cycle-calibration"
    with xr.open_dataset(private/"controller/hindcasts.nc") as file:
        hindcast=file.load()
    with xr.open_dataset(private/"controller/forecast.nc") as file:
        forecast=file.load()
    archived=module("envelope").arrays(hindcast,forecast)
    current=reference(inputs,{}, {"recipe":"specified"})
    spec=yaml.safe_load((HERE/"spec.yaml").read_text())["results"]
    rows=[]
    for name,row in spec.items():
        bound=tolerance(row["tolerance"])
        gap=float(np.max(np.abs(current[name]-archived[name])))
        rows.append({"name":"archived_output_parity."+name,"passed":gap<=bound,
                     "largest_difference":gap,"atol":bound})
    original=HERE.parents[1]/"archive/evaluator-v1-2026-10/weatherbench/task_tools/monthly_cycle/reference.py"
    archived_hash=hashlib.sha256(original.read_bytes()).hexdigest()
    current_hash=hashlib.sha256((HERE/"science.py").read_bytes()).hexdigest()
    rows.append({"name":"archived_science_byte_identity","passed":archived_hash==current_hash,
                 "archived_sha256":archived_hash,"current_sha256":current_hash})
    rows.append({"name":"original_source_inputs_unchanged","passed":all(
        hashlib.sha256((private/row["file"]).read_bytes()).hexdigest()==row["sha256"]
        for row in json.loads((HERE/"sources.json").read_text())["files"]),
        "manifest_sha256":hashlib.sha256((HERE/"sources.json").read_bytes()).hexdigest()})
    return rows
