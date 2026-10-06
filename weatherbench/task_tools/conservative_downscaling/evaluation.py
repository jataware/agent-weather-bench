"""Offline replay and bounded fold/inference probes for conservative adaptation."""
import json,shutil
from pathlib import Path
import numpy as np,xarray as xr
from weatherbench.runtime import offline,InfrastructureUnavailable
from weatherbench.storage import PRIVATE,inventory,read
try:from .reference import geometry,infer
except ImportError:from reference import geometry,infer


def arrays_agree(actual,expected,files=('forecast.nc','hindcasts.nc')):
    for name in files:
        with xr.open_dataset(Path(actual)/name) as a,xr.open_dataset(Path(expected)/name) as b:
            for v in ('rainfall_mm','mapped_coarse_mm'):
                if a[v].dims!=b[v].dims or any(not np.array_equal(a[d],b[d]) for d in b[v].dims) or a[v].attrs.get('units')!='mm' or not np.allclose(a[v],b[v],rtol=1e-9,atol=1e-7):return False
    return True


def stage(frozen,destination,inputs,remove_training=False):
    shutil.copytree(frozen,destination)
    for name in ('forecast.nc','hindcasts.nc'):
        for p in destination.rglob(name):p.unlink()
    if remove_training:
        for p in destination.rglob('fine-training.nc'):p.unlink()
    target=destination/'_controller_inputs';shutil.copytree(inputs,target)
    if remove_training:(target/'fine-training.nc').unlink(missing_ok=True)
    return target


def evaluate(run,output):
    run,output=Path(run),Path(output);frozen=run/'frozen';config=read(run/'system.json');private=PRIVATE/'conservative-downscaling'
    if inventory(frozen)!=read(run/'artifacts.json'):raise ValueError('Frozen submission changed')
    from weatherbench.task_tools.checks import check
    result={'static':check('conservative-downscaling',frozen),'integrity':read(run/'controller/integrity.json'),'replay':{'state':'unresolved','passed':False},'prediction':{'state':'unresolved','passed':False},'counterfactual':{'state':'unresolved','passed':False},'acquisition':{'state':'not_applicable','passed':True},'forecast_outcomes':{}}
    try:
        with xr.open_dataset(frozen/'forecast.nc') as forecast,xr.open_dataset(private/'controller/fine-verification.nc') as observed:
            with xr.open_dataset(private/'agent-inputs/fine-training.nc') as training:climate=training.seasonal_total.mean('year').values
            with xr.open_dataset(private/'controller/forecast.nc') as expected:weights=expected.area_m2.values
            if forecast.rainfall_mm.dims!=observed.seasonal_total.dims or forecast.rainfall_mm.shape!=observed.seasonal_total.shape or any(not np.array_equal(forecast[d],observed[d]) for d in observed.seasonal_total.dims):raise ValueError('Wrong prediction support')
            truth=observed.seasonal_total.values;pred=forecast.rainfall_mm.values
            rms=lambda p:float(np.sqrt(np.sum((p-truth)**2*weights)/(len(truth)*weights.sum())))
            error,baseline=rms(pred),rms(climate[None,:,:])
            result['forecast_outcomes']['private_fine_prediction']={'area_weighted_rmse_mm':error,'climatology_rmse_mm':baseline,'rmse_skill_vs_climatology':1-error/baseline,'untouched_evaluation':False,'skill_gate':False}
    except (OSError,ValueError,KeyError,TypeError) as e:result['forecast_outcomes']['final_error']=str(e)[:1000]
    output.mkdir(parents=True,exist_ok=True)
    try:
        manifest=read(frozen/'execution.json');model=manifest.get('model_path','model.json')
        if not isinstance(model,str) or Path(model).is_absolute() or '..' in Path(model).parts:raise ValueError('Retained relative state required')
        for command in ('replay','predict'):
            argv=manifest[command]['argv']
            if not isinstance(argv,list) or not argv or not all(isinstance(a,str) for a in argv) or not all(any(k in a for a in argv) for k in ('{input_dir}','{output_dir}')):raise ValueError('Alternate input/output argv required')
        def execute(command,staged,out):
            argv=[a.replace('{input_dir}','/work/_controller_inputs').replace('{output_dir}','/output').replace('{model_path}',str(Path('/work')/model)) for a in manifest[command]['argv']]
            record=offline(config['runtime']['image'],staged,out,argv,seconds=config['budget']['command_seconds'],memory=config['runtime']['memory'],cpus=config['runtime']['cpus'])
            if record.get('infrastructure_unavailable'):raise InfrastructureUnavailable(record.get('stderr','Docker unavailable'))
            return record
        rs=output/'replay-stage';stage(frozen,rs,private/'agent-inputs');record=execute('replay',rs,output/'replay');passed=record['exit_code']==0 and arrays_agree(output/'replay',frozen);record.update(passed=passed,state='pass' if passed else 'fail');result['replay']=record
        us=output/'unit-invariance-stage';unit_probe=stage(frozen,us,private/'agent-inputs')
        with xr.open_dataset(unit_probe/'coarse-forecast.nc') as f:unit_data=f.load()
        unit_data.raw_predictor.values=unit_data.raw_predictor.values*92+7
        unit_data.to_netcdf(unit_probe/'coarse-forecast.nc',mode='w')
        unit_record=execute('replay',us,output/'unit-invariance')
        unit_passed=unit_record['exit_code']==0 and arrays_agree(output/'unit-invariance',frozen)
        unit_record.update(passed=unit_passed,state='pass' if unit_passed else 'fail',probe_limit='Positive affine scaling of all raw values; does not resolve physical source units')
        result['unit_scale_invariance']=unit_record
        if not unit_passed:result['replay'].update(passed=False,state='fail',reason='Normal replay or declared affine raw-scale invariance failed')
        cs=output/'counterfactual-stage';probe=stage(frozen,cs,private/'agent-inputs')
        with xr.open_dataset(probe/'fine-training.nc') as f:ds=f.load()
        ds.seasonal_total.values[ds.year.values==2001]*=1.5;ds.to_netcdf(probe/'fine-training.nc',mode='w')
        counter=execute('replay',cs,output/'counterfactual');passed=False
        if counter['exit_code']==0:
            with xr.open_dataset(output/'counterfactual/hindcasts.nc') as a,xr.open_dataset(frozen/'hindcasts.nc') as b:
                passed=all(np.allclose(a[v].sel(year=2001),b[v].sel(year=2001),rtol=1e-9,atol=1e-7) for v in ('rainfall_mm','mapped_coarse_mm'))
        counter.update(passed=passed,state='pass' if passed else 'fail',probe_limit='Single fold whole-truth perturbation, not proof for every fold');result['counterfactual']=counter
        ps=output/'prediction-stage';probe=stage(frozen,ps,private/'agent-inputs',remove_training=True)
        with xr.open_dataset(probe/'coarse-forecast.nc') as f:raw=f.load()
        mask=raw.year.values>=2009;raw.raw_predictor.values[mask]=raw.raw_predictor.values[mask]*.8+5;raw.to_netcdf(probe/'coarse-forecast.nc',mode='w')
        state=read(private/'controller/model.json')
        with xr.open_dataset(private/'agent-inputs/geometry.nc') as g:area,cell=geometry(g.lat,g.lon)
        expected_coarse,expected_fine=infer(raw.raw_predictor.values[mask],state,cell)
        record=execute('predict',ps,output/'prediction');passed=False
        if record['exit_code']==0:
            with xr.open_dataset(output/'prediction/forecast.nc') as ds,xr.open_dataset(private/'controller/forecast.nc') as original:
                support=(ds.rainfall_mm.dims==original.rainfall_mm.dims and ds.mapped_coarse_mm.dims==original.mapped_coarse_mm.dims and all(np.array_equal(ds[d],original[d]) for d in ('year','lat','lon','coarse_cell')) and ds.rainfall_mm.attrs.get('units')=='mm' and ds.mapped_coarse_mm.attrs.get('units')=='mm')
                passed=bool(support and np.allclose(ds.rainfall_mm,expected_fine,rtol=1e-9,atol=1e-7) and np.allclose(ds.mapped_coarse_mm,expected_coarse,rtol=1e-9,atol=1e-7))
        record.update(passed=passed,state='pass' if passed else 'fail',probe_limit='One altered allowed predictor case without observed inputs');result['prediction']=record
    except InfrastructureUnavailable as e:
        for k in ('replay','prediction','counterfactual'):
            if result[k]['state']=='unresolved':result[k].update(reason=str(e)[:1000],failure_origin='controller_infrastructure')
    except (OSError,ValueError,KeyError,RuntimeError,TypeError) as e:
        for k in ('replay','prediction','counterfactual'):
            if result[k]['state']=='unresolved':result[k].update(state='fail',reason=str(e)[:1000])
    return result
