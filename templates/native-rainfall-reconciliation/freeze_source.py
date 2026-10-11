"""Restore a deterministic delivery snapshot from hash-verified native sources.

Run from the repository root. An existing frozen snapshot is verified, never
regenerated in place; a checked-in manifest is never silently replaced.
"""
from pathlib import Path
import json,hashlib,shutil,sys
import numpy as np,xarray as xr
root=Path.cwd(); t=root/'templates/native-rainfall-reconciliation'; source=root/'var/private/tasks/native-rainfall-reconciliation'; a=source/'agent-inputs'
manifest_path=t/'sources.json'
if source.exists() and manifest_path.exists():
 manifest=json.loads(manifest_path.read_text())
 for row in manifest['files']:
  path=source/row['file']
  if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Frozen snapshot missing or changed: '+str(path))
 print('Existing frozen source verified; no bytes changed.')
 sys.exit(0)
a.mkdir(parents=True,exist_ok=True)
k=json.loads((root/'templates/kenya-forecast-revision/sources.json').read_text())
for store,record in k['stores'].items():
 for obj in record['objects']:
  path=root/'var/private/templates/kenya-forecast-revision/stores'/store/obj['path']
  if hashlib.sha256(path.read_bytes()).hexdigest()!=obj['sha256']:raise ValueError('Provider source changed: '+str(path))
current='ECMWF_s2s_precip_2026-09-27.zarr';shutil.copytree(root/'var/private/templates/kenya-forecast-revision/stores'/current,a/current,dirs_exist_ok=True)
old=root/'var/private/templates/kenya-forecast-revision/stores/ECMWF_s2s_precip_2026-09-20.zarr'
with xr.open_zarr(old,chunks=None,consolidated=False) as d:
 d=d.load(); edges=np.array([0,1,3,5,7,8,10,12,14,15,17,19,21,22,24,26,28,29,31,33,35,36,38,40,42,43,45,46]); values=d.tp.transpose('number','step','latitude','longitude').values.astype(float)
 rates=(values[:,edges[1:]]-values[:,edges[:-1]])/np.diff(edges)[None,:,None,None]
 starts=np.datetime64('2026-09-20')+edges[:-1].astype('timedelta64[D]');ends=np.datetime64('2026-09-20')+edges[1:].astype('timedelta64[D]')
 ds=xr.Dataset({'rain_rate':(('member','interval','lat','lon'),rates[:,:,::-1,::-1],{'units':'mm day-1','cell_methods':'time: mean','comment':'Signed net interval mean; no clipping of quantization dips.'}),'time_bounds':(('interval','bounds'),np.stack([starts,ends],axis=1))},coords={'member':d.number.values,'interval':np.arange(len(starts)),'lat':d.latitude.values[::-1],'lon':d.longitude.values[::-1],'issue':np.datetime64('2026-09-20')},attrs={'lineage':'Curator-derived delivery from frozen ECMWF source; not a separate native provider export or model.','conversion':'Endpoint cumulative kg m**-2 differences divided by exact interval durations in days. 1 kg m**-2 liquid water = 1 mm.'})
 ds.to_netcdf(a/'previous-interval-rates.nc',engine='h5netcdf')
(a/'prior-bulletin.json').write_text(json.dumps({'status':'Non-authoritative draft; do not use as computational input.','regional_change_mm':[999,-999],'direction':['wetter','drier']},indent=2)+'\n')
provenance={'source_weather_is_synthetic':False,'provider':'ECMWF public Kenya archive','current':k['stores'][current], 'previous_native':k['stores']['ECMWF_s2s_precip_2026-09-20.zarr'],'previous_delivery':{'file':'previous-interval-rates.nc','derived_by':'templates/native-rainfall-reconciliation/freeze_source.py','operations':['Use unmodified native member/cell values at irregular retained step endpoints','Difference endpoint accumulation kg m**-2, equivalent to mm','Divide by exact integer days between endpoints','Reverse latitude and longitude ordering','Encode NetCDF float64 with explicit half-open valid-time interval bounds'],'information_loss':'Daily detail within two-day intervals is absent; task windows coincide with stored interval boundaries.','new_forecast_model':False},'rights':'Internal development only; scientific and redistribution approvals pending.'}
(a/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
files=[{'file':str(p.relative_to(source)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'visibility':'agent'} for p in sorted(source.rglob('*')) if p.is_file()]
manifest={'schema_version':1,'source_snapshot':str(source.relative_to(root)),'source_weather_is_synthetic':False,'scientific_approval':'pending','redistribution_approval':'pending','files':files}
if manifest_path.exists():
 if json.loads(manifest_path.read_text())!=manifest:raise ValueError('Restored bytes differ from frozen manifest; manifest preserved.')
else:manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
