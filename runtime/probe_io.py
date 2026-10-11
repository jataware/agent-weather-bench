"""Reproduce native I/O faults inside Docker, never by crashing host Python."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess


CODE = """
import xarray as xr
import sys
print('engine order', xr.get_options()['netcdf_engine_order'], flush=True)
data = []
for name in ('training.nc', 'development-features.nc', 'final-features.nc'):
    kwargs = {} if sys.argv[1] == 'default' else {'engine': sys.argv[1]}
    d = xr.open_dataset('/inputs/' + name, **kwargs)
    data.append(d)
    print(name, dict(d.sizes), len(d.to_dataframe().describe()), flush=True)
print('completed reads', flush=True)
"""


def probe(item):
    image, engine, inputs = item
    result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--read-only',
                             '--memory', '768m', '--cpus', '1', '--cap-drop', 'ALL',
                             '--mount', f'type=bind,src={inputs},dst=/inputs,readonly',
                             '--entrypoint', 'sh', image, '-c',
                             'ulimit -c 0; exec python -c "$1" "$2"', 'probe', CODE, engine],
                            capture_output=True, text=True, timeout=60)
    return {'image': image, 'engine': engine, 'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr,
            'passed': result.returncode == 0 and 'completed reads' in result.stdout}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', required=True)
    p.add_argument('--image', action='append', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    inputs = str(Path(args.inputs).resolve())
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(probe, [(image, engine, inputs) for image in args.image for engine in ('default', 'h5netcdf')]))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps([{k: v for k, v in row.items() if k not in ('stdout', 'stderr')} for row in rows], indent=2))
