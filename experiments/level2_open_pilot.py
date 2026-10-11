"""Two-attempt Level 2 pilot; threads orchestrate isolated controller processes only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template
from assessment.storage import digest, inventory, read, write

PLAN = ROOT / 'experiments/level2-open-plan-2026-10-08.json'
REVIEW = ROOT / 'var/review/level2-open-20261008'


def validate(plan):
    assert plan['status'] == 'ready'
    assert plan['max_new_agent_attempts'] == len(plan['systems']) == 2
    task = Template(plan['template'])
    assert task.fingerprint() == plan['fingerprint']
    assert digest(ROOT / plan['contract_manifest']) == plan['contract_manifest_sha256']
    for relative, expected in read(ROOT / plan['contract_manifest']).items():
        assert digest(ROOT / relative) == expected, relative
    cert = read(task.folder / 'certification.json')
    assert cert['fingerprint'] == task.fingerprint() and cert['automatic_tests_passed']
    assert digest(plan['codex_binary']) == plan['codex_binary_sha256']
    for item in plan['preflight_evidence']:
        assert digest(ROOT / item['path']) == item['sha256']
    for system, value in plan['systems'].items():
        for name, expected in value['files'].items():
            assert digest(ROOT / 'systems' / system / name) == expected


def launch(system):
    plan = read(PLAN)
    folder = REVIEW / system
    folder.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-m', 'assessment', 'run', plan['template'], plan['instance'],
               '--level', '2', '--system', system, '--no-judge']
    record = {'system': system, 'plan_sha256': digest(PLAN), 'status': 'running',
              'started_at': datetime.now(timezone.utc).isoformat(), 'command': command,
              'agent_retries': 0, 'direct_paid_api_usd': 0}
    write(folder / 'invocation.json', record)
    started = time.monotonic()
    with (folder / 'stdout.json').open('w') as out, (folder / 'stderr.log').open('w') as err:
        done = subprocess.run(command, cwd=ROOT, stdout=out, stderr=err,
            env={**os.environ, 'CODEX_BINARY': plan['codex_binary'], 'OMP_NUM_THREADS': '1',
                 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'})
    record.update(status='finished', exit_code=done.returncode,
        finished_at=datetime.now(timezone.utc).isoformat(), cli_seconds=time.monotonic()-started)
    if done.returncode == 0:
        record['result'] = read(folder / 'stdout.json')
    write(folder / 'invocation.json', record)
    return record


def run():
    plan = read(PLAN)
    validate(plan)
    assert not REVIEW.exists(), 'Never retry assigned attempts or overwrite evidence'
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(launch, plan['systems']))
    print(json.dumps(rows, indent=2))
    return int(any(row['exit_code'] for row in rows))


def summarize():
    plan = read(PLAN)
    rows = []
    for system in plan['systems']:
        invocation = read(REVIEW / system / 'invocation.json')
        if invocation.get('exit_code') != 0:
            rows.append({'system': system, 'invocation': invocation})
            continue
        folder = ROOT / invocation['result']['directory']
        meta, assessment = read(folder/'run.json'), read(folder/'assessment.json')
        assert meta['fingerprint'] == assessment['fingerprint'] == plan['fingerprint']
        assert meta['system_sha256'] == plan['systems'][system]['files']['system.yaml']
        for child, manifest in [('frozen','artifacts.json'), ('inputs','input-manifest.json'),
                                ('system','substrate-manifest.json')]:
            assert inventory(folder/child) == read(folder/manifest), (system, child)
        events = folder/'logs/events.jsonl'
        assert digest(events) == read(folder/'controller/provenance.json')['trace']['sha256']
        usage = meta.get('usage')
        rows.append({'system': system, 'run': meta['id'], 'status':meta['status'],
            'computed':assessment['computed_outcome'], 'completion':assessment['outcome'],
            'checks': {k:v['state'] for k,v in assessment['checks'].items()},
            'skill':assessment.get('skill'), 'usage':usage,
            'fresh_input_plus_output_tokens':usage['input_tokens']-usage.get('cached_input_tokens',0)+usage['output_tokens'] if usage else None,
            'agent_seconds':meta.get('seconds'), 'cli_seconds':invocation['cli_seconds'],
            'tool_calls':meta.get('tool_calls'), 'feedback':read(folder/'controller/feedback-public.json'),
            'assessment_sha256':digest(folder/'assessment.json'), 'events_sha256':digest(events)})
    output = {'plan_sha256':digest(PLAN), 'rows':rows, 'direct_paid_api_usd':0,
              'subscription_invoice_usd':None, 'interpretation':'Two descriptive attempts on an already-inspected historical split; no tooling-effect or frontier-boundary inference.'}
    write(ROOT/'experiments/level2-open-results-2026-10-08.json', output)
    print(json.dumps(output,indent=2))


if __name__ == '__main__':
    if sys.argv[1:] == ['summarize']:
        summarize()
    else:
        sys.exit(run())
