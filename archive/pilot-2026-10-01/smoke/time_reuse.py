"""Time direct application of a frozen, agent-written predictor (no LLM call)."""
import time
import xarray as xr
from pilot.common import ROOT,read,write
from pilot.runner import offline
base=ROOT/'runs/smoke-v3'
results=[]
for arm in ['scratch','rhiza','accord']:
 initial=base/f'fable-{arm}-initial';follow=base/f'fable-{arm}-followup'
 if not (initial/'checks.json').exists():continue
 checks=read(initial/'checks.json')
 if not any(c['id']=='prediction_validity_and_coverage' and c['passed'] for c in checks['checks']):continue
 out=initial/'direct-followup-timing'
 if (out/'timing.json').exists():results.append(read(out/'timing.json'));continue
 start=time.monotonic()
 outcome=offline(arm,initial/'frozen',out,['python','predict.py','--forecast','/inputs/forecast.nc','--output','/output/predictions.nc'],inputs=ROOT/'.private/smoke/followup/forecast.nc')
 elapsed=time.monotonic()-start
 value={'arm':arm,'seconds_including_container_start_cleanup':elapsed,'agent_tokens':0,'agent_usd':0,'exit_code':outcome['exit_code'],'initial_fitted_state_used':True,'forecast_batch':'2007-2008','scope':'Direct offline application of the initial frozen predictor; this is not the conversational follow-up cost.'}
 if outcome['exit_code']==0:
  from pilot.checks import seasonal_scores
  value['metrics']=seasonal_scores(xr.load_dataset(out/'predictions.nc'),xr.load_dataset(ROOT/'.private/smoke/followup/verification.nc'),xr.load_dataset(ROOT/'.private/smoke/followup/training.nc'))
 write(out/'timing.json',value);results.append(value)
write(ROOT/'results/direct-reuse-timing.json',results)
print([{k:v[k] for k in ['arm','seconds_including_container_start_cleanup','agent_tokens','exit_code']} for v in results])
