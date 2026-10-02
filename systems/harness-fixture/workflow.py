"""Reference-like fixture that only sees the public component inputs in its container."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

os.environ['MPLCONFIGDIR'] = '/tmp/weatherbench-matplotlib'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

parser = argparse.ArgumentParser()
parser.add_argument('--inputs',type=Path,default=Path('inputs'))
parser.add_argument('--output',type=Path,required=True)
args = parser.parse_args()
out = args.output
(out / 'inputs').mkdir(parents=True,exist_ok=True)
for file in args.inputs.iterdir():
    if file.is_file(): shutil.copyfile(file,out / 'inputs' / file.name)
names = ['observed-sst.nc','forecast-sst.nc','forecast-precip.nc']
def load(path):
    with path.open('rb') as stream: engine = 'scipy' if stream.read(3)==b'CDF' else 'h5netcdf'
    return xr.load_dataset(path,engine=engine)
datasets = [load(args.inputs / name) for name in names]
raw = np.stack([np.stack([d[v].values for v in ['below','normal','above']]) for d in datasets]).astype('float64')
valid = np.isfinite(raw).all(axis=1)
count = valid.sum(axis=0).astype('int16')
with np.errstate(invalid='ignore',divide='ignore'):
    distributions = raw / raw.sum(axis=1,keepdims=True)
    equal = np.where(valid[:,None],distributions,0).sum(axis=0) / np.maximum(count,1)[None]
    weights = np.array([2,8,8])[:,None,None] * valid
    weighted = np.where(valid[:,None],distributions * weights[:,None],0).sum(axis=0) / np.maximum(weights.sum(axis=0),1)[None]
    # Source probabilities are percent; support is excluded before extrema.
    lo = np.where(valid[:,None],raw,np.inf).min(axis=0)
    hi = np.where(valid[:,None],raw,-np.inf).max(axis=0)
    disagreement = hi-lo
equal[:,count==0] = np.nan
weighted[:,count==0] = np.nan
disagreement[:,count==0] = np.nan
coords = {'tercile':['below','near','above'],'lat':datasets[0].lat,'lon':datasets[0].lon}
ds = xr.Dataset({'probability':(('tercile','lat','lon'),equal,{'units':'1'}),
                 'nominal_weighted_probability':(('tercile','lat','lon'),weighted,{'units':'1'}),
                 'available_components':(('lat','lon'),count),
                 'disagreement_pp':(('tercile','lat','lon'),disagreement,{'units':'percentage_points'})},coords=coords)
ds.to_netcdf(out / 'objective.nc',engine='h5netcdf')
answer = {'supported_cells':int((count>0).sum()),'fully_supported_cells':int((count==3).sum()),
          'single_component_cells':int((count==1).sum()),'maximum_weighting_difference_pp':float(np.nanmax(abs(equal-weighted))*100)}
(out / 'answer.json').write_text(json.dumps(answer,indent=2))
(out / 'workflow.py').write_text(Path(__file__).read_text())
execution = {'schema_version':1,'replay':{'argv':['python','workflow.py','--output','{output_dir}']},
             'retained_files':['workflow.py']+['inputs/'+name for name in names]+['inputs/source-manifest.json'],
             'dependencies':['Scientific libraries pinned by runtime image content ID']}
(out / 'execution.json').write_text(json.dumps(execution,indent=2))
sources = json.loads((args.inputs / 'source-manifest.json').read_text())['sources']
provenance = {'schema_version':1,'sources':[{'id':s,'product_version':'camsopi ASO2026 skill0.3 dry50',
              'access':'supplied','request':{'identifier':s},'retrieved_at':None} for s in sources],
              'files':[{'path':'inputs/'+n,'sha256':hashlib.sha256((out / 'inputs' / n).read_bytes()).hexdigest(),'source_ids':[s]}
                       for n,s in zip(names,sources)] + [{'path':'objective.nc','sha256':hashlib.sha256((out / 'objective.nc').read_bytes()).hexdigest(),'source_ids':[]}],
              'transformations':[{'operation':'Equal available-component combination and sensitivity audit',
               'inputs':['inputs/'+n for n in names],'outputs':['objective.nc'],
               'parameters':{'input_units':'percent','output_units':'fraction','category_mapping':'normal to near','nominal_weights':[2,8,8],
                             'missingness':'Omit missing components; preserve all-missing cells','disagreement_units':'percentage_points'}}]}
(out / 'provenance.json').write_text(json.dumps(provenance,indent=2))
(out / 'report.txt').write_text('ACMAD final objective consolidation, ASO 2026. Equal weights over available components; missing support preserved. Masks (skill0.3, dry50) are inherited. The nominal 2,8,8 case is hypothetical sensitivity, not exact member pooling. Component disagreement is max-minus-min in percentage points. This does not refit CCA, reconstruct forecaster consensus, or establish observed forecast skill. Harness fixture only.\n'+json.dumps(answer))
(out / 'handoff.txt').write_text('Run python workflow.py --output DIRECTORY from retained root, offline. Inputs are copied native component products. This is a zero-model-call harness fixture, not an agent attempt.')
fig,axes = plt.subplots(1,3,figsize=(12,3),constrained_layout=True)
for ax,field,title in zip(axes,[equal[0],count,np.nanmax(abs(equal-weighted),axis=0)*100],
                          ['Below-normal probability (fraction)','Available components (count)','Maximum weighting difference (pp)']):
    im = ax.pcolormesh(ds.lon,ds.lat,field,shading='auto'); fig.colorbar(im,ax=ax)
    ax.set(title=title,xlabel='Longitude',ylabel='Latitude')
fig.suptitle('ASO 2026 · inherited masks · missing support preserved')
fig.savefig(out / 'outlook.png',dpi=120); plt.close(fig)
