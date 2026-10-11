"""Independent-match product task; old assessment rules are deliberately unused."""
import hashlib
import importlib.util
import json
from functools import lru_cache
from pathlib import Path
import shutil
import numpy as np
import xarray as xr
HERE=Path(__file__).resolve().parent


@lru_cache(None)
def _module(name):
    spec=importlib.util.spec_from_file_location('consolidation_'+name,HERE/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def prepare(private,source_dir=None):
    from assessment.sources import restore
    return restore(HERE,private,source_dir or private)


def candidate_instances():
    return [{'id':'aso-2026--full-source-grid','season':'ASO2026','nominal_weights':[2,8,8]}]


def brief_fields(params):return {}


def stage_inputs(private,params,destination):
    prepare(private);destination=Path(destination);destination.mkdir(parents=True)
    shutil.copytree(Path(private)/'provider',destination/'provider');public=destination/'public';public.mkdir()
    text=json.dumps(params,indent=2)+'\n';(destination/'instance.json').write_text(text);(public/'instance.json').write_text(text)
    (public/'acquisition.json').write_text(json.dumps({'base_url':'http://weather-source:8000','catalog_path':'catalog.json','transport':'immutable source HTTP snapshot'})+'\n')
    _module('acquisition').provider_manifest(destination/'provider')


def expected_coordinates(inputs,params):
    with xr.open_dataset(Path(inputs)/'provider/observed-sst.nc',engine='h5netcdf') as ds:
        return {'tercile':np.arange(3),'lat':np.asarray(ds.lat),'lon':np.asarray(ds.lon)}


def _raw(ds):return {name:ds[name].values for name in ds.variables}


def reference(inputs,params,conventions):return _raw(_module('science').compute(Path(inputs)/'provider',conventions))
def independent(inputs,params,conventions):return _raw(_module('reference_independent').compute(Path(inputs)/'provider',conventions))


def perturb_inputs(inputs,seed,kind='data'):
    if kind!='data':raise ValueError(kind)
    rng=np.random.default_rng(seed);provider=Path(inputs)/'provider'
    for name in _module('science').NAMES:
        path=provider/name
        with xr.open_dataset(path,engine='h5netcdf') as ds:ds=ds.load()
        # First change finite probabilities category-dependently and renormalize;
        # the separate declared partial-vector intervention follows below.
        values=np.stack([np.asarray(ds[c],dtype='float64') for c in ['below','normal','above']])
        finite=np.isfinite(values).all(axis=0)
        values*=rng.uniform(.6,1.5,(3,1,1))
        sums=values.sum(axis=0)
        values=np.where(finite[None],values/sums[None]*100,values)
        for i,c in enumerate(['below','normal','above']):ds[c].values[:]=values[i]
        tmp=path.with_suffix('.tmp.nc');ds.to_netcdf(tmp,engine='h5netcdf');tmp.replace(path)
    # Supplementary controller perturbation, never a claim about historical
    # missingness: make one formerly complete component vector partial where
    # another genuine component remains. This catches per-category nanmean.
    source,_,_=_module('science').load(provider)
    support=np.isfinite(source).all(axis=1)
    candidates=np.argwhere(support[0] & (support.sum(axis=0)>=2))
    if len(candidates)==0:raise ValueError('No overlapping support for partial-vector probe')
    j,k=map(int,candidates[seed % len(candidates)])
    path=provider/'observed-sst.nc'
    with xr.open_dataset(path,engine='h5netcdf') as ds:ds=ds.load()
    ds['normal'].values[j,k]=np.nan
    tmp=path.with_suffix('.tmp.nc');ds.to_netcdf(tmp,engine='h5netcdf');tmp.replace(path)
    catalog=json.loads((provider/'catalog.json').read_text())
    for row in catalog['resources']:
        path=provider/row['path'];row.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
    (provider/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')


def simplex_and_support(results,params,inputs):
    source,_,_=_module('science').load(Path(inputs)/'provider');expected=np.isfinite(source).all(axis=1).sum(axis=0)
    actual=results['available_components'];valid=np.array_equal(actual,expected)
    for name in ['probability','nominal_weighted_probability']:
        p=results[name];support=expected>0
        valid=valid and np.all(p[:,~support]==0) and np.all(np.isfinite(p[:,support])) and np.all(p[:,support]>=-1e-6) and np.all(p[:,support]<=1+1e-6) and np.all(np.abs(p[:,support].sum(axis=0)-1)<1e-6)
    valid=valid and np.all(results['disagreement_pp'][:,expected==0]==0) and np.all(results['disagreement_pp']>=-1e-6) and np.all(results['disagreement_pp']<=100+1e-6)
    return bool(valid),'Source-complete vector counts, normalized fractions on supported cells; explicit zero storage fills where count0 means no forecast.'


INVARIANTS={'simplex_and_support':simplex_and_support}

def expected_claims(results,params):return {}


def regression_checks(inputs):
    # Supplementary edge fixtures exercise complete-vector rejection independently
    # of which missingness patterns happen to occur in this real source snapshot.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='consolidation-regression-') as temp:
        provider=Path(temp)
        vectors=[[[20,30,50],[np.nan,np.nan,np.nan],[10,np.nan,90]],[[40,30,30],[np.nan,np.nan,np.nan],[20,40,40]],[[np.nan,np.nan,np.nan],[np.nan,np.nan,np.nan],[np.nan,np.nan,np.nan]]]
        for name,values in zip(_module('science').NAMES,vectors):
            a=np.asarray(values).T[:,None,:]
            xr.Dataset({c:(('lat','lon'),a[i]) for i,c in enumerate(['below','normal','above'])},coords={'lat':[0.],'lon':[0.,1.,2.]}).to_netcdf(provider/name,engine='h5netcdf')
        a=_module('science').compute(provider);b=_module('reference_independent').compute(provider)
        agreement=all(np.allclose(a[n],b[n],equal_nan=True,atol=1e-12) for n in a.variables)
        correct=(np.array_equal(a.available_components,[[2,0,1]]) and np.allclose(a.probability[:,0,0],[.3,.3,.4]) and np.all(a.probability[:,0,1]==0) and np.allclose(a.probability[:,0,2],[.2,.4,.4]) and np.allclose(a.disagreement_pp[:,0,2],0))
        return [{'name':'complete_vectors_missing_support_and_single_component','passed':bool(correct and agreement)}]


def sandbox_factory(*args,**kwargs):return _module('acquisition').sandbox_factory(*args,**kwargs)
def executor_factory(executor):return _module('acquisition').executor_factory(executor)
def acquisition_evidence(scratch,destination=None):return _module('acquisition').acquisition_evidence(scratch,destination)
