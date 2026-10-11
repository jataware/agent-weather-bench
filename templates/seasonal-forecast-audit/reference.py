"""Method-free forecast validity, controlled interventions and numerical audit."""
import importlib.util
import json
import shutil
from pathlib import Path
import numpy as np
import xarray as xr
from assessment.sources import restore

HERE=Path(__file__).resolve().parent
RESPONSE_PERTURBATIONS=('training_targets', 'features')
RESPONSE_GROUPS={'hindcast':['hindcast_mm'],'production':['forecast_mm']}
CASES={
 'case-a': {'centering_scope':'training_fold','select_scope':'fixed'},
 'case-b': {'centering_scope':'whole_record','select_scope':'fixed'},
 'case-c': {'centering_scope':'training_fold','select_scope':'whole_record'},
 'case-d': {'centering_scope':'training_fold','select_scope':'fixed'},
}
REPORTS={
 'case-a':'All preprocessing is fitted within each expanding training fold. The 2005–2019 hindcasts are descriptive retrospective evaluation, using final-vintage data. They are not independent evidence of operational deployment skill.',
 'case-b':'The transform is fitted once for stable anomalies, then every regression fit uses earlier years only. These hindcasts are entirely past-only and provide independent validation of the complete learning procedure.',
 'case-c':'Predictors are screened once to remove irrelevant SST features. Each reported year is excluded from its regression fit, so these hindcasts independently validate the entire selection and fitting procedure.',
 'case-d':'We inspected these 2005–2019 scores during development to choose the final architecture and retained this configuration. The same scores are an independent final test and establish deployment readiness for East Africa.',
}


def module(name):
    spec=importlib.util.spec_from_file_location('audit_'+name,HERE/(name+'.py'))
    out=importlib.util.module_from_spec(spec);spec.loader.exec_module(out);return out


def prepare(private,source_dir=None):
    root=HERE.parents[1]
    return restore(HERE,private,source_dir or root/'var/private/templates/seasonal-cca-reproduction')


def candidate_instances(): return [{'id':case,'case':case} for case in CASES]
def brief_fields(params):
    return {'candidate_config':json.dumps(CASES[params['case']],indent=2),
            'candidate_report':REPORTS[params['case']],
            'candidate_source':(HERE/'candidate_science.py').read_text()}


def stage_inputs(private,params,destination):
    dst=Path(destination);dst.mkdir(parents=True)
    for name in ('predictors.nc','targets.nc','source-manifest.json'):
        shutil.copyfile(Path(private)/'agent-inputs'/name,dst/name)
    for name in ('candidate-pipeline.py','candidate_science.py','scientific-objective.md','source-records.yaml'):
        shutil.copyfile(HERE/name,dst/name)
    (dst/'candidate-config.json').write_text(json.dumps(CASES[params['case']],indent=2)+'\n')
    (dst/'candidate-report.md').write_text(REPORTS[params['case']]+'\n')
    (dst/'instance.json').write_text(json.dumps({'id':params['id']})+'\n')


def expected_coordinates(inputs,params):
    with xr.open_dataset(Path(inputs)/'targets.nc') as ds: n=ds.sizes['target']
    return {'hindcast_year':np.arange(2005,2020),'forecast_year':np.arange(2020,2024),'target':np.arange(n)}


def _rewrite(path,change):
    with xr.open_dataset(path) as ds: data=ds.load()
    change(data);tmp=path.with_suffix('.tmp');data.to_netcdf(tmp);tmp.replace(path)


def perturb_inputs(inputs,seed,kind='training_targets'):
    inputs=Path(inputs);rng=np.random.default_rng(seed)
    if kind == 'training_targets' or kind.startswith('cut_'):
        cut=int(kind.split('_')[1]) if kind.startswith('cut_') else 1993
        with xr.open_dataset(inputs/'predictors.nc') as ds: x=ds.sst.sel(year=np.arange(1993,2020)).values[:,-1]
        def change(ds):
            values=ds.rainfall.values.copy();mask=ds.year.values>=cut
            # Structured intervention also challenges outcome-based feature screening.
            shifted=700+200*(x[mask]-x.mean())[:,None]+rng.uniform(20,60,(mask.sum(),values.shape[1]))
            values[mask]=np.maximum(shifted,1)
            ds['rainfall']=(ds.rainfall.dims,values,ds.rainfall.attrs)
        _rewrite(inputs/'targets.nc',change)
        if kind.startswith('cut_'):
            def future_features(ds):
                values=ds.sst.values.copy();mask=ds.year.values>cut
                values[mask]+=rng.normal(5,1,(mask.sum(),values.shape[1]))
                ds['sst']=(ds.sst.dims,values,ds.sst.attrs)
            _rewrite(inputs/'predictors.nc',future_features)
    elif kind in ('features','later_forecast','production_2021','production_2023'):
        def change(ds):
            values=ds.sst.values.copy();boundary=2022 if kind=='later_forecast' else int(kind.split('_')[1]) if kind.startswith('production_') else 1993;mask=ds.year.values>=boundary
            values[mask]+=rng.normal(2,0.3,(mask.sum(),values.shape[1]))
            ds['sst']=(ds.sst.dims,values,ds.sst.attrs)
        _rewrite(inputs/'predictors.nc',change)
    else: raise ValueError(kind)


def _early(cut):
    return lambda results,inputs,params: {'hindcast_mm':results['hindcast_mm'][results['hindcast_year']<=cut]}


INVARIANCE_PROBES={
 'first_year_isolation':{'perturb':'cut_2005','unchanged':_early(2005),'passes':'The first hindcast excludes its own and later targets.','fails':'The first hindcast uses its own or later targets.'},
 'middle_year_isolation':{'perturb':'cut_2012','unchanged':_early(2012),'passes':'Hindcasts through 2012 exclude targets from 2012 onward.','fails':'A hindcast through 2012 changes when 2012 or later targets change.'},
 'last_year_isolation':{'perturb':'cut_2019','unchanged':_early(2019),'passes':'All hindcasts exclude the final year target.','fails':'A hindcast changes when the final year target changes.'},
 'forecast_batch_isolation':{'perturb':'later_forecast','unchanged':lambda r,i,p:{'forecast_mm':r['forecast_mm'][:2]},'passes':'2020–2021 forecasts ignore 2022–2023 predictors.','fails':'An earlier production forecast uses later predictors.'},
}


for _year in range(2005,2020):
    if _year not in (2005,2012,2019):
        INVARIANCE_PROBES[f'year_{_year}_isolation']={
            'perturb':f'cut_{_year}', 'unchanged':_early(_year),
            'passes':f'Hindcasts through {_year} exclude target observations from {_year} onward.',
            'fails':f'A hindcast through {_year} changes when {_year} or later targets change.'}


for _year in (2021,2023):
    INVARIANCE_PROBES[f'production_{_year}_isolation']={
        'perturb':f'production_{_year}',
        'unchanged':lambda r,i,p,year=_year:{'forecast_mm':r['forecast_mm'][:year-2020]},
        'passes':f'Production forecasts before {_year} ignore {_year} and later predictors.',
        'fails':f'A production forecast before {_year} uses {_year} or later predictors.'}


def _nonnegative(r,p,i):
    value=min(float(r[n].min()) for n in ('hindcast_mm','forecast_mm'))
    return value>=0,f'Smallest repaired rainfall total: {value:.8g} mm.'


def _original(r,p,i):
    want=module('candidate_science').original(i)
    gap=float(np.max(np.abs(r['original_hindcast_mm']-want)))
    return gap<=np.finfo(np.float64).eps*1000000*10000,f'Original candidate reconstruction maximum difference: {gap:.8g} mm.'


def _metrics(r,p,i):
    with xr.open_dataset(Path(i)/'targets.nc') as ds: t=ds.load()
    y=t.rainfall.sel(year=r['hindcast_year']).values
    cl=np.array([t.rainfall.sel(year=t.year[t.year<year]).mean('year').values for year in r['hindcast_year']])
    expected={'original_rmse_mm':np.sqrt(np.mean((r['original_hindcast_mm']-y)**2)),
              'hindcast_rmse_mm':np.sqrt(np.mean((r['hindcast_mm']-y)**2)),
              'climatology_rmse_mm':np.sqrt(np.mean((cl-y)**2))}
    gap=max(abs(float(r[n])-v) for n,v in expected.items())
    return gap<=np.finfo(np.float32).eps*10000,f'Maximum reported metric error: {gap:.8g} mm.'


INVARIANTS={'nonnegative_rainfall':_nonnegative,'original_evaluation':_original,'metric_identity':_metrics}


def expected_claims(r,p):
    measured=score(r,p,HERE.parents[1]/'var/private/templates/seasonal-forecast-audit')
    return {'original_hindcast_is_past_only':[['yes' if p['case'] in ('case-a','case-d') else 'no']],
            'original_report_supported':[['yes' if p['case']=='case-a' else 'no']],
            'repaired_beats_climatology':[['yes' if measured['rmse_mm']<measured['climatology_rmse_mm']-1e-9 else 'no']]}


def _truth(private):
    with xr.open_dataset(Path(private)/'agent-inputs/targets.nc') as ds: return ds.load()


def score(r,p,private,split='hindcast'):
    t=_truth(private);y=t.rainfall.sel(year=np.arange(2005,2020)).values
    cl=np.array([t.rainfall.sel(year=t.year[t.year<year]).mean('year').values for year in range(2005,2020)])
    rmse=float(np.sqrt(np.mean((r['hindcast_mm']-y)**2)))
    baseline=float(np.sqrt(np.mean((cl-y)**2)))
    return {'split':split,'rmse_mm':rmse,'climatology_rmse_mm':baseline,'skill_vs_climatology':1-rmse/baseline,'years':15,'cells':y.shape[1]}


def independent_score(r,p,private,split='hindcast'):
    return module('reference_independent').score(r,p,private,split)


def baseline_results(private,p,which):
    t=_truth(private)
    return {'hindcast_mm':np.array([t.rainfall.sel(year=t.year[t.year<year]).mean('year').values for year in range(2005,2020)])}


def regression_checks(scratch):
    import tempfile
    rows=[]
    with tempfile.TemporaryDirectory() as folder:
        for params in candidate_instances():
            path=Path(folder)/params['id']; stage_inputs(HERE.parents[1]/'var/private/templates/seasonal-forecast-audit',params,path)
            a=module('candidate_science').original(path);b=module('reference_independent').original(path)
            gap=float(np.max(np.abs(a-b)))
            rows.append({'name':'independent original audit '+params['id'],'passed':bool(gap<=np.finfo(np.float64).eps*1000000*10000),'detail':f'maximum primal/dual difference {gap:.8g} mm'})
    return rows


def response_results(results,inputs,params):
    """Only repaired predictions demonstrate forecasting input dependence."""
    return {name:results[name] for name in ('hindcast_mm','forecast_mm')}
