"""Numerical equivalence checks on alternate spherical algebra and CCA bases.

These controller diagnostics do not change the template or substitute a grader.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.compare import compare
from assessment.spec import Template


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def geometry_checks():
    template = Template('rainfall-downscaling')
    science = module(template.folder / 'science.py', 'stress_geometry')
    lat = np.arange(40, dtype=float) * .05 + .525
    lon = np.arange(40, dtype=float) * .05 + 36.525
    expected, _ = science.geometry(lat, lon)
    # sin(a+b)-sin(a-b) = 2*cos(a)*sin(b). This independent expression
    # avoids subtracting two close sine values, using long-double intermediates.
    pi = np.arccos(np.longdouble(-1))
    strip = 2 * np.cos(lat.astype(np.longdouble) * pi / 180) * np.sin(np.longdouble('.025') * pi / 180)
    alternate = np.asarray(np.longdouble(6371000) ** 2 * strip[:, None] * (np.longdouble('.05') * pi / 180) * np.ones((1, len(lon))), dtype=float)
    spec = {name: template.spec['results'][name] for name in ('latitude', 'longitude', 'area_m2')}
    correct = {'latitude': lat, 'longitude': lon, 'area_m2': expected}
    gap = float(np.max(np.abs(alternate - expected)))
    assert compare(spec, {**correct, 'area_m2': alternate}, correct)[0]
    wrong = alternate * ((6371001. / 6371000.) ** 2)
    assert not compare(spec, {**correct, 'area_m2': wrong}, correct)[0]
    # A tied predictor must map to the mean of corresponding observed ranks.
    # The two interpolated answers and both clamped tails are written analytically.
    values = science.map_value(np.array([-1., 0., 1., 2., 3., 4., 5.]),
                               np.array([2., 0., 2., 4.]), np.array([400., 300., 100., 200.]))
    np.testing.assert_array_equal(values, [100., 100., 175., 250., 325., 400., 400.])
    return {'alternate': 'long-double spherical half-angle identity', 'max_area_difference_m2': gap,
            'area_bound_m2': spec['area_m2']['tolerance']['atol'], 'correct_algebra_accepted': True,
            'one_metre_radius_error_rejected': True, 'tied_rank_and_clamped_tail_analytic_cases_pass': True}


def cca_checks(inputs):
    template = Template('seasonal-cca-reproduction')
    science = module(template.folder / 'science.py', 'stress_cca')
    xd, yd = science.load(inputs)
    x, y = xd.sst.values[:len(yd.year)], yd.rainfall.values
    new = xd.sst.values[len(yd.year):]
    xlat, ylat = xd.predictor_lat.values, yd.target_lat.values
    px = np.arange(x.shape[1])[::-1]
    py = np.roll(np.arange(y.shape[1]), 3)
    restore = np.argsort(py)
    original_svd = np.linalg.svd

    def other_signs(*args, **kwargs):
        u, singular, vh = original_svd(*args, **kwargs)
        signs = np.where(np.arange(len(singular)) % 2 == 0, -1., 1.)
        return u * signs, singular, vh * signs[:, None]

    rows = []
    for n in (12, len(y)):
        for modes in science.CANDIDATES:
            probability, mean, _ = science.distribution(x[:n], y[:n], new, xlat, ylat, modes)
            with patch.object(np.linalg, 'svd', other_signs):
                pp, mu, _ = science.distribution(x[:n, px], y[:n, py], new[:, px], xlat[px], ylat[py], modes)
            pp, mu = pp[:, restore], mu[:, restore]
            mean_gap = float(np.max(np.abs(mean - mu)))
            probability_gap = float(np.max(np.abs(probability - pp)))
            assert mean_gap <= template.spec['results']['forecast_mean_mm']['tolerance']['atol']
            assert probability_gap <= template.spec['results']['forecast_probability']['tolerance']['atol']
            rows.append({'training_years': n, 'modes': list(modes), 'max_mean_difference_mm': mean_gap,
                         'max_probability_difference': probability_gap})
    return {'alternate': 'reverse predictor columns, rotate target columns, change legal EOF/canonical sign choices',
            'scope': 'fixed-candidate forecasts including leave-one-out uncertainty; all 14 candidates, 12 and 27 fit years',
            'independent_implementation': False, 'cases': rows, 'accepted': True}


def run(inputs, output):
    report = {'kind': 'controller_numerical_stress', 'model_calls': 0,
              'geometry': geometry_checks(), 'cca': cca_checks(inputs)}
    output.write_text(json.dumps(report, indent=2) + '\n')
    print('geometry alternate algebra and 1 m fault passed; 28 CCA basis/sign cases passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, default=ROOT / 'var/review/grader-stress-2026-10-08-v3/seasonal-cca-reproduction/inputs')
    parser.add_argument('--output', type=Path, default=ROOT / 'experiments/grader-numerical-stress-2026-10-08.json')
    args = parser.parse_args()
    run(args.inputs, args.output)
