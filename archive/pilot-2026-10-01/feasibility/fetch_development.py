"""Small live feasibility fetch. Only the predeclared development years are allowed.

Run with the prepared environment, e.g.:
  ../weather-skills-bench/.venv-accord/bin/python fetch_development.py forecast
  ../weather-skills-bench/.venv-accord/bin/python fetch_development.py observations
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ['ACMADDL_CACHE_DIR'] = str(ROOT / '.cache')
os.environ['ACMADDL_TMP_DIR'] = str(ROOT / '.tmp')
os.environ['NUTHATCH_ROOT_FILESYSTEM'] = 'file://' + str(ROOT / '.cache')
os.environ['NUTHATCH_LOCAL_FILESYSTEM'] = 'file://' + str(ROOT / '.cache')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['forecast', 'observations'])
    args = parser.parse_args()
    from acmaddl import fetch
    for name in ['data', 'results', '.tmp']:
        (ROOT / name).mkdir(exist_ok=True)
    target = ROOT / 'data' / f'{args.kind}-development.nc'
    if target.exists():
        print(f'Already fetched: {target}; not requesting it again.', flush=True)
        return
    common = dict(variable='precip', hindcast=(1993, 2008), cache=False,
                  verbose=False, progress=False, destination=str(target),
                  region_buffer=0, max_retries=1)
    if args.kind == 'forecast':
        product = 'c3s/ecmwf-monthly'
        specific = dict(init='1993-09', target='OND', region=[-3, 1, 36, 39], year_index=False)
    else:
        product = 'obs/chirps-v3-monthly'
        specific = dict(months=[10, 11, 12], region=[-3.5, 1.5, 35.5, 39.5])
    print(f'Fetching {product}, DEVELOPMENT ONLY: 1993–2008', flush=True)
    started = time.monotonic()
    ds = fetch(product, **common, **specific)
    details = {
        'purpose': 'development_feasibility_not_agent_benchmark',
        'product': product, 'years': [1993, 2008], 'parameters': specific,
        'elapsed_seconds': time.monotonic() - started,
        'sizes': dict(ds.sizes),
        'variables': {name: {'dims': list(v.dims), 'attrs': v.attrs} for name, v in ds.data_vars.items()},
        'coordinates': {name: {'dims': list(v.dims), 'first': str(v.values.flat[0]),
                                 'last': str(v.values.flat[-1])} for name, v in ds.coords.items()},
        'packages': {name: importlib.metadata.version(name) for name in ['acmadDL', 'africas2s', 'xarray', 'cdsapi']},
        'file_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'file_bytes': target.stat().st_size,
    }
    output = ROOT / 'results' / f'{args.kind}-fetch.json'
    output.write_text(json.dumps(details, indent=2, default=str) + '\n')
    print(json.dumps(details, indent=2, default=str), flush=True)


if __name__ == '__main__':
    main()
