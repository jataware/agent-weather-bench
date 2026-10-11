"""Trusted forecast controls still retrieve the declared HTTP resources."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
from urllib.request import urlopen
import numpy as np
import science


def acquire(inputs, destination):
    config = json.loads((Path(inputs) / 'acquisition.json').read_text())
    base = config['base_url'].rstrip('/') + '/'
    with urlopen(base + config['catalog_path'], timeout=30) as response:
        catalog = json.loads(response.read(1024*1024))
    needed = ['models/' + name + '.nc' for name in science.MODELS] + ['observations/training.nc']
    resources = {row['path']: row for row in catalog['resources']}
    for name in needed:
        row = resources[name]; path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or not 0 < row['bytes'] < 128*1024*1024:
            raise ValueError('Invalid resource')
        with urlopen(base + name, timeout=60) as response:
            content = response.read(row['bytes']+1)
        if len(content) != row['bytes'] or hashlib.sha256(content).hexdigest() != row['sha256']:
            raise ValueError('Source hash mismatch')
        target = Path(destination) / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--inputs', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    variant = json.loads(Path('variant.json').read_text())['defect']
    params = json.loads((Path(args.inputs) / 'instance.json').read_text())
    with tempfile.TemporaryDirectory(prefix='synthesis-acquired-') as directory:
        acquire(args.inputs, directory); models, observations = science.load(directory)
        kind = variant if variant in ('climatology', 'raw_models') else 'expert'
        result = science.forecast(models, observations, params, kind)
        if variant == 'future_pooling':
            # Tempting but forbidden transductive correction uses all target years.
            field = models['ecmwf'].sel(year=params['forecast_years']).mean(('year','member'))
            offset = .08*np.tanh((np.asarray(field)-np.asarray(observations.mean('year')))/100)
            result.forecast_probability.values[:,0] += offset
            result.forecast_probability.values[:,2] -= offset
            # A convex uniform mix ensures this fault isolates future dependence.
            result.forecast_probability.values[:] = .3*result.forecast_probability.values+.7/3
        if variant == 'percent':
            result.forecast_probability.values[:] *= 100
        if variant == 'wrong_sum':
            result.forecast_probability.values[:] *= .8
        if variant == 'reordered':
            result = result.isel(lat=slice(None,None,-1), forecast_year=slice(None,None,-1), tercile=slice(None,None,-1)).transpose('lon','tercile','lat','forecast_year')
    result.to_zarr(output / 'results.zarr', mode='w', zarr_format=3, consolidated=False)
    (output / 'answer.json').write_text(json.dumps({'run': {'argv': ['python','solve.py','--inputs','{input_dir}','--output','{output_dir}']}, 'claims': {}})+'\n')
    (output / 'report.md').write_text('A trusted '+variant+' control acquired and hash-checked curator-normalized seasonal rainfall. The expert uses train-only chronological model/shrinkage selection and fixed fitting on 1993-2004; climatology and raw-centre alternatives are valid. No withheld verification score is claimed.\n')


if __name__ == '__main__':
    main()
