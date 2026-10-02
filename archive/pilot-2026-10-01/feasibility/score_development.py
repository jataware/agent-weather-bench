"""Verify a seasonal calibration on development years only, never pilot test years."""
import argparse
import json
from pathlib import Path

import numpy as np
import xarray as xr
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
YEARS = np.arange(1993, 2009)


def probabilities(samples, thresholds):
    below = (samples < thresholds[0]).mean(axis=0)
    above = (samples > thresholds[1]).mean(axis=0)
    return np.stack([below, 1 - below - above, above])


def rps(probability, category):
    # Unnormalized RPS: sum over the two nontrivial cumulative categories.
    outcome = np.eye(3)[category].transpose(2, 0, 1)
    return ((probability.cumsum(axis=0)[:2] - outcome.cumsum(axis=0)[:2]) ** 2).sum(axis=0)


def independent_ereg(x, y, xf, thresholds):
    # Independent least-squares solution, not the library's closed-form engine.
    mu = np.empty(x.shape[1:])
    sigma = np.empty_like(mu)
    for ij in np.ndindex(mu.shape):
        a = np.column_stack([np.ones(len(x)), x[(slice(None),) + ij]])
        target = y[(slice(None),) + ij]
        beta = np.linalg.lstsq(a, target, rcond=None)[0]
        residual_variance = np.sum((target - a @ beta) ** 2) / (len(x) - 2)
        query = np.array([1., xf[ij]])
        mu[ij] = max(float(query @ beta), 0.)
        sigma[ij] = np.sqrt(max(residual_variance * (1 + query @ np.linalg.inv(a.T @ a) @ query), 1e-12))
    low = norm.cdf(thresholds[0], loc=mu, scale=sigma)
    high = 1 - norm.cdf(thresholds[1], loc=mu, scale=sigma)
    return np.stack([low, 1 - low - high, high]), mu


def prepare():
    forecast = xr.load_dataset(ROOT / 'data/forecast-development.nc')['precip']
    observations = xr.load_dataset(ROOT / 'data/observations-development.nc')['precip']
    assert forecast.attrs['units'] in ['mm/day', 'mm day-1'], forecast.attrs
    assert observations.attrs['units'] in ['mm/month', 'mm month-1'], observations.attrs
    assert set(forecast.lead_time.values.tolist()) == {2, 3, 4}, forecast.lead_time
    np.testing.assert_array_equal(forecast.init_time.dt.year.values, YEARS)
    np.testing.assert_array_equal(np.unique(observations.time.dt.year), YEARS)
    assert set(observations.time.dt.month.values.tolist()) == {10, 11, 12}
    assert observations.sizes['time'] == len(YEARS) * 3
    assert np.isfinite(forecast.values).all()
    assert float(forecast.min()) >= 0
    # Never use an unweighted mean of the three monthly rainfall rates.
    days = xr.DataArray([31., 30., 31.], dims='lead_time', coords={'lead_time': [2, 3, 4]})
    hc = (forecast * days).sum('lead_time', skipna=False)
    hc = hc.assign_coords(init_time=YEARS).rename(init_time='year').transpose('year', 'member', 'lat', 'lon')
    # Area-average native CHIRPS cells within each full 1-degree forecast cell.
    coarse = np.empty((observations.sizes['time'], hc.sizes['lat'], hc.sizes['lon']))
    coverage = np.empty_like(coarse)
    for i, lat in enumerate(hc.lat.values):
        for j, lon in enumerate(hc.lon.values):
            sub = observations.where((observations.lat >= lat-.5) & (observations.lat < lat+.5) &
                                     (observations.lon >= lon-.5) & (observations.lon < lon+.5), drop=True)
            assert sub.sizes['lat'] == 20 and sub.sizes['lon'] == 20, sub.sizes
            weights = np.cos(np.deg2rad(sub.lat)).broadcast_like(sub)
            valid = sub.notnull()
            coverage[:, i, j] = ((weights * valid).sum(['lat', 'lon']) / weights.sum(['lat', 'lon'])).values
            coarse[:, i, j] = sub.weighted(np.cos(np.deg2rad(sub.lat))).mean(['lat', 'lon']).values
    assert coverage.min() >= .9, f'Observation coverage too low: {coverage.min()}'
    obs = xr.DataArray(coarse, dims=['time', 'lat', 'lon'],
                       coords={'time': observations.time, 'lat': hc.lat, 'lon': hc.lon})
    obs = obs.groupby('time.year').sum('time', skipna=False).transpose('year', 'lat', 'lon')
    assert np.isfinite(obs.values).all() and float(obs.min()) >= 0
    hc.attrs = {'units': 'mm', 'period': 'OND'}
    obs.attrs = dict(hc.attrs)
    xr.Dataset({'forecast': hc, 'observed': obs}).to_netcdf(ROOT / 'data/seasonal-development.nc')
    return hc, obs, float(coverage.min())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=['accord', 'numpy'], default='accord',
                        help='numpy verifies numerical feasibility without either project installed')
    args = parser.parse_args()
    if args.engine == 'accord':
        import africas2s
    # Hand-computable metric checks, independent of any library metric code.
    assert rps(np.array([1., 0., 0.])[:, None, None], np.zeros((1, 1), dtype=int)).item() == 0
    np.testing.assert_allclose(rps(np.full((3, 1, 1), 1/3), np.zeros((1, 1), dtype=int)), 5/9)
    hc, obs, coverage = prepare()
    names = ['raw', 'model_climate', 'climatology', 'calibrated']
    scores = {n: [] for n in names}
    probability_fields = {n: [] for n in names}
    observed_categories = []
    errors = {'raw': [], 'calibrated': []}
    checks = []
    weights = np.cos(np.deg2rad(hc.lat.values))[:, None] * np.ones((1, hc.sizes['lon']))
    weights /= weights.sum()
    for year in YEARS:
        train = YEARS[YEARS != year]
        h, y = hc.sel(year=train), obs.sel(year=train)
        f, target = hc.sel(year=year), obs.sel(year=year).values
        thresholds = np.quantile(y.values, [1/3, 2/3], axis=0, method='linear')
        category = np.where(target < thresholds[0], 0, np.where(target > thresholds[1], 2, 1))
        observed_categories.append(category)
        pm = probabilities(f.values, np.quantile(h.values.reshape(-1, *target.shape), [1/3, 2/3], axis=0))
        ref, mu = independent_ereg(h.mean('member').values, y.values, f.mean('member').values, thresholds)
        if args.engine == 'accord':
            calibrated = africas2s.calibrate((h, f.expand_dims(year=[year])), y, method='ereg',
                                           forecast_year=int(year), clip_negative=True).transpose('tercile', 'lat', 'lon').values
            deterministic = africas2s.calibrate((h, f.expand_dims(year=[year])), y, method='ereg',
                                               forecast_year=int(year), clip_negative=True,
                                               output_type='deterministic').transpose('lat', 'lon').values
            np.testing.assert_allclose(deterministic, mu, atol=1e-8, rtol=1e-8)
            checks.append(float(np.max(np.abs(calibrated - ref))))
            np.testing.assert_allclose(calibrated, ref, atol=1e-8, rtol=1e-8)
        else:
            calibrated = ref
        predictions = dict(raw=probabilities(f.values, thresholds), model_climate=pm,
                           climatology=probabilities(y.values, thresholds), calibrated=calibrated)
        for name, p in predictions.items():
            assert np.isfinite(p).all() and p.min() >= -1e-12 and p.max() <= 1+1e-12
            np.testing.assert_allclose(p.sum(axis=0), 1, atol=1e-10)
            scores[name].append(float((rps(p, category) * weights).sum()))
            probability_fields[name].append(p)
        errors['raw'].append(float((((f.mean('member').values-target)**2)*weights).sum()))
        errors['calibrated'].append(float((((mu-target)**2)*weights).sum()))
    average = {n: float(np.mean(v)) for n, v in scores.items()}
    rng = np.random.default_rng(20261001)
    draws = rng.integers(0, len(YEARS), (5000, len(YEARS)))
    intervals = {}
    for baseline in ['raw', 'model_climate', 'climatology']:
        ratio = 1 - np.array(scores['calibrated'])[draws].mean(axis=1) / np.array(scores[baseline])[draws].mean(axis=1)
        intervals[baseline] = np.quantile(ratio, [.025, .975]).tolist()
    reliability = {}
    event = (np.array(observed_categories) == 2).astype(float)
    mass = np.broadcast_to(weights, event.shape)
    for name in names:
        prob = np.array(probability_fields[name])[:, 2]
        bins = np.minimum((prob*5).astype(int), 4)
        rows = []
        for b in range(5):
            mask = bins == b
            if not mask.any():
                continue
            w = mass[mask]
            rows.append({'bin': b, 'forecast_probability': float(np.average(prob[mask], weights=w)),
                         'observed_frequency': float(np.average(event[mask], weights=w)),
                         'cell_year_count': int(mask.sum()), 'distinct_years': int(mask.any(axis=(1, 2)).sum()),
                         'weight': float(w.sum()/mass.sum())})
        reliability[name] = {'bins': rows, 'weighted_absolute_gap': sum(r['weight'] * abs(r['forecast_probability']-r['observed_frequency']) for r in rows)}
    result = {
        'status': 'development_feasibility_only', 'engine': args.engine,
        'agent_runs': 0, 'heldout_evaluation_accessed': False,
        'development_years': YEARS.tolist(), 'validation': 'leave_one_year_out_on_development_years',
        'grid_cells': int(weights.size), 'ensemble_members': int(hc.sizes['member']),
        'minimum_observation_coverage': coverage, 'rps_definition': 'sum_of_two_cumulative_category_squared_errors',
        'mean_RPS': average, 'calibrated_skill_vs': {n: 1-average['calibrated']/average[n] for n in names if n != 'calibrated'},
        'RMSE_mm': {n: float(np.sqrt(np.mean(v))) for n, v in errors.items()},
        'paired_year_resampling_95pct_intervals': intervals,
        'uncertainty_note': 'Exploratory: 16 development years; folds share training data. Not a confirmatory significance test.',
        'max_probability_difference_from_independent_OLS': max(checks) if checks else None,
        'reliability': reliability, 'per_year_RPS': {n: dict(zip(map(str, YEARS), v)) for n, v in scores.items()},
    }
    # Verify a reusable fitted artifact without opening any pilot evaluation year.
    # The replay case is a development forecast; it is not scored as a new test.
    if args.engine == 'accord':
        from africas2s.methods.ensemble_regression import EnsembleRegressionMethod
        fitted = EnsembleRegressionMethod(clip_negative=True).fit(hc, obs)
        model_path = ROOT/'data/development-fitted-model.pkl'
        fitted.save(model_path)
        restored = EnsembleRegressionMethod().load(model_path)
        replay = hc.sel(year=[2008])
        before = fitted.predict_tercile(replay, obs)
        after = restored.predict_tercile(replay, obs)
        xr.testing.assert_identical(before, after)
        result['fitted_model_save_reload'] = {'identical_predictions': True, 'bytes': model_path.stat().st_size,
                                           'replay_year': 2008, 'counts_as_followup_attempt': False}
    (ROOT/'results/development-scores.json').write_text(json.dumps(result, indent=2)+'\n')
    xr.Dataset({n: (['year', 'tercile', 'lat', 'lon'], np.array(v)) for n, v in probability_fields.items()},
               coords={'year': YEARS, 'tercile': [0, 1, 2], 'lat': hc.lat, 'lon': hc.lon}).to_netcdf(ROOT/'data/development-probabilities.nc')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout='constrained')
    labels = ['Raw', 'Model-climate\nterciles', 'Climatology', 'Calibrated']
    axes[0].bar(labels, [average[n] for n in names], color=['#9ca3af', '#64748b', '#d6b45b', '#168c86'])
    axes[0].set(ylabel='Ranked probability score (lower is better)', title='Development years only: leave-one-year-out')
    axes[1].plot([0, 1], [0, 1], '--', color='gray', label='Perfect reliability')
    for name in ['raw', 'model_climate', 'calibrated']:
        rows = reliability[name]['bins']
        axes[1].plot([r['forecast_probability'] for r in rows], [r['observed_frequency'] for r in rows], 'o-', label=name.replace('_', ' '))
    axes[1].set(xlabel='Forecast probability', ylabel='Observed frequency', title='Above-normal rainfall: pooled diagnostic', xlim=(0, 1), ylim=(0, 1))
    axes[1].legend(fontsize=8)
    fig.suptitle('Kenyan study box · September-issued OND rainfall · 1993–2008\nExploratory reference computation; no agent benchmark or untouched-test result', fontsize=11)
    fig.savefig(ROOT/'results/development.png', dpi=160)
    print(json.dumps({k:v for k,v in result.items() if k not in ['reliability','per_year_RPS']}, indent=2))


if __name__ == '__main__':
    main()
