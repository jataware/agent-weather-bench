"""Explicit one-time derivative of an immutable real native source snapshot.

Execute only in a fresh single-thread scientific container. No data downloads,
cache unpickling or old-snapshot edits. The train-selected method is locked to
code and input hashes before any withheld score is calculated.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE = ROOT / 'var/private/templates/mam-multimodel-outlook'
TARGET = ROOT / 'var/private/templates/mam-forecast-synthesis'
PARAMS = {'id': 'kenya-interior--fixed-training-12-blind-seasons',
          'training_years': list(range(1993, 2005)), 'forecast_years': list(range(2005, 2017)),
          'target_latitude': [-2.5, -1.5, -.5, .5, 1.5, 2.5],
          'target_longitude': [36.5, 37.5, 38.5]}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name):
    spec = importlib.util.spec_from_file_location('synthesis_' + name, HERE / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    manifest_path = HERE / 'sources.json'
    if manifest_path.exists():
        for row in json.loads(manifest_path.read_text())['files']:
            assert digest(TARGET / row['file']) == row['sha256'], row['file']
        print('Existing immutable synthesis snapshot verified; no regeneration.')
        return
    assert not TARGET.exists(), 'Do not overwrite partial/frozen data; investigate explicitly.'
    old = json.loads((HERE.parent / 'mam-multimodel-outlook/sources.json').read_text())
    for row in old['files']:
        assert digest(SOURCE / row['file']) == row['sha256'], row['file']
    science, independent = module('native_science'), module('native_independent')
    provider = TARGET / 'provider'; provider.mkdir(parents=True)
    years = PARAMS['training_years'] + PARAMS['forecast_years']
    lat, lon = PARAMS['target_latitude'], PARAMS['target_longitude']
    parity = {}
    for name in ['ecmwf', 'cmcc', 'ukmo', 'meteofrance']:
        source = SOURCE / 'provider/models' / (name + '.nc')
        with xr.open_dataset(source, engine='h5netcdf') as ds:
            native = ds.load()
        total = science.seasonal_model(native, years, lat, lon)
        other = independent.seasonal_model(native, years, lat, lon)
        gap = float(np.max(np.abs(np.asarray(total)-np.asarray(other))))
        assert gap < 1e-9, (name, gap)
        total = total.rename('precip')
        total.attrs.update(units='mm', source_sha256=digest(source), normalization='Calendar-weighted native m/s rates integrated over valid March-April-May, float64; target grid interpolation.')
        path = provider / 'models' / (name + '.nc'); path.parent.mkdir(exist_ok=True)
        total.to_dataset().to_netcdf(path, engine='h5netcdf')
        parity[name] = gap
    source = SOURCE / 'provider/observations/chirps-monthly-pre2016.nc'
    with xr.open_dataset(source, engine='h5netcdf') as ds:
        native = ds.load()
    pre = science.seasonal_observed(native, list(range(1993, 2016)), lat, lon)
    check = independent.seasonal_observed(native, list(range(1993, 2016)), lat, lon)
    parity['chirps_pre2016'] = float(np.max(np.abs(np.asarray(pre)-np.asarray(check))))
    assert parity['chirps_pre2016'] < 1e-9
    train = pre.sel(year=PARAMS['training_years']).rename('precip')
    train.attrs.update(units='mm', source_sha256=digest(source), normalization='Sum three monthly mm totals then bilinear interpolation; only 1993-2004 records served.')
    path = provider / 'observations/training.nc'; path.parent.mkdir(exist_ok=True)
    train.to_dataset().to_netcdf(path, engine='h5netcdf')
    # Train-only fit lock is persisted BEFORE decoding/assembling 2016 or scoring any withheld target.
    methods = module('science'); models, observations = methods.load(provider)
    selection = methods.select_expert(models, observations)
    selection.update({'method_code_sha256': digest(HERE / 'science.py'),
                      'predeclared_design_sha256': digest(ROOT / 'experiments/hard-task-mam-expert-design-2026-10-08.json'),
                      'training_observation_sha256': digest(path),
                      'predictor_sha256': {name: digest(provider / 'models' / (name + '.nc')) for name in methods.MODELS},
                      'lock_precedes_private_score': True})
    write_json(TARGET / 'controller/expert-lock.json', selection)
    # Genuine withheld records from the original snapshot; never enter provider/.
    source2016 = SOURCE / 'private-targets/chirps-monthly-2016.nc'
    with xr.open_dataset(source2016, engine='h5netcdf') as ds:
        native2016 = ds.load()
    last = science.seasonal_observed(native2016, [2016], lat, lon)
    other = independent.seasonal_observed(native2016, [2016], lat, lon)
    parity['chirps_2016'] = float(np.max(np.abs(np.asarray(last)-np.asarray(other))))
    assert parity['chirps_2016'] < 1e-9
    private = xr.concat([pre.sel(year=list(range(2005, 2016))), last], dim='year').rename('precip')
    private.attrs.update(units='mm', visibility='controller-only; never served over HTTP')
    path = TARGET / 'controller/heldout-observations.nc'
    private.to_dataset().to_netcdf(path, engine='h5netcdf')
    provenance = {'source': 'Genuine frozen C3S seasonal monthly model rates and CHIRPS v2 monthly totals',
                  'source_manifest_sha256': digest(HERE.parent / 'mam-multimodel-outlook/sources.json'),
                  'source_manifest': 'templates/mam-multimodel-outlook/sources.json',
                  'source_files': [{k: row[k] for k in ('file', 'sha256', 'bytes')} for row in old['files'] if row['visibility'] == 'provider'],
                  'transformation': 'Curator normalized seasonal totals, not byte-original native products. Four models retain native unequal member counts; common inland service grid. Model/all-year predictors; observations only 1993-2004.',
                  'years_in_observation_service': PARAMS['training_years'],
                  'not_claimed': ['historical operational vintages', 'country-wide Kenya coverage', 'raw GRIB ingestion exercise'],
                  'scientific_normalization_agreement_mm': {k: v for k,v in parity.items() if k != 'chirps_2016'},
                  'target_coordinates': {'lat': lat, 'lon': lon},
                  'provider_urls': ['https://cds.climate.copernicus.eu/datasets/seasonal-monthly-single-levels?tab=overview', 'https://www.chc.ucsb.edu/data/chirps']}
    write_json(provider / 'provenance.json', provenance)
    resources = [{'path': str(path.relative_to(provider)), 'sha256': digest(path), 'bytes': path.stat().st_size}
                 for path in sorted(provider.rglob('*')) if path.is_file()]
    write_json(provider / 'catalog.json', {'resources': resources})
    files = [{'file': str(path.relative_to(TARGET)), 'sha256': digest(path), 'bytes': path.stat().st_size,
              'visibility': 'provider' if path.is_relative_to(provider) else 'controller'}
             for path in sorted(TARGET.rglob('*')) if path.is_file()]
    write_json(manifest_path, {'schema_version': 1, 'source_snapshot': 'var/private/templates/mam-forecast-synthesis',
                              'source_weather_is_synthetic': False, 'files': files,
                              'lineage': provenance, 'normalization_independent_max_gap_mm': parity,
                              'expert_lock_sha256': digest(TARGET / 'controller/expert-lock.json')})
    print(json.dumps({'frozen': True, 'files': len(files), 'selection': selection['selected'], 'parity_mm': parity}, indent=2))


if __name__ == '__main__':
    main()
