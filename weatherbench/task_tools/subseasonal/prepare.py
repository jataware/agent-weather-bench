"""Prepare initial data explicitly; normal preparation only verifies frozen bytes."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import xarray as xr

from .baseline import fit, predict

TASK = 'subseasonal-optimization'
SOURCE_IDS = ['subseasonalclimateusa-paper', 'adaptive-bias-correction',
              'subseasonal-data', 'cpc-precipitation', 'cfsv2-reforecasts',
              'source-notes', 'baseline-code']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_dataset(path, dataset, initialize=False):
    if not path.exists():
        if not initialize:
            raise ValueError(f'Missing frozen dataset: {path}')
        dataset.to_netcdf(path)
    else:
        with xr.open_dataset(path) as previous:
            xr.testing.assert_identical(previous, dataset)


def frozen_bytes(path, content, initialize=False):
    if not path.exists():
        if not initialize:
            raise ValueError(f'Missing frozen material: {path}')
        path.write_bytes(content)
    elif path.read_bytes() != content:
        raise ValueError(f'Frozen supplied material changed: {path}; version the task')


def write_manifest(repo):
    """Authoring action only: record current data/material hashes explicitly.

    This does not create or rewrite weather data. Invoke only before a solver
    attempt, or as part of a declared new task version.
    """
    repo = Path(repo)
    root = repo / 'var/private/tasks' / TASK
    inputs = root / 'agent-inputs'
    package = repo / 'tasks' / TASK
    records = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        record = {'file': str(path.relative_to(root)), 'sha256': digest(path),
                  'bytes': path.stat().st_size,
                  'visibility': 'agent' if inputs in path.parents else 'controller_only'}
        if path.suffix == '.nc':
            with xr.open_dataset(path) as dataset:
                record['dimensions'] = dict(dataset.sizes)
                record['variables'] = {
                    name: {'dimensions': list(variable.dims), 'units': variable.attrs.get('units')}
                    for name, variable in dataset.data_vars.items()}
        records.append(record)
    material = [path for path in sorted(package.rglob('*'))
                if path.is_file() and path.name not in ('input-manifest.json', 'review.html')]
    # Hash the scientific construction/scoring implementation as well as source
    # notes and public experiment contract. Generated review HTML stays excluded.
    material.extend(Path(__file__).with_name(name) for name in
                    ('baseline.py', 'metrics.py', 'prepare.py', 'checks.py',
                     'evaluation.py', 'extract.py', 'acquire.py'))
    reference = Path(__file__).with_name('metrics.py')
    manifest = {
        'schema_version': 1, 'task': TASK, 'status': 'local_development_snapshot',
        'local_storage': str(root.relative_to(repo)), 'files': records,
        'source_record_root': 'repository', 'expert_approval': False,
        'public_redistribution_review': 'pending',
        'reference_code_path': str(reference.relative_to(repo)),
        'reference_code_sha256': digest(reference),
        'reference_validation': {
            'fixed_splits_before_skill_comparison': True,
            'reference_is_baseline_not_required_optimizer': True,
            'historical_public_targets_not_pristine': True},
        'source_records': [
            {'path': str(path.relative_to(repo)), 'sha256': digest(path),
             'original_locator': 'repository-owned experiment/scientific material'}
            for path in material]}
    (package / 'input-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def verify_manifest(repo):
    repo = Path(repo)
    root = repo / 'var/private/tasks' / TASK
    path = repo / 'tasks' / TASK / 'input-manifest.json'
    if not path.is_file():
        raise ValueError('Missing frozen input manifest; initialization must be explicit')
    manifest = json.loads(path.read_text())
    if manifest['task'] != TASK:
        raise ValueError('Wrong task manifest')
    for row in manifest['files']:
        file = root / row['file']
        if not file.is_file() or file.stat().st_size != row['bytes'] or digest(file) != row['sha256']:
            raise ValueError(f'Frozen data bytes differ or are missing: {file}')
    for row in manifest['source_records']:
        file = repo / row['path']
        if not file.is_file() or digest(file) != row['sha256']:
            raise ValueError(f'Frozen scientific material differs or is missing: {file}')
    if digest(repo / manifest['reference_code_path']) != manifest['reference_code_sha256']:
        raise ValueError('Frozen metric implementation differs')
    return manifest


def prepare(repo=None, initialize=False):
    """Default is a read-only verification/recomputation with JSON audit return."""
    repo = Path(repo) if repo is not None else Path(__file__).resolve().parents[3]
    root = repo / 'var/private/tasks' / TASK
    inputs, controller = root / 'agent-inputs', root / 'controller'
    if initialize:
        inputs.mkdir(parents=True, exist_ok=True)
    else:
        verify_manifest(repo)
    with xr.open_dataset(controller / 'source-subset.nc') as file:
        source = file.load()
    end = source.target_start + np.timedelta64(14, 'D')
    masks = {
        'training': end < np.datetime64('2015-01-01'),
        'development': ((source.issue_time >= np.datetime64('2015-01-01'))
                        & (end < np.datetime64('2018-01-01'))),
        'final': ((source.issue_time >= np.datetime64('2018-01-01'))
                  & (source.issue_time < np.datetime64('2022-01-01')))}
    train = source.sel(issue_time=masks['training'])
    state = fit(train)
    frozen_dataset(inputs / 'training.nc', train, initialize)
    counts = {'training': int(train.sizes['issue_time'])}
    for split in ('development', 'final'):
        dataset = source.sel(issue_time=masks[split])
        counts[split] = int(dataset.sizes['issue_time'])
        features = dataset.drop_vars('precipitation')
        targets = dataset.drop_vars('raw_cfsv2')
        frozen_dataset(inputs / f'{split}-features.nc', features, initialize)
        frozen_dataset(controller / f'{split}-targets.nc', targets, initialize)
        baselines = xr.Dataset({
            'raw_cfsv2': dataset.raw_cfsv2,
            'climatology': predict(features, state, 'climatology').precipitation,
            'bias_corrected': predict(features, state, 'bias').precipitation})
        frozen_dataset(controller / f'{split}-baselines.nc', baselines, initialize)
    for name in ('baseline.py', 'source-notes.txt'):
        original = (Path(__file__).with_name(name) if name.endswith('.py')
                    else repo / 'tasks' / TASK / 'source-material' / name)
        frozen_bytes(inputs / name, original.read_bytes(), initialize)
    source_bytes = (json.dumps({'sources': SOURCE_IDS}, indent=2) + '\n').encode()
    frozen_bytes(inputs / 'source-manifest.json', source_bytes, initialize)
    if initialize:
        write_manifest(repo)
    manifest = verify_manifest(repo)
    return {
        'task': TASK, 'frozen_data_verified': True, 'references_recomputed': True,
        'files_verified': len(manifest['files']),
        'source_records_verified': len(manifest['source_records']),
        'issues': counts, 'locations': int(source.sizes['location']),
        'agent_input_bytes': sum(path.stat().st_size for path in inputs.iterdir()),
        'model_calls': 0, 'agent_attempts': 0,
        'preparation_writes': bool(initialize), 'historical_public_targets_not_pristine': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--initialize', action='store_true',
                        help='Explicit authoring initialization; never rewrites weather bytes')
    parser.add_argument('--repo', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.repo, initialize=args.initialize), indent=2))


if __name__ == '__main__':
    main()
