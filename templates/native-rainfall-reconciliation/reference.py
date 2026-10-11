"""Delivery reconciliation of real ECMWF weather with an explicit derived channel."""
import importlib.util
import json,shutil
from pathlib import Path
import numpy as np
import xarray as xr
from assessment.sources import restore
HERE=Path(__file__).resolve().parent


def _module(name):
    spec=importlib.util.spec_from_file_location('reconciliation_'+name,HERE/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def prepare(private,source_dir):return restore(HERE,private,source_dir)


def candidate_instances():
    return [{'id':name,'rectangle':box,'period_start':periods} for name,box,periods in [
        ('service-area--weeks-1-2',{'south':-5,'north':5,'west':34,'east':42},['2026-09-27','2026-10-04']),
        ('coast--weeks-2-3',{'south':-4.5,'north':1.5,'west':39,'east':42},['2026-10-04','2026-10-11']),
        ('north-west--weeks-1-2',{'south':0.5,'north':6,'west':33,'east':38},['2026-09-27','2026-10-04'])]]


def brief_fields(params):return {'rectangle':json.dumps(params['rectangle']),'periods':', '.join(params['period_start'])}


def stage_inputs(private,params,destination):
    shutil.copytree(Path(private)/'agent-inputs',destination)
    (Path(destination)/'instance.json').write_text(json.dumps(params)+'\n')


def perturb_inputs(inputs,seed,kind='data'):
    inputs=Path(inputs);rng=np.random.default_rng(seed)
    if kind=='bulletin':
        (inputs/'prior-bulletin.json').write_text(json.dumps({'regional_change_mm':rng.uniform(-10000,10000,2).tolist(),'direction':['drier','wetter'],'status':'Non-authoritative draft; do not use as computational input.'})+'\n');return
    if kind!='data':raise ValueError(kind)
    import zarr
    store=zarr.open_group(inputs/'ECMWF_s2s_precip_2026-09-27.zarr',mode='r+');arr=store['tp'];names=list(arr.metadata.dimension_names);values=np.asarray(arr[...],dtype=float);shape=[1]*values.ndim;shape[names.index('step')]=values.shape[names.index('step')]
    values+=np.arange(shape[names.index('step')]).reshape(shape)*rng.uniform(.5,2);arr[...]=np.round(values*32)/32
    path=inputs/'previous-interval-rates.nc'
    with xr.open_dataset(path,engine='h5netcdf') as d:changed=d.load()
    attrs=dict(changed.rain_rate.attrs);changed['rain_rate']=changed.rain_rate*rng.uniform(.7,1.4);changed.rain_rate.attrs=attrs;temporary=path.with_suffix('.tmp');changed.to_netcdf(temporary,engine='h5netcdf');temporary.replace(path)


def reference(inputs,params,conventions):return _module('science').compute(inputs,params,conventions)
def independent(inputs,params,conventions):return _module('reference_independent').reference(inputs,params,conventions)
INVARIANCE_PROBES={'bulletin_independence':{'perturb':'bulletin','unchanged':lambda results,*_:results,'passes':'Non-authoritative bulletin changes leave all computed arrays unchanged.','fails':'Computed weather depends on a non-authoritative bulletin.'}}


def difference(results,params,inputs=None):
    gap=float(np.max(np.abs(results['change_mm']-(results['current_mean_mm']-results['previous_mean_mm']))));return gap<=2*(101+101+203)*2**-24*200,f'Maximum difference identity error {gap:g} mm.'
def region(results,params,inputs=None):
    x=results['change_mm'];v=results['regional_change_mm'];ok=bool(np.all((v>=x.min((1,2))-2*371*2**-24*200)&(v<=x.max((1,2))+2*371*2**-24*200)));return ok,'Regional changes lie within cell changes.'
INVARIANTS={'difference_identity':difference,'regional_range':region}


def expected_claims(results,params):return {'direction':[{'wetter'} if x>1e-3 else {'drier'} if x< -1e-3 else {'unchanged','wetter','drier'} for x in results['regional_change_mm']]}
