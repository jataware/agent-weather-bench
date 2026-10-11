"""Independent frozen-output verification, in one fresh scientific process.

No model calls or submitted-code execution. The separate FFT/scalar-covariance
reference checks each array and each production system without replacing the
original assessment.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.compare import EnvelopeError, align, compare, read_results
from assessment.spec import Template
from assessment.storage import digest, inventory, read, write


def verify(plan_path, output_path):
    import numpy as np
    plan_path, output_path = Path(plan_path), Path(output_path)
    if output_path.exists():
        raise ValueError('Never overwrite a previous numeric audit')
    plan = read(plan_path)
    template = Template(plan['template'])
    if template.fingerprint() != plan['fingerprint']:
        raise ValueError('Task/controller changed after launch')
    independent_path = template.folder / 'reference_independent.py'
    loader = importlib.util.spec_from_file_location('monthly_independent_frozen_verification', independent_path)
    independent = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(independent)
    rows = []
    for system in plan['systems']:
        invocation = read(ROOT / plan['review_directory'] / system / 'invocation.json')
        if invocation.get('exit_code') != 0:
            rows.append({'system': system, 'verification': 'not_available', 'invocation': invocation})
            continue
        folder = ROOT / invocation['result']['directory']
        metadata, assessment = read(folder / 'run.json'), read(folder / 'assessment.json')
        if metadata['fingerprint'] != plan['fingerprint'] or assessment['fingerprint'] != plan['fingerprint']:
            raise ValueError('Attempt uses another task/controller contract')
        manifests = {name: inventory(folder / name) for name in ('frozen', 'inputs', 'system')}
        for name, filename in [('frozen', 'artifacts.json'), ('inputs', 'input-manifest.json'), ('system', 'substrate-manifest.json')]:
            if manifests[name] != read(folder / filename):
                raise ValueError('Immutable attempt bundle changed: ' + name)
        row = {'system': system, 'run': metadata['id'], 'original_computed_outcome': assessment['computed_outcome'],
               'original_completion': assessment['outcome'], 'assessment_sha256': digest(folder / 'assessment.json'),
               'verification': 'not_available'}
        try:
            answer = read(folder / 'frozen/answer.json')
            actual, problems = read_results(template.spec['results'], folder / 'frozen', answer)
            frame = template.hooks.expected_coordinates(folder / 'inputs', metadata['instance'])
            actual = align(template.spec['results'], actual, frame)
            expected = independent.reference(folder / 'inputs')
            agrees, details = compare(template.spec['results'], actual, expected)
            row.update(verification='compared', numeric_reference_agrees=agrees, envelope_numeric_problems=problems,
                       fields=details, production_by_system={})
            for index, label in enumerate(('climatology', 'independent-month', 'constant-slope', 'nested-cyclic')):
                if 'forecast_mm' not in actual:
                    break
                values, target = actual['forecast_mm'][index], expected['forecast_mm'][index]
                finite = np.isfinite(values) & np.isfinite(target)
                error = values[finite] - target[finite]
                row['production_by_system'][label] = {
                    'finite_pairs': int(finite.sum()),
                    'nonfinite_mask_agrees': bool(np.array_equal(np.isfinite(values), np.isfinite(target))),
                    'max_absolute_error_mm': float(np.max(np.abs(error))) if error.size else None,
                    'rmse_of_difference_mm': float(np.sqrt(np.mean(error**2))) if error.size else None}
            row['selected_candidates'] = {name: actual[name].tolist() for name in ('selected_candidate', 'final_candidate') if name in actual}
            if 'msss' in actual:
                row['pooled_msss'] = actual['msss'].tolist()
        except EnvelopeError as error:
            row['numeric_envelope_error'] = str(error)
        for name in manifests:
            if inventory(folder / name) != manifests[name]:
                raise ValueError('Attempt changed during read-only verification')
        rows.append(row)
    result = {'schema_version': 1, 'verified_at': datetime.now(timezone.utc).isoformat(),
              'plan_sha256': digest(plan_path), 'fingerprint': plan['fingerprint'],
              'verifier_sha256': digest(Path(__file__)), 'independent_reference_sha256': digest(independent_path),
              'new_model_calls': 0, 'submitted_code_executed': False, 'rows': rows,
              'scope': 'Independent numeric comparison of frozen submissions only; replay and saved-state verdicts remain separate original instruments.'}
    write(output_path, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = verify(args.plan, args.output)
    print(json.dumps({'output': args.output, 'rows': [{key: row.get(key) for key in ('system', 'verification', 'numeric_reference_agrees')} for row in result['rows']]}, indent=2))
