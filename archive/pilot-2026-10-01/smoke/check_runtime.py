from pathlib import Path
import shutil,shlex
from pilot.common import ROOT,write
from pilot.runtime import Sandbox
result={}
for arm in ['scratch','rhiza','accord']:
 work=ROOT/'.preflight'/('smoke-io-'+arm);work.mkdir(parents=True,exist_ok=True)
 for p in (ROOT/'.private/smoke/inputs').glob('*.nc'):shutil.copy2(p,work/p.name)
 code='''import xarray as xr, rasterio, rioxarray, numpy as np
for fn in ['forecast-development.nc','observations-development.nc']:
 d=xr.load_dataset(fn);d.to_netcdf('roundtrip.nc');r=xr.load_dataset('roundtrip.nc');xr.testing.assert_identical(d,r)
print('read-write-roundtrip and raster imports passed')
'''
 with Sandbox(arm,work) as box:
  r=box.execute('python -c '+shlex.quote(code));result[arm]=r
  if r['exit_code']: raise RuntimeError(arm+': '+r['stderr'])
 print(arm,'passed',flush=True)
write(ROOT/'results/smoke-runtime-io.json',result)
