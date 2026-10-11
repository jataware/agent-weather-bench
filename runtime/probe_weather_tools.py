"""Offline functional diagnostics for candidate tasks, not agent evaluations.

Synthetic edge cases have explicit physical answers. Host orchestration uses
only stdlib; scientific code runs inside the pinned, isolated tooling images.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

RHIZA = r'''
import json, tempfile, subprocess, sys
from pathlib import Path
import numpy as np
import xarray as xr
rows=[]
with tempfile.TemporaryDirectory() as scratch:
 for consolidated in (False, True):
  for name, units, values in [('mass','kg m**-2',[0.,2.,8.,14.]),('depth','m',[0.,.002,.008,.014]),('rate_guard','mm day-1',[0.,2.,8.,14.])]:
   path=Path(scratch)/(name+str(consolidated)); output=Path(scratch)/(name+str(consolidated)+'-rates')
   d=xr.Dataset({'tp':(('step','latitude','longitude'),np.array(values)[:,None,None],{'units':units})},coords={'step':np.array([0,12,36,60],dtype='timedelta64[h]'),'latitude':[1.],'longitude':[37.],'time':np.datetime64('2026-09-27')})
   d.to_zarr(path,zarr_format=3,consolidated=consolidated)
   p=subprocess.run([sys.executable,'/catalog/skills/weather-skills/deaccumulate/scripts/deaccumulate.py','-i',str(path),'-o',str(output),'-v','tp'],capture_output=True,text=True)
   row={'case':name,'consolidated_metadata':consolidated,'input_units':units,'exit_code':p.returncode}
   if name=='rate_guard':
    row.update(expected='Reject already-rate data without differencing',passed=p.returncode==2,stderr=p.stderr[-800:])
   elif p.returncode==0:
    with xr.open_zarr(output,consolidated=False) as result:
     actual=result.tp.values.ravel(); error=float(np.max(np.abs(actual-np.array([4.,6.,6.]))))
     row.update(expected_mm_per_day=[4,6,6],actual_mm_per_day=actual.tolist(),maximum_error=error,passed=error<2e-12 and result.tp.attrs['units']=='mm day-1')
   else:row.update(passed=False,stderr=p.stderr[-800:])
   rows.append(row)
print(json.dumps(rows))
'''

ACCORD = r'''
import json,datetime
import numpy as np
import xarray as xr
from acmaddl.normalize import normalize,select_lon
raw=xr.Dataset({'precip':(('S','L','M','Y','X'),np.full((2,3,1,2,1),2.))},coords={'S':np.array(['2019-11-01','2020-11-01'],dtype='datetime64[ns]'),'L':[1,2,3],'M':[0],'Y':[1.,0.],'X':[35.]})
config={'variables':{'precip':{'units':'mm/day','target_units':'mm/day'}},'target_range':(datetime.datetime(2019,12,1),datetime.datetime(2020,2,29)),'leadtime_month':[12,1,2]}
result=normalize(raw,config,'precip',year_index=True)
actual=result.precip.values[:,0,0,0]
rows=[{'case':'DJF_leap_year_and_canonical_axes','expected_mm':[182,180],'actual_mm':actual.tolist(),'year_labels':result.year.values.tolist(),'latitude':result.lat.values.tolist(),'units':result.precip.attrs['units'],'passed':bool(np.array_equal(actual,[182,180]) and result.precip.attrs['units']=='mm' and np.array_equal(result.lat,[0,1]) and 'lead_time' not in result.dims)}]
cube=xr.Dataset({'v':('lon',np.arange(36))},coords={'lon':np.arange(0,360,10)})
selected=select_lon(cube,170,-170)
rows.append({'case':'antimeridian_on_0_360_grid','expected_longitude':[170,180,190],'actual_longitude':selected.lon.values.tolist(),'passed':bool(np.array_equal(selected.lon,[170,180,190]))})
print(json.dumps(rows))
'''


def run(item):
    arm, code, image = item
    result = subprocess.run(
        ["docker", "run", "--rm", "-i", "--network", "none", "--read-only",
         "--memory", "768m", "--cpus", "1", "--user", "65534:65534",
         "--tmpfs", "/tmp:rw,nosuid,size=256m", "--entrypoint", "python", image, "-"],
        input=code, capture_output=True, text=True, timeout=120)
    rows = json.loads(result.stdout.splitlines()[-1]) if result.returncode == 0 else []
    return {"arm": arm, "runtime_image": image, "exit_code": result.returncode,
            "passed": result.returncode == 0 and bool(rows) and all(r["passed"] for r in rows),
            "cases": rows, "stderr": result.stderr[-1500:]}


if __name__ == "__main__":
    images = json.loads((ROOT / "experiments/runtime-manifest-2026-10-08.json").read_text())["images"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(run, [("rhiza", RHIZA, images["rhiza"]), ("accord", ACCORD, images["accord"])]))
    output = {"type": "synthetic functional diagnostics; not benchmark attempts",
              "interpretation": "Validate useful tool capabilities before building real-data tasks. These tests do not establish an agent-level tooling advantage or capability boundary.",
              "rows": rows}
    (ROOT / "experiments/tooling-diagnostics-2026-10-08.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))
