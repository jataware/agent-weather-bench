"""Trusted full replay, fold-target perturbation and no-target saved-state inference."""
from pathlib import Path
import json,shutil
import numpy as np
import xarray as xr
from weatherbench.runtime import offline,InfrastructureUnavailable
from weatherbench.storage import PRIVATE,read,inventory
from .checks import comparison,GROUPS
from .reference import from_state

FIELDS={'hindcasts.nc':['prediction','probability','threshold','selected_candidate','inner_loss','rps','rpss','full_fit_prediction','full_fit_probability'],'forecast.nc':['prediction','probability','threshold','selected_candidate','inner_loss']}

def matching(actual,expected,fields=FIELDS):
    for name,variables in fields.items():
        with xr.open_dataset(Path(actual)/name) as a,xr.open_dataset(Path(expected)/name) as b:
            p,d=comparison(a,b,variables)
            if not p:return p,d
    return True,'Scientific outputs match'

def stage(frozen,destination,inputs,no_targets=False):
    shutil.copytree(frozen,destination)
    # Remove known truth/hindcast outputs everywhere, retained original inputs included.
    if no_targets:
        for pattern in ['targets.nc','hindcasts.nc']:
            for p in destination.rglob(pattern):p.unlink()
    target=destination/'_controller_inputs';shutil.copytree(inputs,target)
    if no_targets:(target/'targets.nc').unlink(missing_ok=True)
    return target

def evaluate(run,output):
    run,output=Path(run),Path(output);frozen=run/'frozen';config=read(run/'system.json')
    if inventory(frozen)!=read(run/'artifacts.json'):raise ValueError('Frozen submission changed')
    from weatherbench.task_tools.checks import check
    private=PRIVATE/'cca-seasonal-reproduction';output.mkdir(parents=True,exist_ok=True)
    result={'static':check('cca-seasonal-reproduction',frozen),'integrity':read(run/'controller/integrity.json'),'replay':{'state':'unresolved','passed':False},'counterfactual':{'state':'unresolved','passed':False},'prediction':{'state':'unresolved','passed':False},'acquisition':{'state':'not_applicable','passed':True},'forecast_outcomes':{}}
    try:
        manifest=json.loads((frozen/'execution.json').read_text());model=manifest['model_path']
        if not isinstance(model,str) or Path(model).is_absolute() or '..' in Path(model).parts:raise ValueError('model_path must be relative fitted state')
        for name in ['replay','predict']:
            if not all(any(p in a for a in manifest[name]['argv']) for p in ['{input_dir}','{output_dir}']):raise ValueError(f'{name}.argv requires input/output placeholders')
        def execute(name,where,out):
            args=[a.replace('{input_dir}','/work/_controller_inputs').replace('{output_dir}','/output').replace('{model_path}',str(Path('/work')/model)) for a in manifest[name]['argv']]
            r=offline(config['runtime']['image'],where,out,args,seconds=config['budget']['command_seconds'],memory=config['runtime']['memory'],cpus=config['runtime']['cpus'])
            if r.get('infrastructure_unavailable'):raise InfrastructureUnavailable(r.get('stderr','Docker unavailable'))
            return r
        stage(frozen,output/'replay-stage',private/'agent-inputs');replay=execute('replay',output/'replay-stage',output/'replay')
        p,d=matching(output/'replay',frozen) if replay['exit_code']==0 else (False,replay['stderr']);replay.update(passed=p,state='pass' if p else 'fail',detail=d);result['replay']=replay
        probe=stage(frozen,output/'counterfactual-stage',private/'agent-inputs')
        with xr.open_dataset(probe/'targets.nc') as ds:changed=ds.load()
        changed.rainfall.values[changed.year.values>=2011]*=1.7;changed.to_netcdf(probe/'targets.nc',mode='w')
        with xr.open_dataset(probe/'predictors.nc') as ds:changed=ds.load()
        changed.sst.values[changed.year.values>2011]+=np.linspace(-.7,1.1,changed.sizes['predictor']);changed.to_netcdf(probe/'predictors.nc',mode='w')
        counter=execute('replay',output/'counterfactual-stage',output/'counterfactual')
        if counter['exit_code']==0:
            with xr.open_dataset(output/'counterfactual/hindcasts.nc') as a,xr.open_dataset(frozen/'hindcasts.nc') as b:p,d=comparison(a.sel(year=slice(None,2011)),b.sel(year=slice(None,2011)),['prediction','probability','threshold','selected_candidate','inner_loss'])
        else:p,d=False,counter['stderr']
        counter.update(passed=p,state='pass' if p else 'fail',detail=d);result['counterfactual']=counter
        probe=stage(frozen,output/'prediction-stage',private/'agent-inputs',no_targets=True)
        with xr.open_dataset(probe/'predictors.nc') as ds:changed=ds.load()
        changed.sst.values[changed.year.values>=2020]+=np.linspace(.8,-.6,changed.sizes['predictor']);changed.to_netcdf(probe/'predictors.nc',mode='w')
        expected=from_state(read(private/'controller/model.json'),probe)
        prediction=execute('predict',output/'prediction-stage',output/'prediction')
        if prediction['exit_code']==0:
            with xr.open_dataset(output/'prediction/forecast.nc') as a:p,d=comparison(a,expected,FIELDS['forecast.nc'])
        else:p,d=False,prediction['stderr']
        prediction.update(passed=p,state='pass' if p else 'fail',detail=d,saved_state_review_still_required=True);result['prediction']=prediction
        result['replay']['passed']=result['replay']['passed'] and counter['passed'] and prediction['passed'];result['replay']['state']='pass' if result['replay']['passed'] else 'fail'
        # Scientific outcome is descriptive, not a required positive-skill gate.
        if prediction['passed']:
            with xr.open_dataset(frozen/'forecast.nc') as ds:fc=ds.load()
            with xr.open_dataset(private/'controller/private-targets.nc') as ds:obs=ds.load()
            truth=obs.rainfall.values[None,:,:]<fc.threshold.values[:,None,:]
            target=truth.transpose(1,2,0);loss=np.mean((np.cumsum(fc.probability.values,axis=-1)[...,:2]-target[None])**2,axis=-1)
            wt=np.cos(np.deg2rad(obs.target_lat.values));pooled=np.einsum('syt,t->s',loss,wt)
            result['forecast_outcomes']={'independent_holdout':{str(s):{'rpss':float(1-pooled[i]/pooled[0]),'mean_rps':float(pooled[i]/(4*wt.sum()))} for i,s in enumerate(fc.system.values)},'years':[2020,2021,2022,2023],'skill_gate':False,'withheld_from_agent_and_fit':True,'untouched_evaluation':False,'data_vintage':'retrospective_final_observations'}
    except InfrastructureUnavailable as e:result['replay'].update(state='unresolved',passed=False,reason=str(e)[:1500],infrastructure_unavailable=True)
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as e:result['replay'].update(state='fail',passed=False,reason=str(e)[:1500])
    return result
