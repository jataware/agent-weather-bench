"""Read-only localization of two historical errors against trusted references.

Run in one fresh, single-threaded process. Imports controller reference modules
only: it never imports or executes either model's workflow.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'experiments/historical-science-slices-2026-10-08.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_reference(name):
    path = ROOT / 'archive/evaluator-v1-2026-10/weatherbench/task_tools' / name / 'reference.py'
    spec = importlib.util.spec_from_file_location('trusted_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, {'path': str(path.relative_to(ROOT)), 'sha256': digest(path)}


def differences(actual, expected):
    actual, expected = xr.align(actual, expected, join='exact')
    actual = actual.transpose(*expected.dims).values
    expected = expected.values
    finite = np.isfinite(actual) & np.isfinite(expected)
    error = actual[finite] - expected[finite]
    return {'finite_pairs': int(finite.sum()),
            'nonfinite_mask_agrees': bool(np.array_equal(np.isfinite(actual), np.isfinite(expected))),
            'max_absolute_error': float(np.max(np.abs(error))) if error.size else None,
            'rmse_of_difference': float(np.sqrt(np.mean(error**2))) if error.size else None,
            'values_differing_by_more_than_1e_7': int((np.abs(error) > 1e-7).sum())}


def main():
    if DESTINATION.exists():
        raise ValueError('Preserve previous evidence; do not overwrite')
    audit_path = ROOT / 'experiments/original-portfolio-failure-audit-2026-10-08.json'
    audit = json.loads(audit_path.read_text())
    originals = {path: value for row in audit['runs'].values() for path, value in row['sources'].items()}
    for path, value in originals.items():
        if digest(ROOT / path) != value:
            raise ValueError('Original changed: ' + path)

    monthly_run = ROOT / 'var/runs/20261005T183342-monthly-cycle-calibration-codex-luna-e7f6e0'
    monthly, monthly_source = load_reference('monthly_cycle')
    _, forecast, _ = monthly.build(monthly_run / 'inputs')
    with xr.open_dataset(monthly_run / 'frozen/forecast.nc') as ds:
        submitted = ds.load()
    monthly_rows = {system: differences(submitted.prediction.sel(system=system), forecast.prediction.sel(system=system))
                    for system in monthly.SYSTEMS}

    station_run = ROOT / 'var/runs/20261005T181603-station-verification-codex-luna-ff16df'
    station, station_source = load_reference('station_verification')
    scores = station.build(station_run / 'inputs')
    with xr.open_dataset(station_run / 'frozen/scores.nc') as ds:
        submitted = ds.load()
    station_rows = {variant: differences(submitted.diagnostic_rmse.sel(variant=variant), scores.diagnostic_rmse.sel(variant=variant))
                    for variant in station.VARIANTS}

    for path, value in originals.items():
        if digest(ROOT / path) != value:
            raise ValueError('Original changed during read-only audit: ' + path)
    result = {'schema_version': 1, 'source_audit_sha256': digest(audit_path),
              'scope': 'Fresh trusted-reference calculations and read-only original arrays; no submission code executed, no model requests.',
              'references': {'monthly': monthly_source, 'station': station_source},
              'original_artifacts_reverified': len(originals),
              'monthly_production_by_system': monthly_rows,
              'station_diagnostic_by_variant': station_rows,
              'interpretation': 'Differences localize the faults; passing other slices is preserved. This is not a repeated agent attempt or a persistent capability boundary.'}
    DESTINATION.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
