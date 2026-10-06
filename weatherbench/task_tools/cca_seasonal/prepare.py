"""Freeze a real-data compact method adaptation and audit both linear-algebra routes."""
from pathlib import Path
import hashlib,json,shutil,time
import numpy as np
import xarray as xr
from .reference import build,CANDIDATES
TASK='cca-seasonal-reproduction'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def initial(repo,source):
    root=repo/'var/private/tasks'/TASK;inputs=root/'agent-inputs';controller=root/'controller';material=repo/'tasks'/TASK/'source-material'
    for d in (inputs,controller,material):d.mkdir(parents=True,exist_ok=True)
    if (inputs/'predictors.nc').exists():raise ValueError('Inputs already frozen')
    years=np.arange(1993,2024);data=source/'v4zeek/data'
    xrows=[];xlat=[];xlon=[];xnames=[]
    for box,latitudes,longitudes in [('nino34',[-4,0,4],[200,215,230]),('iod_w',[-8,0,8],[52,60,68]),('iod_e',[-8,-4,0],[92,94,96])]:
        with xr.open_dataset(data/f'sst_{box}_monthly.nc') as ds:
            for lat in latitudes:
                for lon in longitudes:
                    p=ds.sst.sel(lat=lat,lon=lon,method='nearest')
                    vals=[float(p.sel(time=slice(f'{year}-06-01',f'{year}-08-31')).mean()) for year in years]
                    xrows.append(vals);xlat.append(float(p.lat));xlon.append(float(p.lon));xnames.append(f'{box}:{float(p.lat):g}:{float(p.lon):g}')
    yrows=[];ylat=[];ylon=[];ynames=[]
    with xr.open_dataset(data/'ea_precip_monthly.nc') as ds:
        for lat in [-2,0,2]:
            for lon in [35,36,38,40]:
                p=ds.precip.sel(lat=lat,lon=lon,method='nearest')
                vals=[float(p.sel(time=slice(f'{year}-10-01',f'{year}-12-31')).sum(skipna=False)*30) for year in years]
                yrows.append(vals);ylat.append(float(p.lat));ylon.append(float(p.lon));ynames.append(f'{float(p.lat):.6f}:{float(p.lon):.6f}')
    x=np.array(xrows).T;y=np.array(yrows).T
    if not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('Selected actual source support contains missing values')
    xd=xr.Dataset({'sst':(('year','predictor'),x)},coords={'year':years,'predictor':xnames,'predictor_lat':('predictor',xlat),'predictor_lon':('predictor',xlon)})
    xd.sst.attrs={'units':'degree_Celsius','processing':'Arithmetic June July August monthly observed ERA5 SST mean at selected native cells; no fitting or anomalies'}
    yd=xr.Dataset({'rainfall':(('year','target'),y)},coords={'year':years,'target':ynames,'target_lat':('target',ylat),'target_lon':('target',ylon)})
    yd.rainfall.attrs={'units':'mm','processing':'Sum native monthly CHIRPS OND totals at selected land cells; multiplied legacy scaled monthly source by30 to undo adapter normalization'}
    xd.to_netcdf(inputs/'predictors.nc');yd.sel(year=slice(1993,2019)).to_netcdf(inputs/'targets.nc');yd.sel(year=slice(2020,2023)).to_netcdf(controller/'private-targets.nc')
    records={str(p.relative_to(source)):{'sha256':digest(p),'bytes':p.stat().st_size} for p in [data/'ea_precip_monthly.nc',*[data/f'sst_{b}_monthly.nc' for b in ['nino34','iod_w','iod_e']]]}
    (material/'original-files.json').write_text(json.dumps(records,indent=2)+'\n')
    excerpts=[('pycpt-probabilistic-route.py.txt',source/'iri-pycpt/pycpt/src/pycpt/notebook.py',380,410),('africas2s-cca-method.py.txt',source/'africas2s/src/africas2s/methods/cca.py',1,410),('africas2s-method-record.txt',source/'africas2s/scripts/benchmark_pycpt.py',1,98)]
    for name,path,start,end in excerpts:
        txt=f'# Frozen source {path.relative_to(source)}, lines {start}-{end}\n'+''.join(path.read_text().splitlines(keepends=True)[start-1:end])
        (material/name).write_text(txt);(inputs/name).write_text(txt)
    (inputs/'candidates.json').write_text(json.dumps([{'id':i,'x_eof':a,'y_eof':b,'cca':c} for i,(a,b,c) in enumerate(CANDIDATES)],indent=2)+'\n')
    (inputs/'source-manifest.json').write_text(json.dumps({'sources':['chirps3','era5-sst','legacy-normalization','pycpt-source','africas2s-source']},indent=2)+'\n')
    shutil.copyfile(repo/'tasks'/TASK/'algorithm.md',inputs/'algorithm.md')

def prepare(repo=None,initialize=False):
    repo=Path(repo) if repo is not None else Path(__file__).resolve().parents[3]
    root=repo/'var/private/tasks'/TASK;controller=root/'controller'
    started=time.monotonic();a=build(root/'agent-inputs');b=build(root/'agent-inputs',backend='eigen')
    delta={}
    for filename,one,two in zip(['hindcasts.nc','forecast.nc'],a[:2],b[:2]):
        for k in one.data_vars:
            np.testing.assert_allclose(one[k],two[k],rtol=2e-9,atol=2e-7)
            delta[f'{filename}:{k}']=float(np.max(np.abs(one[k].values-two[k].values)))
        dest=controller/filename
        if initialize:
            if dest.exists():raise ValueError('Reference already frozen')
            one.to_netcdf(dest)
        else:
            with xr.open_dataset(dest) as old:xr.testing.assert_allclose(one,old,rtol=1e-12,atol=1e-12)
    audit={'task':TASK,'source_weather_is_synthetic':False,'methods':['NumPy thin SVD','SciPy symmetric covariance eigendecomposition and gesvd canonical decomposition'],'maximum_absolute_errors':delta,'all_selected_modes_equal':True,'candidate_count':len(CANDIDATES),'outer_years':[2005,2019],'training_years':[1993,2019],'private_years':[2020,2023],'human_scientific_approval':False,'cpt_binary_executed':False,'full_paper_reproduction':False,'reference_seconds':time.monotonic()-started}
    if initialize:
        (controller/'model.json').write_text(json.dumps(a[2],indent=2)+'\n');(controller/'reference-audit.json').write_text(json.dumps(audit,indent=2)+'\n');write_manifest(repo,root)
    return audit

def write_manifest(repo,root):
    package=repo/'tasks'/TASK
    rows=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file():continue
        rel=str(p.relative_to(root));r={'file':rel,'sha256':digest(p),'bytes':p.stat().st_size,'visibility':'agent' if rel.startswith('agent-inputs/') else 'controller_only'}
        if p.suffix=='.nc':
            with xr.open_dataset(p) as d:r.update(dimensions=dict(d.sizes),variables={k:{'dimensions':list(v.dims),'units':v.attrs.get('units')} for k,v in d.data_vars.items()})
        rows.append(r)
    code=repo/'weatherbench/task_tools/cca_seasonal/reference.py'
    manifest={'schema_version':1,'task':TASK,'status':'local_development_snapshot','local_storage':str(root.relative_to(repo)),'files':rows,'reference_code_path':str(code.relative_to(repo)),'reference_code_sha256':digest(code),'reference_validation':'Independent SVD/eigendecomposition across all candidate scores/predictions/probabilities','source_records':[{'path':str(p.relative_to(repo)),'sha256':digest(p)} for p in sorted(package.rglob('*')) if p.is_file() and p.name not in ['input-manifest.json','review.html']]}
    (package/'input-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
