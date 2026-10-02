"""Freeze a small development-only smoke; no private pilot years or new downloads."""
from pathlib import Path
import copy,json,yaml
import xarray as xr
from pilot.common import ROOT,read,write,digest
from pilot.runtime import policies

spec=read(ROOT/'tasks/seasonal.yaml')
spec['version']='smoke-1'
spec['title']='Development smoke: seasonal rainfall calibration and saved-model reuse'
spec['brief']=spec['brief'].replace('Train on 1993–2008 only.','Train on 1993–2004 only.').replace('Training remains 1993–2008','Training remains 1993–2004').replace('limits of 16 years','limits of 12 years')
spec['brief']+='''\nSMOKE SCOPE: Identical verified normalized monthly development inputs are supplied
under /work/inputs. No live acquisition is scored. forecast-development.nc contains
ECMWF precipitation in mm/day; observations-development.nc contains native CHIRPS
monthly totals in mm/month. Inspect their coordinates and perform the required
seasonal and spatial aggregation yourself. Inputs contain training years only.
The private test batches are drawn from previously inspected development years;
this is an infrastructure/agent smoke, NOT untouched scientific validation.
Save your fitted model or fitted parameters as model.pkl, model.npz, model.nc or
model.json. predict.py must load saved state rather than fit again. Use any sound
training-only calibration method; disclose it. Retain all code, input files and
fitted state so a forecaster can use the workflow again. Cite the original raw
sources listed in inputs/source-manifest.json. Keep answer.json concise; put
numerical fields in NetCDF rather than huge JSON arrays. Do not install packages.
'''
spec['submission']=spec['submission'].replace('1993–2008','1993–2004')
spec['phases']['initial']['private_years']=[2005,2006]
spec['phases']['followup']['private_years']=[2007,2008]
spec['phases']['followup']['brief']=spec['phases']['followup']['brief'].replace('1993–2008','1993–2004')+' Your fitted state and workflow are already present. Validate that predict.py loads them and prepare the next batch without refitting. Preserve original training validation; document any edits.'
spec['readiness']={'reference':'development_smoke_only','unresolved':[]}
(ROOT/'smoke/task.yaml').write_text(yaml.safe_dump(spec,sort_keys=False,allow_unicode=True))
source=read(ROOT/'results/source-audit.json')
urls=[source['forecast']['dataset_url']]+[s for s in source['observations']['raw_stores'] if any(str(y) in s for y in range(1993,2005))]
base=ROOT/'.private/smoke'; inp=base/'inputs'; inp.mkdir(parents=True,exist_ok=True)
f=xr.load_dataset(ROOT/'data/forecast-development.nc');f=f.sel(init_time=f.init_time.dt.year<=2004);f.to_netcdf(inp/'forecast-development.nc')
o=xr.load_dataset(ROOT/'data/observations-development.nc');o=o.sel(time=o.time.dt.year<=2004);o.to_netcdf(inp/'observations-development.nc')
request=copy.deepcopy(source['forecast']['request']);request['year']=[str(y) for y in range(1993,2005)]
write(inp/'source-manifest.json',{'sources':urls,'forecast_request':request,'scope':'provided normalized development inputs; retrieval excluded',
 'files':{p.name:digest(p) for p in inp.glob('*.nc')}})
season=xr.load_dataset(ROOT/'data/seasonal-development.nc')
for phase,years in [('initial',[2005,2006]),('followup',[2007,2008])]:
 ref=base/phase;ref.mkdir(exist_ok=True)
 season.sel(year=slice(1993,2004)).to_netcdf(ref/'training.nc')
 season.sel(year=years).to_netcdf(ref/'verification.nc')
 season.sel(year=years)[['forecast']].to_netcdf(ref/'forecast.nc')
 write(ref/'reference.json',{'task':'seasonal','phase':phase,'task_sha256':digest(ROOT/'smoke/task.yaml'),
  'reviewed':True,'status':'previously_inspected_development_smoke_not_untouched_evaluation','sources':urls,
  'files':{p.name:digest(p) for p in ref.glob('*.nc')}})
policy=policies('seasonal','initial');policy.update(reviewed=True,readiness='development_smoke_no_live_retrieval',retrievals=[],urls=[])
write(base/'policy.json',policy)
cfg=read(ROOT/'experiment.yaml');cfg['study_type']='development_smoke'
cfg['agent'].update(model='claude-fable-5-1',input_usd_per_million=10,output_usd_per_million=50,
 max_usd=6,max_total_tokens=250000,max_output_tokens=8192,max_turns=35,max_seconds=600)
cfg['judge'].update(model='claude-sonnet-5-5',input_usd_per_million=2,output_usd_per_million=10,
 max_usd=1.5,max_output_tokens=4096)
(ROOT/'smoke/config.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False))
weak=copy.deepcopy(cfg);weak['agent'].update(model='claude-haiku-4-5-20251001',input_usd_per_million=1,output_usd_per_million=5)
(ROOT/'smoke/weak-config.yaml').write_text(yaml.safe_dump(weak,sort_keys=False))
write(ROOT/'smoke/manifest.json',{'purpose':'three-arm development smoke with follow-up and one weaker scratch contrast',
 'strong_model':'claude-fable-5-1','weak_model':'claude-haiku-4-5-20251001','judge_model':'claude-sonnet-5-5',
 'maximum_attempts':7,'maximum_model_spend_usd':42,'maximum_judge_spend_usd':10.5,
 'input_data':'normalized monthly fields, identical across arms; no live retrieval measured',
 'training_years':[1993,2004],'initial_years':[2005,2006],'followup_years':[2007,2008],
 'private_pilot_years_accessed':False,'sources':urls,'task_sha256':digest(ROOT/'smoke/task.yaml')})
review=read(ROOT/'launch-review.yaml');review.update(status='ready',allowed_scope='smoke_only',
 reason='User explicitly authorized the three-arm smoke, saved-state follow-up and targeted weaker-model illustration.',
 notes='Full pilot and parameter sweep remain unlaunched. Maximum seven development-smoke attempts plus judges.')
(ROOT/'launch-review.yaml').write_text(yaml.safe_dump(review,sort_keys=False))
print('Prepared fixed development smoke; no model calls yet.')
