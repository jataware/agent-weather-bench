"""Task-owned validity, blind verification, and frozen baseline hooks.

There is deliberately no unique valid answer and no response-to-input rule:
constant climatology is valid, and skill is evaluated outside the validity gate.
"""
import hashlib
import importlib.util
import json
from functools import lru_cache
from math import fsum
from pathlib import Path
import shutil
import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent


@lru_cache(None)
def _module(name):
    spec = importlib.util.spec_from_file_location('synthesis_' + name, HERE / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def prepare(private, source_dir=None):
    from assessment.sources import restore
    return restore(HERE, private, source_dir or private)


def candidate_instances():
    return [{'id': 'kenya-interior--fixed-training-12-blind-seasons',
             'training_years': list(range(1993, 2005)), 'forecast_years': list(range(2005, 2017)),
             'target_latitude': [-2.5, -1.5, -.5, .5, 1.5, 2.5], 'target_longitude': [36.5, 37.5, 38.5]}]


def brief_fields(params):
    return {}


def stage_inputs(private, params, destination):
    private, destination = Path(private), Path(destination)
    prepare(private); destination.mkdir(parents=True)
    shutil.copytree(private / 'provider', destination / 'provider')
    public = destination / 'public'; public.mkdir()
    text = json.dumps(params, indent=2) + '\n'
    (destination / 'instance.json').write_text(text); (public / 'instance.json').write_text(text)
    (public / 'acquisition.json').write_text(json.dumps({'base_url': 'http://weather-source:8000',
        'catalog_path': 'catalog.json', 'transport': 'immutable training-only HTTP snapshot'}) + '\n')
    _module('acquisition').provider_manifest(destination / 'provider')


def expected_coordinates(inputs, params):
    return {'forecast_year': np.asarray(params['forecast_years']), 'tercile': np.arange(3),
            'lat': np.asarray(params['target_latitude']), 'lon': np.asarray(params['target_longitude'])}


def probabilities_valid(results, params, inputs=None):
    p = results['forecast_probability']; epsilon = 1e-6
    valid = (np.isfinite(p).all() and np.all(p >= -epsilon) and np.all(p <= 1+epsilon)
             and np.max(np.abs(np.sum(p, axis=1)-1)) <= epsilon)
    return bool(valid), 'Finite ordered-category probabilities in [0,1], summing to one within 1e-6.'


INVARIANTS = {'probabilities_valid': probabilities_valid}


def perturb_inputs(inputs, seed, kind='future_forecasts'):
    if kind != 'future_forecasts':
        raise ValueError(kind)
    provider = Path(inputs) / 'provider'
    params = json.loads((Path(inputs) / 'instance.json').read_text())
    rng = np.random.default_rng(seed)
    for name in _module('science').MODELS:
        path = provider / 'models' / (name + '.nc')
        with xr.open_dataset(path, engine='h5netcdf') as ds:
            ds = ds.load()
        attrs = dict(ds.precip.attrs)
        factors = xr.DataArray(rng.uniform(1.6, 2.4, ds.sizes['year']), dims='year', coords={'year': ds.year})
        ds['precip'] = ds.precip * xr.where(ds.year >= 2011, factors, 1.)
        ds.precip.attrs = attrs
        temporary = path.with_suffix('.tmp.nc'); ds.to_netcdf(temporary, engine='h5netcdf'); temporary.replace(path)
    catalog = json.loads((provider / 'catalog.json').read_text())
    for row in catalog['resources']:
        path = provider / row['path']
        row.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)
    (provider / 'catalog.json').write_text(json.dumps(catalog, indent=2) + '\n')


def _earlier_probabilities(results, inputs, params):
    return {'forecast_probability': results['forecast_probability'][np.asarray(results['forecast_year']) < 2011]}


INVARIANCE_PROBES = {'no_future_forecasts': {'perturb': 'future_forecasts', 'unchanged': _earlier_probabilities,
    'passes': 'Earlier fixed-calibration outlooks do not depend on later forecast-year predictors.',
    'fails': 'Earlier outlook probabilities depend on later forecast-year predictors.'}}


def expected_claims(results, params):
    return {}


def baseline_results(private, params, which):
    private = Path(private)
    methods = _module('science')
    models, observations = methods.load(private / 'provider')
    lock = json.loads((private / 'controller/expert-lock.json').read_text())
    ds = methods.forecast(models, observations, params, which, selection=lock)
    return {name: ds[name].values for name in ds.variables}


def _targets(private, params):
    private = Path(private)
    with xr.open_dataset(private / 'provider/observations/training.nc', engine='h5netcdf') as ds:
        train = np.asarray(ds.precip.sel(year=params['training_years']).transpose('year', 'lat', 'lon'))
    with xr.open_dataset(private / 'controller/heldout-observations.nc', engine='h5netcdf') as ds:
        truth = np.asarray(ds.precip.sel(year=params['forecast_years']).transpose('year', 'lat', 'lon'))
    return train, truth


def _summary(annual, climo, expert, params):
    mean, climomean, expertmean = map(lambda a: fsum(map(float, a))/len(a), (annual, climo, expert))
    return {'split': 'blind_years', 'rps': mean, 'climatology_rps': climomean, 'expert_rps': expertmean,
            'rpss': 1-mean/climomean, 'performance_target_rps': min(climomean, expertmean)+1e-6,
            'performance_target_met': bool(mean <= min(climomean, expertmean)+1e-6),
            'years': params['forecast_years'], 'annual_rps': list(map(float, annual)),
            'annual_climatology_rps': list(map(float, climo)), 'annual_expert_rps': list(map(float, expert)),
            'cells': len(params['target_latitude'])*len(params['target_longitude']), 'ranking_enabled': False,
            'validity_separate_from_performance': True}


def score(results, params, private, split):
    if split != 'blind_years':
        raise ValueError(split)
    methods = _module('science'); train, truth = _targets(private, params)
    labels = methods.category(truth, methods.cuts(train))
    p = results['forecast_probability']
    annual = methods.rps_yearwise(p, labels)
    climo = methods.rps_yearwise(np.full_like(p, 1/3, dtype='float64'), labels)
    expert = methods.rps_yearwise(baseline_results(private, params, 'expert')['forecast_probability'], labels)
    return _summary(annual, climo, expert, params)


def independent_score(results, params, private, split):
    if split != 'blind_years':
        raise ValueError(split)
    methods = _module('science'); train, truth = _targets(private, params)
    p = results['forecast_probability']
    annual = methods.scalar_yearwise(p, train, truth)
    climo = methods.scalar_yearwise(np.full_like(p, 1/3, dtype='float64'), train, truth)
    expert = methods.scalar_yearwise(baseline_results(private, params, 'expert')['forecast_probability'], train, truth)
    return _summary(annual, climo, expert, params)


def regression_checks(scratch):
    methods = _module('science')
    labels = np.asarray([[[0]], [[1]], [[2]]])
    perfect = np.eye(3).reshape(3,3,1,1)
    opposite = perfect[::-1]
    uniform = np.full((3,3,1,1), 1/3)
    a, b, c = (methods.rps_yearwise(p, labels) for p in (perfect, opposite, uniform))
    rows = [{'name': 'ordered_score_known_cases', 'passed': bool(np.allclose(a,[0,0,0]) and np.allclose(b,[2,0,2]) and np.allclose(c,[5/9,2/9,5/9]))}]
    private = HERE.parent.parent / 'var/private/templates/mam-forecast-synthesis'
    params = candidate_instances()[0]
    models, observations = methods.load(private / 'provider')
    lock = json.loads((private / 'controller/expert-lock.json').read_text())
    repeated = methods.select_expert(models, observations)
    rows.append({'name': 'train_only_expert_lock_reproducible', 'passed': repeated['selected'] == lock['selected']})
    # Scalar Gaussian calculation independently checks the frozen selected forecast.
    native = _module('native_independent')
    selected = lock['selected']; train = params['training_years']; new = params['forecast_years']
    y = np.asarray(observations.sel(year=train)); thresholds = methods.cuts(y)
    names = methods.MODELS if selected['combination'] == 'equal_models' else [selected['combination']]
    p = np.zeros((len(new),3,len(params['target_latitude']),len(params['target_longitude'])))
    for name in names:
        x = np.asarray(models[name].sel(year=train).mean('member')); xf = np.asarray(models[name].sel(year=new).mean('member'))
        for t,j,k in np.ndindex(xf.shape):
            p[t,:,j,k] += np.asarray(native.predict(x[:,j,k], y[:,j,k], xf[t,j,k], thresholds[:,j,k])) / len(names)
    p = selected['alpha']*p+(1-selected['alpha'])/3
    primary = baseline_results(private, params, 'expert')['forecast_probability']
    gap = float(np.max(np.abs(p-primary)))
    rows.append({'name': 'independent_scalar_expert_forecast', 'passed': gap < 1e-10, 'maximum_probability_gap': gap})
    return rows


def sandbox_factory(*args, **kwargs):
    return _module('acquisition').sandbox_factory(*args, **kwargs)


def executor_factory(executor):
    return _module('acquisition').executor_factory(executor)


def acquisition_evidence(scratch, destination=None):
    return _module('acquisition').acquisition_evidence(scratch, destination)
