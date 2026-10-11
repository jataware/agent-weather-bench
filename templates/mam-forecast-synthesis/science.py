"""Forecast methods are controls/comparators, never requirements on an agent.

Expert selection consumes training observations only. Probabilities follow the
Wilks OLS/Gaussian predictive variance; a train-only chronological development
set selects a centre/equal-centre combination and shrinkage to climatology.
"""
from math import fsum, erf, sqrt
from pathlib import Path
import json
import numpy as np
import xarray as xr
from scipy.special import ndtr

MODELS = ['ecmwf', 'cmcc', 'ukmo', 'meteofrance']
ALPHAS = [0., .25, .5, .75, 1.]


def load(provider):
    provider = Path(provider)
    models = {}
    for name in MODELS:
        with xr.open_dataset(provider / 'models' / (name + '.nc'), engine='h5netcdf') as ds:
            field = ds.precip.load().transpose('year', 'member', 'lat', 'lon')
        models[name] = field
    with xr.open_dataset(provider / 'observations/training.nc', engine='h5netcdf') as ds:
        observations = ds.precip.load().transpose('year', 'lat', 'lon')
    return models, observations


def cuts(y):
    return np.quantile(y, [1/3, 2/3], axis=0, method='linear')


def category(y, thresholds):
    return np.where(y < thresholds[0], 0, np.where(y > thresholds[1], 2, 1))


def rps_yearwise(p, labels):
    truth = np.stack([labels == i for i in range(3)], axis=1)
    score = np.sum((np.cumsum(p, axis=1) - np.cumsum(truth, axis=1)) ** 2, axis=1)
    return score.mean(axis=(1, 2))


def calibrate(x, y, xf, thresholds):
    """x,y training(year,lat,lon); xf forecasts(year,lat,lon)."""
    n = len(y)
    xb, yb = x.mean(axis=0), y.mean(axis=0)
    dx, dy = x-xb, y-yb
    sxx = np.sum(dx*dx, axis=0)
    slope = np.divide(np.sum(dx*dy, axis=0), sxx, out=np.zeros_like(xb), where=sxx > 1e-12)
    variance = np.sum((y-yb-slope*dx)**2, axis=0) / (n-2)
    mu = yb+slope*(xf-xb)
    inflation = 1 + 1/n + np.divide((xf-xb)**2, sxx, out=np.zeros_like(xf), where=sxx > 1e-12)
    sd = np.sqrt(np.maximum(variance*inflation, 1e-12))
    below = ndtr((thresholds[0]-mu)/sd)
    above = ndtr((mu-thresholds[1])/sd)
    return np.stack([below, 1-below-above, above], axis=1)


def calibrated(models, observations, training_years, forecast_years):
    y = np.asarray(observations.sel(year=training_years), dtype='float64')
    thresholds = cuts(y)
    return {name: calibrate(np.asarray(field.sel(year=training_years).mean('member')),
                            y, np.asarray(field.sel(year=forecast_years).mean('member')), thresholds)
            for name, field in models.items()}


def select_expert(models, observations):
    """All candidates/selection years fixed in expert-design.json, no test access."""
    years = list(map(int, observations.year.values))
    candidates = [(name, alpha) for name in ['equal_models'] + MODELS for alpha in ALPHAS]
    losses = {candidate: [] for candidate in candidates}
    for year in range(2000, 2005):
        train = [y for y in years if y < year]
        y = np.asarray(observations.sel(year=train))
        label = category(np.asarray(observations.sel(year=[year])), cuts(y))
        predictions = calibrated(models, observations, train, [year])
        predictions['equal_models'] = np.mean(list(predictions.values()), axis=0)
        for name, alpha in candidates:
            losses[name, alpha].append(float(rps_yearwise(alpha*predictions[name]+(1-alpha)/3, label)[0]))
    rows = [{'combination': name, 'alpha': alpha, 'development_year_rps': losses[name, alpha],
             'mean_development_rps': fsum(losses[name, alpha])/5} for name, alpha in candidates]
    # Stable ties: equal_models first, then centre declaration order, smaller alpha.
    winner = min(enumerate(rows), key=lambda pair: (pair[1]['mean_development_rps'], pair[0]))[1]
    return {'selection_years': list(range(2000, 2005)), 'training_years': years,
            'candidate_count': len(rows), 'selected': winner, 'candidates': rows,
            'uses_verifying_observations': False}


def forecast(models, observations, params, which='expert', selection=None):
    years = params['forecast_years']
    training = params['training_years']
    shape = (len(years), 3, len(params['target_latitude']), len(params['target_longitude']))
    if which == 'climatology':
        probabilities = np.full(shape, 1/3)
    elif which == 'raw_models':
        thresholds = cuts(np.asarray(observations.sel(year=training)))
        rows = []
        for name in MODELS:
            members = np.asarray(models[name].sel(year=years))
            labels = category(members, thresholds)
            rows.append(np.stack([(labels == i).mean(axis=1) for i in range(3)], axis=1))
        probabilities = np.mean(rows, axis=0)
    else:
        selection = selection or select_expert(models, observations)
        predictions = calibrated(models, observations, training, years)
        predictions['equal_models'] = np.mean(list(predictions.values()), axis=0)
        selected = selection['selected']
        probabilities = selected['alpha']*predictions[selected['combination']] + (1-selected['alpha'])/3
    return xr.Dataset({'forecast_probability': (('forecast_year', 'tercile', 'lat', 'lon'), probabilities)},
                      coords={'forecast_year': years, 'tercile': [0, 1, 2],
                              'lat': params['target_latitude'], 'lon': params['target_longitude']})


def scalar_yearwise(probabilities, training, verifying):
    """Independent scalar quantiles, categories and ordered-score accumulation."""
    def quantile(values, q):
        ordered = sorted(map(float, values)); index = (len(ordered)-1)*q
        low = int(index); high = min(low+1, len(ordered)-1)
        return ordered[low] + (index-low)*(ordered[high]-ordered[low])
    output = []
    for year in range(len(verifying)):
        errors = []
        for j in range(verifying.shape[1]):
            for k in range(verifying.shape[2]):
                low, high = (quantile(training[:, j, k], q) for q in (1/3, 2/3))
                truth = 0 if verifying[year, j, k] < low else 2 if verifying[year, j, k] > high else 1
                cumulative = 0.; terms = []
                for c in range(3):
                    cumulative += float(probabilities[year, c, j, k])
                    terms.append((cumulative - (1. if c >= truth else 0.))**2)
                errors.append(fsum(terms))
        output.append(fsum(errors)/len(errors))
    return np.asarray(output)
