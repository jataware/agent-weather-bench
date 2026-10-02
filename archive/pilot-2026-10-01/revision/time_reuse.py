"""Apply working initial predictors to the next batch without another model call."""
import time
import xarray as xr
from pilot.common import ROOT,read,write
from pilot.runner import offline
from pilot.checks import seasonal_scores
rows=[]
for run in sorted((ROOT/'runs/revision-v1').glob('*-initial')):
 if not (run/'checks.json').exists():continue
 if not any(c['id']=='prediction_validity_and_coverage' and c['passed'] for c in read(run/'checks.json')['checks']):continue
 m=read(run/'run.json');out=run/'direct-reuse'
 if (out/'timing.json').exists():rows.append(read(out/'timing.json'));continue
 ref=ROOT/'.private/smoke/followup';start=time.monotonic()
 replay=offline(m['arm'],run/'frozen',out,['python','predict.py','--forecast','/inputs/forecast.nc','--output','/output/predictions.nc'],inputs=ref/'forecast.nc')
 elapsed=time.monotonic()-start
 row={'run':run.name,'seconds':elapsed,'tokens':0,'agent_usd':0,'status':'passed' if replay['exit_code']==0 else 'failed','includes':'container start, prediction and cleanup; local compute not priced','forecast_years':[2007,2008]}
 if replay['exit_code']==0:
  row['metrics']=seasonal_scores(xr.load_dataset(out/'predictions.nc'),xr.load_dataset(ref/'verification.nc'),xr.load_dataset(ref/'training.nc'))
 write(out/'timing.json',row);rows.append(row)
write(ROOT/'results/revision-direct-reuse.json',rows)
print([{k:r[k] for k in ['run','seconds','status']} for r in rows])
