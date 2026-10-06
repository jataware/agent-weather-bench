"""Task replay and saved-inference consistency; final metric after freeze only."""
import json,shutil
from pathlib import Path
import numpy as np
import xarray as xr
from weatherbench.runtime import offline,InfrastructureUnavailable
from weatherbench.storage import PRIVATE,inventory,read
from .metrics import score_file,validate_prediction


def agreement(actual,expected,inputs):
    for split in ('development','final'):
        with xr.open_dataset(inputs/f'{split}-features.nc') as f:shape=f.load()
        a=validate_prediction(Path(actual)/f'{split}-predictions.nc',shape)
        b=validate_prediction(Path(expected)/f'{split}-predictions.nc',shape)
        if not np.allclose(a,b,rtol=1e-7,atol=1e-5):return False,'Predictions differ'
    return True,'Both scientific prediction arrays agree on fixed support'


def stage(frozen,destination,inputs,remove_training=False,change=False):
    shutil.copytree(frozen,destination)
    if remove_training:
        for p in destination.rglob('training.nc'):p.unlink()
    for split in ('development','final'):
        for p in destination.rglob(f'{split}-predictions.nc'):p.unlink()
    target=destination/'_controller_inputs';shutil.copytree(inputs,target)
    if remove_training:(target/'training.nc').unlink(missing_ok=True)
    if change:
        for split in ('development','final'):
            file=target/f'{split}-features.nc'
            with xr.open_dataset(file) as original:ds=original.load()
            ds.raw_cfsv2.values=ds.raw_cfsv2.values*1.2+3
            ds.to_netcdf(file,mode='w')
    return target


def evaluate(run,output):
    run,output=Path(run),Path(output);config=read(run/'system.json');frozen=run/'frozen';private=PRIVATE/'subseasonal-optimization'
    if inventory(frozen)!=read(run/'artifacts.json'):raise ValueError('Frozen submission changed')
    from weatherbench.task_tools.checks import check
    result={'static':check('subseasonal-optimization',frozen),'integrity':read(run/'controller/integrity.json'),
            'replay':{'state':'unresolved','passed':False},'prediction':{'state':'unresolved','passed':False},
            'counterfactual':{'state':'unresolved','passed':False},'acquisition':{'state':'not_applicable','passed':True},'forecast_outcomes':{}}
    feedback=run/'controller/feedback-public.json'
    result['feedback']=read(feedback) if feedback.is_file() else {'state':'unavailable','scope':'development_only','reason':'No trusted development-feedback summary; imported controls cannot establish query exposure','final_score_exposed':False,'final_observations_exposed':False}
    # Final outcomes become inspectable only here, after artifacts freeze, even if replay manifest fails.
    try:result['forecast_outcomes']['private_final']={**score_file(frozen/'final-predictions.nc',private,'final'),'untouched_evaluation':False,'skill_gate':False}
    except (OSError,ValueError,KeyError,TypeError) as error:result['forecast_outcomes']['final_error']=str(error)[:1500]
    output.mkdir(parents=True,exist_ok=True)
    try:
        manifest=read(frozen/'execution.json');model=manifest.get('model_path','model.json')
        if not isinstance(model,str) or Path(model).is_absolute() or '..' in Path(model).parts or not (frozen/model).is_file():raise ValueError('Retained relative saved state is required')
        for command in ('replay','predict'):
            argv=manifest[command]['argv']
            if not isinstance(argv,list) or not argv or not all(isinstance(a,str) for a in argv):raise ValueError('Nonempty string argv required')
            for placeholder in ('{input_dir}','{output_dir}'):
                if not any(placeholder in a for a in argv):raise ValueError('Replay/predict need alternate input/output placeholders')
        def execute(command,staged,out):
            argv=[a.replace('{input_dir}','/work/_controller_inputs').replace('{output_dir}','/output').replace('{model_path}',str(Path('/work')/model)) for a in manifest[command]['argv']]
            record=offline(config['runtime']['image'],staged,out,argv,seconds=config['budget']['command_seconds'],memory=config['runtime']['memory'],cpus=config['runtime']['cpus'])
            if record.get('infrastructure_unavailable'):raise InfrastructureUnavailable(record.get('stderr','Docker unavailable'))
            return record
        replay_stage=output/'replay-stage';inputs=stage(frozen,replay_stage,private/'agent-inputs')
        record=execute('replay',replay_stage,output/'replay')
        passed,detail=agreement(output/'replay',frozen,inputs) if record['exit_code']==0 else (False,record['stderr'])
        record.update(passed=passed,state='pass' if passed else 'fail',detail=detail);result['replay']=record
        # Changed allowed forecast features, same unchanged training; full replay should preserve chosen configuration.
        counter_stage=output/'counterfactual-stage';changed=stage(frozen,counter_stage,private/'agent-inputs',change=True)
        counter=execute('replay',counter_stage,output/'counterfactual')
        prediction_stage=output/'prediction-stage';stage(frozen,prediction_stage,private/'agent-inputs',remove_training=True,change=True)
        record=execute('predict',prediction_stage,output/'prediction')
        passed,detail=agreement(output/'prediction',output/'counterfactual',changed) if record['exit_code']==0 and counter['exit_code']==0 else (False,'Replay or saved-state inference command failed')
        record.update(passed=passed,state='pass' if passed else 'fail',detail=detail,probe_limit='Consistency on one altered feature case; not proof of general correctness or leakage freedom')
        counter.update(passed=passed,state='pass' if passed else 'fail',detail=detail);result['prediction']=record;result['counterfactual']=counter
    except InfrastructureUnavailable as error:
        for name in ('replay','prediction','counterfactual'):
            if result[name]['state']=='unresolved':result[name].update(reason=str(error)[:1500],failure_origin='controller_infrastructure')
    except (OSError,ValueError,KeyError,RuntimeError,TypeError) as error:
        for name in ('replay','prediction','counterfactual'):
            if result[name]['state']=='unresolved':result[name].update(state='fail',reason=str(error)[:1500])
    return result
