"""Read-only verify and recompute frozen staged/installed development references."""
import hashlib,json
from pathlib import Path
import xarray as xr
try:from .reference import build
except ImportError:from reference import build

TASK='conservative-downscaling'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_manifest(repo):
    repo=Path(repo);private=repo/'var/private/tasks'/TASK;package=repo/'tasks'/TASK
    rows=[]
    for path in sorted(private.rglob('*')):
        if not path.is_file():continue
        row={'file':str(path.relative_to(private)),'sha256':digest(path),'bytes':path.stat().st_size,'visibility':'agent' if 'agent-inputs' in path.parts else 'controller_only'}
        if path.suffix=='.nc':
            with xr.open_dataset(path) as ds:row.update(dimensions=dict(ds.sizes),variables={n:{'dimensions':list(v.dims),'units':v.attrs.get('units')} for n,v in ds.data_vars.items()})
        rows.append(row)
    paths=[p for p in sorted(package.rglob('*')) if p.is_file() and p.name not in ('input-manifest.json','review.html')]
    paths+=list(Path(__file__).parent.glob('*.py'))
    reference=Path(__file__).with_name('reference.py')
    value={'schema_version':1,'task':TASK,'status':'local_development_snapshot','local_storage':str(private.relative_to(repo)), 'files':rows,'source_record_root':'repository','reference_code_path':str(reference.relative_to(repo)),'reference_code_sha256':digest(reference),'source_records':[{'path':str(p.relative_to(repo)),'sha256':digest(p),'original_locator':'source adaptation/scientific task material'} for p in paths], 'reference_validation':{'independent_spherical_aggregation':True,'positive_affine_scale_invariance':True,'raw_units_resolved':False,'original_paper_replication':False},'expert_approval':False,'public_redistribution_review':'pending'}
    (package/'input-manifest.json').write_text(json.dumps(value,indent=2)+'\n');return value


def prepare(repo=None,initialize=False):
    repo=Path(repo) if repo else Path(__file__).resolve().parents[3];private=repo/'var/private/tasks'/TASK
    if initialize:write_manifest(repo)
    manifest=json.loads((repo/'tasks'/TASK/'input-manifest.json').read_text())
    for row in manifest['files']:
        p=private/row['file']
        if not p.is_file() or p.stat().st_size!=row['bytes'] or digest(p)!=row['sha256']:raise ValueError('Frozen data differs or missing: '+str(p))
    for row in manifest['source_records']:
        if digest(repo/row['path'])!=row['sha256']:raise ValueError('Frozen scientific material differs: '+row['path'])
    for name,expected in zip(('forecast.nc','hindcasts.nc'),build(private/'agent-inputs')[:2]):
        with xr.open_dataset(private/'controller'/name) as actual:xr.testing.assert_allclose(actual,expected,rtol=1e-12,atol=1e-9)
    return {'task':TASK,'files_verified':len(manifest['files']),'references_recomputed':True,'model_calls':0,'agent_attempts':0,'preparation_writes':bool(initialize),'raw_source_units_resolved':False}
