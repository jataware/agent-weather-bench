from pathlib import Path
import xarray as xr,yaml
from pilot.common import ROOT,read,write,digest
inp=ROOT/'.private/smoke/inputs'
for p in inp.glob('*.nc'):
 d=xr.load_dataset(p);d.to_netcdf(p.with_suffix('.new'),engine='scipy',format='NETCDF3_64BIT');p.with_suffix('.new').replace(p)
source=read(inp/'source-manifest.json');source['files']={p.name:digest(p) for p in inp.glob('*.nc')};write(inp/'source-manifest.json',source)
p=ROOT/'smoke/task.yaml';s=read(p)
s['brief']+='\nEnvironment note: the supplied files are NetCDF3. Read them with xarray engine="scipy". Use engine="h5netcdf" for NetCDF output. These common I/O settings avoid an identified native NetCDF binding shutdown defect.\n'
p.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True))
for phase in ['initial','followup']:
 p=ROOT/'.private/smoke'/phase/'reference.json';r=read(p);r['task_sha256']=digest(ROOT/'smoke/task.yaml');write(p,r)
for n in ['config','weak-config']:
 p=ROOT/'smoke'/f'{n}.yaml';cfg=read(p);cfg['agent'].update(max_total_tokens=500000,max_usd=5);p.write_text(yaml.safe_dump(cfg,sort_keys=False))
p=ROOT/'smoke/run.py';p.write_text(p.read_text().replace('runs/smoke-v2','runs/smoke-v3'))
p=ROOT/'smoke/manifest.json';s=read(p);s.update(maximum_model_spend_usd=35,maximum_judge_spend_usd=10.5,task_sha256=digest(ROOT/'smoke/task.yaml'),scope_note='Earlier infrastructure-aborted runs remain separately archived; total recorded spend monitored below $60.');write(p,s)
print('NetCDF3 input conversion complete; frozen task and reference hashes updated.')
