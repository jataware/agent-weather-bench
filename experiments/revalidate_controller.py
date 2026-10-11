"""Refresh stale automatic controls once, with scientific I/O in fresh processes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template
from assessment.storage import digest


def worker(name):
    # The orchestration thread does no HDF5/NetCDF work.
    path = ROOT / 'var/review' / ('response-groups-certify-' + name + '.log')
    with path.open('w') as stream:
        result = subprocess.run([sys.executable, '-m', 'assessment', 'certify', name,
                                 '--full', '--local-trusted'], cwd=ROOT,
                                stdout=stream, stderr=subprocess.STDOUT, timeout=1200)
    return name, result.returncode, str(path.relative_to(ROOT))


if __name__ == '__main__':
    ledger = json.loads((ROOT / 'experiments/response-projection-revision-2026-10-08.json').read_text())
    names, rows = [], []
    for name in ledger['legacy_templates']:
        path = ROOT / 'templates' / name / 'certification.json'
        record = json.loads(path.read_text())
        if record['fingerprint'] == Template(name).fingerprint() and record['automatic_tests_passed']:
            rows.append({'template': name, 'already_current': True, 'passed': True,
                         'fingerprint': record['fingerprint']})
        else:
            names.append(name)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, name) for name in names]
        for future in as_completed(futures):
            name, code, log = future.result()
            path = ROOT / 'templates' / name / 'certification.json'
            record = json.loads(path.read_text())
            passed = code == 0 and record['automatic_tests_passed'] and record['fingerprint'] == Template(name).fingerprint()
            rows.append({'template': name, 'exit_code': code, 'passed': passed, 'log': log,
                         'fingerprint': record['fingerprint'], 'certification': str(path.relative_to(ROOT)),
                         'sha256': digest(path), 'tests': {k: v['passed'] for k, v in record['tests'].items()}})
            print(json.dumps({'template': name, 'passed': passed}), flush=True)
    report = {'schema_version': 1, 'revision': 'experiments/response-projection-revision-2026-10-08.json',
              'model_calls': 0, 'judge_calls': 0, 'scientific_workers': 'two fresh interpreter subprocesses; threads only orchestrate',
              'passed': all(row['passed'] for row in rows), 'rows': rows}
    (ROOT / 'experiments/response-groups-controls-2026-10-08.json').write_text(json.dumps(report, indent=2) + '\n')
    if not report['passed']:
        raise SystemExit(1)
