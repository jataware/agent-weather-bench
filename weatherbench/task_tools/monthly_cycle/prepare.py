"""Freeze real all-month SST/rainfall and independently crosscheck cyclic smoothing."""
from pathlib import Path
import hashlib,json,shutil,time
import numpy as np
import xarray as xr
from .reference import build,LAMBDAS
TASK='monthly-cycle-calibration'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def initial(repo,source):
    repo,source=Path(repo),Path(source);root=repo/'var/private/tasks'/TASK;inputs=root/'agent-inputs';controller=root/'controller';material=repo/'tasks'/TASK/'source-material'
    for d in [inputs,controller,material]:d.mkdir(parents=True,exist_ok=True)
    if (inputs/'predictors.nc').exists():raise ValueError('Inputs already frozen')
    years=np.arange(1993,2024);data=source/'v4zeek/data';series=[]
    for box in ['iod_w','iod_e']:
        with xr.open_dataset(data/f'sst_{box}_monthly.nc') as ds:series.append(ds.sst.weighted(np.cos(np.deg2rad(ds.lat))).mean(('lat','lon')).load())
    iod=series[0]-series[1]
    x=[]
    for year in years:
        row=[]
        for month in range(1,13):
            previous=np.datetime64(f'{year}-{month:02d}','M')-np.timedelta64(1,'M')
            row.append(float(iod.sel(time=str(previous)+'-01')))
        x.append(row)
    # Reuse independently audited real regional monthly reduction; undo exactly
    # the legacy factor30 for training, and retain already recovered private totals.
    existing=source/'agent-weather-bench/var/private/tasks/short-rains-workflow'
    with xr.open_dataset(existing/'agent-inputs/rainfall.nc') as ds:train=ds.monthly_rainfall_scaled.load()*30
    with xr.open_dataset(existing/'controller/private-targets.nc') as ds:test=ds.monthly_total.load()
    rain=xr.concat([train,test],dim='time').transpose('time','region')
    names=rain.region.values.tolist();latitudes=[5.15,.15,2.];longitudes=[46.2,37.9,44.25]
    x=np.array(x);y=np.stack([np.stack([rain.sel(time=f'{year}-{month:02d}-01').values for month in range(1,13)]) for year in years])
    if not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('Incomplete all-month year: exclude whole year rather than partial-month fitting')
    xd=xr.Dataset({'iod':(('year','month'),x)},coords={'year':years,'month':np.arange(1,13),'source_month':('month',np.r_[12,np.arange(1,12)]),'source_year':(('year','month'),np.broadcast_to(years[:,None],(len(years),12))-np.r_[1,np.zeros(11,dtype=int)][None,:])})
    xd.iod.attrs={'units':'degree_Celsius','processing':'West-minus-east raw ERA5 SST cosine-weighted retrieval-box monthly means; previous calendar month only; not a dynamical hindcast or exact standard DMI geometry'}
    yd=xr.Dataset({'rainfall':(('year','month','target'),y)},coords={'year':years,'month':np.arange(1,13),'target':names,'target_lat':('target',latitudes),'target_lon':('target',longitudes)})
    yd.rainfall.attrs={'units':'mm','processing':'Actual existing audited cosine-weighted regional CHIRPS monthly means; training legacy /30 undone, private monthly totals already recovered; no day-count multiplication'}
    xd.to_netcdf(inputs/'predictors.nc');yd.sel(year=slice(1993,2019)).to_netcdf(inputs/'targets.nc');yd.sel(year=slice(2020,2023)).to_netcdf(controller/'private-targets.nc')
    original=[data/'ea_precip_monthly.nc',data/'sst_iod_w_monthly.nc',data/'sst_iod_e_monthly.nc',existing/'agent-inputs/rainfall.nc',existing/'controller/private-targets.nc']
    (material/'original-files.json').write_text(json.dumps({str(p.relative_to(source)):{'sha256':digest(p),'bytes':p.stat().st_size} for p in original},indent=2)+'\n')
    code=source/'africas2s/src/africas2s/methods/smoothed_regression.py'
    excerpt='# Pinned AfricaS2S4f8526a32232f9c9af400a01e5a6f103a865c735, methods/smoothed_regression.py lines1-92\n'+''.join(code.read_text().splitlines(keepends=True)[:92])
    (material/'africas2s-smoothed-method.py.txt').write_text(excerpt);(inputs/'africas2s-smoothed-method.py.txt').write_text(excerpt)
    for name in ['algorithm.md','literature-notes.md']:shutil.copyfile(repo/'tasks'/TASK/name,inputs/name)
    (inputs/'candidates.json').write_text(json.dumps([{'id':i,'lambda':v} for i,v in enumerate(LAMBDAS)],indent=2)+'\n')
    (inputs/'source-manifest.json').write_text(json.dumps({'sources':['chirps3','era5-sst','legacy-normalization','africas2s-source','kharin2017']},indent=2)+'\n')

def prepare(repo=None,initialize=False):
    repo=Path(repo) if repo is not None else Path(__file__).resolve().parents[3];root=repo/'var/private/tasks'/TASK;controller=root/'controller'
    start=time.monotonic();a=build(root/'agent-inputs');b=build(root/'agent-inputs',backend='fft');maximum={}
    for filename,one,two in zip(['hindcasts.nc','forecast.nc'],a[:2],b[:2]):
        for k in one.data_vars:
            np.testing.assert_allclose(one[k],two[k],rtol=2e-10,atol=2e-8);maximum[f'{filename}:{k}']=float(abs(one[k]-two[k]).max())
        path=controller/filename
        if initialize:
            if path.exists():raise ValueError('Reference already frozen')
            one.to_netcdf(path)
        else:
            with xr.open_dataset(path) as old:xr.testing.assert_allclose(one,old,rtol=1e-12,atol=1e-12)
    audit={'task':TASK,'source_weather_is_synthetic':False,'dynamical_hindcasts_used':False,'method_adaptation':True,'full_paper_reproduction':False,'methods':['NumPy coupled cyclic linear solve and vectorized sample covariance','FFT circulant spectral solution and separate scalar covariance'],'max_absolute_differences':maximum,'all_selections_equal':True,'candidate_count':6,'complete_years':True,'reference_seconds':time.monotonic()-start,'human_scientific_approval':False}
    if initialize:
        (controller/'model.json').write_text(json.dumps(a[2],indent=2)+'\n');(controller/'reference-audit.json').write_text(json.dumps(audit,indent=2)+'\n');write_manifest(repo,root)
    return audit

def write_manifest(repo,root):
    package=repo/'tasks'/TASK;rows=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file():continue
        rel=str(p.relative_to(root));row={'file':rel,'sha256':digest(p),'bytes':p.stat().st_size,'visibility':'agent' if rel.startswith('agent-inputs/') else 'controller_only'}
        if p.suffix=='.nc':
            with xr.open_dataset(p) as ds:row.update(dimensions=dict(ds.sizes),variables={k:{'dimensions':list(v.dims),'units':v.attrs.get('units')} for k,v in ds.data_vars.items()})
        rows.append(row)
    ref=repo/'weatherbench/task_tools/monthly_cycle/reference.py'
    manifest={'schema_version':1,'task':TASK,'status':'local_development_snapshot','local_storage':str(root.relative_to(repo)),'files':rows,'reference_code_path':str(ref.relative_to(repo)),'reference_code_sha256':digest(ref),'reference_validation':'Independent solve/FFT smoothing and scalar/vectorized covariance across all selections and predictions','source_records':[{'path':str(p.relative_to(repo)),'sha256':digest(p)} for p in sorted(package.rglob('*')) if p.is_file() and p.name not in ['input-manifest.json','review.html']]}
    (package/'input-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
