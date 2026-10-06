"""Actual Docker tests for constructed controls; no model/provider calls."""
from pathlib import Path
import json,time
import numpy as np
import xarray as xr
from weatherbench.runtime import offline
from .evaluation import stage,matching,FIELDS
from .reference import from_state
from .checks import comparison,submission_checks

IMAGE='sha256:14ded77c764dccdcaeef07f91c549709b4ff3549d0c30f5dc780e4376347917a'

def validate(repo=None):
    repo=Path(repo) if repo is not None else Path(__file__).resolve().parents[3]
    private=repo/'var/private/tasks/cca-seasonal-reproduction';root=repo/'var/calibration/cca-seasonal-reproduction';out=root/f'docker-{time.time_ns()}';records={}
    for name in ['baseline','full-training-leak','cached-inference']:
        frozen=root/'controls'/name/'frozen';dest=out/name;dest.mkdir(parents=True)
        row={'constructed_not_agent_attempt':True,'network':'none','cpu':2,'memory':'4g','scientific_checks':submission_checks(frozen,private)}
        for probe_name in ['replay','counterfactual','prediction']:
            p=stage(frozen,dest/(probe_name+'-stage'),private/'agent-inputs',no_targets=probe_name=='prediction')
            if probe_name=='counterfactual':
                with xr.open_dataset(p/'targets.nc') as ds:y=ds.load()
                y.rainfall.values[y.year.values>=2011]*=1.7;y.to_netcdf(p/'targets.nc',mode='w')
                with xr.open_dataset(p/'predictors.nc') as ds:x=ds.load()
                x.sst.values[x.year.values>2011]+=np.linspace(-.7,1.1,x.sizes['predictor']);x.to_netcdf(p/'predictors.nc',mode='w')
            if probe_name=='prediction':
                with xr.open_dataset(p/'predictors.nc') as ds:x=ds.load()
                x.sst.values[x.year.values>=2020]+=np.linspace(.8,-.6,x.sizes['predictor']);x.to_netcdf(p/'predictors.nc',mode='w')
                expected=from_state(json.loads((private/'controller/model.json').read_text()),p)
            argv=['python','workflow.py','--inputs','/work/_controller_inputs','--outputs','/output']
            if probe_name=='prediction':argv+=['--model','/work/model.json']
            result=offline(IMAGE,dest/(probe_name+'-stage'),dest/probe_name,argv,seconds=180,memory='4g',cpus=2)
            if result['exit_code']==0:
                if probe_name=='replay':passed,detail=matching(dest/probe_name,frozen)
                elif probe_name=='counterfactual':
                    with xr.open_dataset(dest/probe_name/'hindcasts.nc') as a,xr.open_dataset(frozen/'hindcasts.nc') as b:passed,detail=comparison(a.sel(year=slice(None,2011)),b.sel(year=slice(None,2011)),['prediction','probability','threshold','selected_candidate','inner_loss'])
                else:
                    with xr.open_dataset(dest/probe_name/'forecast.nc') as a:passed,detail=comparison(a,expected,FIELDS['forecast.nc'])
            else:passed,detail=False,result['stderr']
            result.update(passed=bool(passed),state='pass' if passed else 'fail',detail=detail);row[probe_name]=result
        records[name]=row
        (dest/'result.json').write_text(json.dumps(row,indent=2)+'\n')
    expected={'baseline':['pass','pass','pass'],'full-training-leak':['pass','fail','pass'],'cached-inference':['pass','pass','fail']}
    for name,states in expected.items():
        actual=[records[name][k]['state'] for k in ['replay','counterfactual','prediction']]
        if actual!=states:raise AssertionError(f'{name}: expected{states}, got{actual}')
    summary={'constructed_controls':True,'model_calls':0,'human_labels':False,'docker_controls_passed':True,'directory':str(out.relative_to(repo)),'records':records}
    (root/'docker-controls.json').write_text(json.dumps(summary,indent=2)+'\n');return summary

if __name__=='__main__':
    out=validate();print(json.dumps({'directory':out['directory'],'states':{n:{p:r[p]['state'] for p in ['replay','counterfactual','prediction']} for n,r in out['records'].items()}},indent=2))
