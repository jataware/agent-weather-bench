"""Expert-written feasibility checks, not model attempts or benchmark solutions.

Verify the reference numerics in environments lacking ACCORD, and exercise
real Rhiza helpers. Inputs are already-verified development data; this check
does not test autonomous discovery or live retrieval by either agent arm.
Nothing under .preflight or the reference scripts belongs in agent workspaces.
"""
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
from pilot.common import rhiza_catalog
CATALOG = rhiza_catalog()


def run_box(image, work, command, catalog=False):
    args = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--pids-limit', '128', '--memory', '2g',
            '--cpus', '1', '--user', f'{os.getuid()}:{os.getgid()}',
            '--tmpfs', '/tmp:rw,nosuid,size=256m', '--env', 'MPLCONFIGDIR=/tmp/mpl',
            '--mount', f'type=bind,src={work},dst=/work', '--workdir', '/work']
    if catalog:
        args += ['--mount', f'type=bind,src={CATALOG},dst=/catalog,readonly']
    completed = subprocess.run(args+[image]+command, capture_output=True, text=True, timeout=180)
    if completed.returncode:
        raise RuntimeError(f'{image}: {completed.stderr[-3000:]}')
    return completed.stdout


def main():
    (ROOT/'.preflight').mkdir(exist_ok=True)
    reference = json.loads((ROOT/'results/development-scores.json').read_text())
    summary = {'purpose': 'expert_written_feasibility_not_agent_benchmark', 'agent_attempts': 0,
               'input_scope': 'previously_verified_development_data; no live retrieval in this check',
               'network_gateway_validated': False, 'arms': {}}
    probe = """import importlib.util,json
names=['africas2s','acmaddl','rosetta','weather_skills_core']
print(json.dumps({n:importlib.util.find_spec(n) is not None for n in names}))
"""
    for arm, image in [('scratch','weather-bench-python:iod-v1'), ('rhiza','weather-bench-skills:iod-v1')]:
        work = Path(tempfile.mkdtemp(prefix=arm+'-',dir=ROOT/'.preflight'))
        (work/'data').mkdir()
        (work/'results').mkdir()
        (work/'score_development.py').write_text((ROOT/'feasibility/score_development.py').read_text().replace(
            'ROOT = Path(__file__).resolve().parents[1]', 'ROOT = Path(__file__).resolve().parent'))
        for name in ['forecast-development.nc', 'observations-development.nc']:
            shutil.copyfile(ROOT/'data'/name,work/'data'/name)
        available = json.loads(run_box(image,work,['python','-c',probe]))
        assert not any(available[n] for n in ['africas2s','acmaddl','rosetta'])
        assert available['weather_skills_core'] == (arm == 'rhiza')
        print(f'{arm}: package isolation verified; running NumPy/SciPy reference',flush=True)
        run_box(image,work,['python','/work/score_development.py','--engine','numpy'])
        result = json.loads((work/'results/development-scores.json').read_text())
        for key in ['mean_RPS','RMSE_mm']:
            for metric, value in result[key].items():
                np.testing.assert_allclose(value,reference[key][metric],rtol=1e-8,atol=1e-8)
        image_id = subprocess.check_output(['docker','image','inspect',image,'--format','{{.Id}}'],text=True).strip()
        record = {'image_id':image_id, 'package_availability':available,
                  'reference_metrics_match':True, 'mean_RPS':result['mean_RPS'], 'RMSE_mm':result['RMSE_mm']}
        if arm == 'rhiza':
            forecast = xr.load_dataset(work/'data/forecast-development.nc')['precip']
            days = xr.DataArray([31.,30.,31.],dims='lead_time',coords={'lead_time':[2,3,4]})
            monthly = (forecast*days).rename({'init_time':'time','lead_time':'lead_month',
                                            'member':'number','lat':'latitude','lon':'longitude'})
            monthly.attrs = {'units':'mm'}
            monthly.latitude.attrs={'standard_name':'latitude','units':'degrees_north'}
            monthly.longitude.attrs={'standard_name':'longitude','units':'degrees_east'}
            monthly.to_dataset(name='precip').to_zarr(work/'monthly.zarr',zarr_format=2)
            script = '/catalog/skills/weather-skills/summarize-dim/scripts/summarize_dim.py'
            run_box(image,work,['python',script,'--input','/work/monthly.zarr','--output','/work/seasonal.zarr',
                               '--variable','precip','--dim','lead_month','--method','sum'],catalog=True)
            run_box(image,work,['python',script,'--input','/work/seasonal.zarr','--output','/work/ensemble_mean.zarr',
                               '--variable','precip','--dim','number','--method','mean'],catalog=True)
            actual=xr.open_zarr(work/'ensemble_mean.zarr')['precip'].load()
            expected=monthly.sum('lead_month').mean('number').transpose(*actual.dims)
            np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=1e-8)
            obs=xr.load_dataset(work/'data/observations-development.nc')['precip'].sel(lat=slice(-3,-2),lon=slice(36,37))
            obs=obs.rename({'lat':'latitude','lon':'longitude'})
            obs.latitude.attrs={'standard_name':'latitude','units':'degrees_north'}
            obs.longitude.attrs={'standard_name':'longitude','units':'degrees_east'}
            obs.to_dataset().to_zarr(work/'obs_cell.zarr',zarr_format=2)
            run_box(image,work,['python',script,'--input','/work/obs_cell.zarr','--output','/work/obs_mean.zarr',
                               '--variable','precip','--dim','latitude','--dim','longitude','--method','mean',
                               '--lat-weighted'],catalog=True)
            actual=xr.open_zarr(work/'obs_mean.zarr')['precip'].load()
            expected=obs.weighted(np.cos(np.deg2rad(obs.latitude))).mean(['latitude','longitude'])
            np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=1e-8)
            record['real_skills_verified']=['seasonal sum of monthly totals','ensemble mean','cosine-latitude weighted observation mean']
            record['catalog_commit']=subprocess.check_output(['git','-C',str(CATALOG),'rev-parse','HEAD'],text=True).strip()
            record['requires_python_glue']=['seasonal CDS and monthly CHIRPS acquisition','calendar/unit normalization',
                                          'per-cell spatial grouping','held-out calibration','independent verification']
        summary['arms'][arm]=record
        print(f'{arm}: PASS',flush=True)
    summary['status']='PASS'
    (ROOT/'results/other-arms-feasibility.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
