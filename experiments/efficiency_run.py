"""Run exactly one predeclared efficiency cell; never silently retry."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main(system, precision=False):
    plan_path = ROOT / ('experiments/efficiency_precision_plan_2026-10-08.json' if precision else 'experiments/efficiency_plan_2026-10-08.json')
    plan = json.loads(plan_path.read_text())
    if precision:
        assert plan['status'] == 'declared_ready', 'Precision phase is not validated and declared'
        initial = json.loads((ROOT / 'experiments/efficiency_plan_2026-10-08.json').read_text())
        assigned = set(initial['systems']) | set(plan['systems'])
        attempts = [p for p in (ROOT / 'var/template-runs').glob('*mam-multimodel-outlook*')
                    if json.loads((p / 'run.json').read_text())['system'] in assigned]
        assert len(attempts) < 4, 'Four-attempt efficiency cap exhausted'
    config = plan['systems'][system]
    for relative, expected in config['files'].items():
        assert digest(ROOT / 'systems' / system / relative) == expected, relative
    if config['replication'] == 2:
        gate = json.loads((ROOT / 'experiments/efficiency_replication_gate_2026-10-08.json').read_text())
        assert gate['eligible'] and gate['plan_sha256'] == digest(plan_path)
    template = Template(plan['template'])
    if precision:
        assert template.spec['spec_version'] == plan['required_spec_version']
    certificate = json.loads((template.folder / 'certification.json').read_text())
    proof = json.loads((ROOT / plan.get('docker_proof', 'var/review/mam-suite-20261008/final16-docker-correct-summary.json')).read_text())
    if precision:
        assert digest(ROOT / plan['docker_proof']) == plan['validated_gates']['docker_proof_sha256']
    assert certificate['fingerprint'] == proof['fingerprint'] == template.fingerprint() == plan['fingerprint']
    assert certificate['automatic_tests_passed'] and proof['outcome'] == 'pass'
    assert certificate['tests']['1_reference_implementations_agree']['combinations'] == 16
    binary = Path.home() / '.codex/packages/standalone/releases/0.160.0-aarch64-apple-darwin/bin/codex'
    assert digest(binary) == '112fae7a5a1223e673c8a1791d32338f37df8b527ff1159bb8adac6c4dbf1b4b'
    version = subprocess.check_output([str(binary), '--version'], text=True).strip()
    assert version == 'codex-cli 0.160.0'
    folder = ROOT / ('var/review/mam-efficiency-precision-20261008' if precision else 'var/review/mam-efficiency-20261008') / system
    folder.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-m', 'assessment', 'run', plan['template'], plan['instance'], '--system', system, '--no-judge']
    record = {'system': system, 'assigned_arm': config['arm'], 'replication': config['replication'],
              'fingerprint': template.fingerprint(), 'plan_sha256': digest(plan_path),
              'system_sha256': digest(ROOT / 'systems' / system / 'system.yaml'),
              'started_at': datetime.now(timezone.utc).isoformat(), 'command': command,
              'status': 'running', 'agent_retries': 0, 'direct_paid_api_usd': 0,
              'codex_binary': str(binary), 'codex_version': version, 'codex_binary_sha256': digest(binary)}
    path = folder / 'invocation.json'
    path.write_text(json.dumps(record, indent=2) + '\n')
    started = time.monotonic()
    with (folder / 'stdout.json').open('w') as stdout, (folder / 'stderr.log').open('w') as stderr:
        result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, env={**os.environ, 'CODEX_BINARY': str(binary)})
    record.update(status='finished', exit_code=result.returncode, finished_at=datetime.now(timezone.utc).isoformat(), cli_wall_seconds=time.monotonic()-started)
    if result.returncode == 0:
        record['result'] = json.loads((folder / 'stdout.json').read_text())
    path.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    return result.returncode

if __name__ == '__main__':
    sys.exit(main(sys.argv[1], precision='--precision' in sys.argv[2:]))
