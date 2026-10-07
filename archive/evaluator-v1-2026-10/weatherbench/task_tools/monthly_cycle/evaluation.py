"""Offline replay, whole-year isolation and saved state inference on changed SST."""
from pathlib import Path
import json,shutil
import numpy as np
import xarray as xr
from weatherbench.runtime import offline,InfrastructureUnavailable
from weatherbench.storage import PRIVATE,inventory,read
from .checks import comparison
from .reference import from_state
FIELDS={'hindcasts.nc':['prediction','coefficient','standardized_coefficient','selected_candidate','inner_loss','xmean','xstd','ymean','ystd','squared_error','monthly_msss','msss'],'forecast.nc':['prediction','coefficient','standardized_coefficient','selected_candidate','inner_loss']}

def matching(actual,expected,fields=FIELDS):
    for filename,names in fields.items():
        with xr.open_dataset(Path(actual)/filename) as a,xr.open_dataset(Path(expected)/filename) as b:
            p,d=comparison(a,b,names)
            if not p:return p,d
    return True,'Required scientific arrays match'

def stage(frozen,destination,inputs,no_targets=False):
    shutil.copytree(frozen,destination)
    if no_targets:
        for name in ['targets.nc','hindcasts.nc']:
            for p in destination.rglob(name):p.unlink()
    target=destination/'_controller_inputs';shutil.copytree(inputs,target)
    if no_targets:(target/'targets.nc').unlink(missing_ok=True)
    return target

def evaluate(run,output):
    run,output=Path(run),Path(output);frozen=run/'frozen';config=read(run/'system.json');private=PRIVATE/'monthly-cycle-calibration'
    if inventory(frozen)!=read(run/'artifacts.json'):raise ValueError('Frozen artifacts changed')
    from weatherbench.task_tools.checks import check
    result={'static':check('monthly-cycle-calibration',frozen),'integrity':read(run/'controller/integrity.json'),'replay':{'state':'unresolved','passed':False},'counterfactual':{'state':'unresolved','passed':False},'prediction':{'state':'unresolved','passed':False},'acquisition':{'state':'not_applicable','passed':True},'forecast_outcomes':{}}
    output.mkdir(parents=True,exist_ok=True)
    try:
        manifest=read(frozen/'execution.json');model=manifest['model_path']
        if not isinstance(model,str) or Path(model).is_absolute() or '..' in Path(model).parts:raise ValueError('Relative fitted model_path required')
        for name in ['replay','predict']:
            if not all(any(token in a for a in manifest[name]['argv']) for token in ['{input_dir}','{output_dir}']):raise ValueError('Alternate input/output placeholders required')
        def execute(name,work,out):
            args=[a.replace('{input_dir}','/work/_controller_inputs').replace('{output_dir}','/output').replace('{model_path}',str(Path('/work')/model)) for a in manifest[name]['argv']]
            r=offline(config['runtime']['image'],work,out,args,seconds=config['budget']['command_seconds'],memory=config['runtime']['memory'],cpus=config['runtime']['cpus'])
            if r.get('infrastructure_unavailable'):raise InfrastructureUnavailable(r.get('stderr','Docker unavailable'))
            return r
        stage(frozen,output/'replay-stage',private/'agent-inputs');r=execute('replay',output/'replay-stage',output/'replay')
        p,d=matching(output/'replay',frozen) if r['exit_code']==0 else (False,r['stderr']);r.update(passed=p,state='pass' if p else 'fail',detail=d);result['replay']=r
        probe=stage(frozen,output/'counterfactual-stage',private/'agent-inputs')
        with xr.open_dataset(probe/'targets.nc') as ds:y=ds.load()
        y.rainfall.values[y.year.values>=2011]*=1.7;y.to_netcdf(probe/'targets.nc',mode='w')
        with xr.open_dataset(probe/'predictors.nc') as ds:x=ds.load()
        x.iod.values[x.year.values>2011]+=np.linspace(-.7,1.1,12);x.to_netcdf(probe/'predictors.nc',mode='w')
        r=execute('replay',output/'counterfactual-stage',output/'counterfactual')
        if r['exit_code']==0:
            with xr.open_dataset(output/'counterfactual/hindcasts.nc') as a,xr.open_dataset(frozen/'hindcasts.nc') as b:p,d=comparison(a.sel(year=slice(None,2011)),b.sel(year=slice(None,2011)),['prediction','coefficient','standardized_coefficient','selected_candidate','inner_loss','xmean','xstd','ymean','ystd'])
        else:p,d=False,r['stderr']
        r.update(passed=p,state='pass' if p else 'fail',detail=d);result['counterfactual']=r
        probe=stage(frozen,output/'prediction-stage',private/'agent-inputs',no_targets=True)
        with xr.open_dataset(probe/'predictors.nc') as ds:x=ds.load()
        x.iod.values[x.year.values>=2020]+=np.linspace(.8,-.6,12);x.to_netcdf(probe/'predictors.nc',mode='w')
        expected=from_state(read(private/'controller/model.json'),probe);r=execute('predict',output/'prediction-stage',output/'prediction')
        if r['exit_code']==0:
            with xr.open_dataset(output/'prediction/forecast.nc') as a:p,d=comparison(a,expected,FIELDS['forecast.nc'])
        else:p,d=False,r['stderr']
        r.update(passed=p,state='pass' if p else 'fail',detail=d,saved_state_review_still_required=True);result['prediction']=r
        result['replay']['passed']=result['replay']['passed'] and result['counterfactual']['passed'] and r['passed'];result['replay']['state']='pass' if result['replay']['passed'] else 'fail'
        if r['passed']:
            with xr.open_dataset(frozen/'forecast.nc') as ds:fc=ds.load()
            with xr.open_dataset(private/'controller/private-targets.nc') as ds:y=ds.load()
            weights=np.ones(y.sizes['target']);error=(fc.prediction.values-y.rainfall.values[None])**2;pooled=np.einsum('symt,t->s',error,weights)
            result['forecast_outcomes']={'independent_holdout':{str(s):{'msss':float(1-pooled[i]/pooled[0]),'rmse_mm':float(np.sqrt(pooled[i]/(48*weights.sum())))} for i,s in enumerate(fc.system.values)},'years':[2020,2021,2022,2023],'skill_gate':False,'withheld_from_agent_and_fit':True,'untouched_evaluation':False,'dynamical_hindcasts_used':False}
    except InfrastructureUnavailable as e:result['replay'].update(state='unresolved',passed=False,reason=str(e),infrastructure_unavailable=True)
    except (OSError,ValueError,TypeError,KeyError,RuntimeError) as e:result['replay'].update(state='fail',passed=False,reason=str(e)[:1500])
    return result
