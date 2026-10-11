"""Exactly one Luna/Astra pair on a frozen, validated monthly calibration task.

No inference occurs on import, freeze or validation. Parallelism orchestrates two
fresh CLI processes; scientific files are never read from Python threads.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import DECIDING, Template
from assessment.storage import digest, inventory, read, write
from assessment.systems import validate as validate_system

SYSTEMS = ('monthly-fragility-luna-accord', 'monthly-fragility-astra-accord')
DISALLOWED_PUBLIC_FILENAME = 'africas2s-smoothed-method.py.txt'
IMAGE = 'sha256:08dbb4fce25955523a4c3caa3e2efdfb75b960dae3d2b8f3b92746e7f19f7c49'
BUDGET = {'max_seconds': 900, 'max_tool_calls': 32, 'command_seconds': 120,
          'max_uncached_and_output_tokens': 100000, 'max_output_tokens': 20000}


def check_systems():
    rows = {}
    adapter_text = []
    for backbone, name in zip(('luna', 'astra'), SYSTEMS):
        folder = ROOT / 'systems' / name
        config = validate_system(folder / 'system.yaml')
        if (config['runtime'] != {'image': IMAGE, 'memory': '1536m', 'cpus': 2}
            or config['budget'] != BUDGET or config['substrate']['paths'] != ['adapter.py']):
            raise ValueError('System environment/budget/substrate differs from declared pair')
        text = (folder / 'adapter.py').read_text()
        if f'MODEL = "gpt-6-{backbone}"' not in text:
            raise ValueError('Unexpected adapter model identity')
        adapter_text.append(text.replace(f'MODEL = "gpt-6-{backbone}"', 'MODEL = "MATCHED"'))
        rows[name] = {'model': f'gpt-6-{backbone}', 'reasoning_effort': 'high',
                      'files': {file: digest(folder / file) for file in ('system.yaml', 'adapter.py')}}
    if adapter_text[0] != adapter_text[1]:
        raise ValueError('Adapters differ beyond the model constant')
    configs = [read(ROOT / 'systems' / name / 'system.yaml') for name in SYSTEMS]
    for value in configs:
        value.pop('id')
    if configs[0] != configs[1]:
        raise ValueError('System definitions differ beyond ID')
    return rows


def freeze(template_name, instance, codex_binary, plan_path, review_directory, preflight_evidence=()):
    """Root calls this only after author controls and Docker proof have passed."""
    plan_path, review_directory = Path(plan_path), Path(review_directory)
    if plan_path.exists() or review_directory.exists():
        raise ValueError('Never overwrite an existing attempt plan or review directory')
    template = Template(template_name)
    template.instance(instance)
    certification = read(template.folder / 'certification.json')
    if certification['fingerprint'] != template.fingerprint() or not certification['automatic_tests_passed']:
        raise ValueError('Current task must pass automatic certification before freezing actors')
    systems = check_systems()
    source_files = inventory(template.private)
    if not source_files:
        raise ValueError('No frozen task data to hash')
    # This task's staging hook only copies files/writes JSON; no scientific
    # decoder is run here. Audit the exact public bundle before any actor sees it.
    with tempfile.TemporaryDirectory(prefix='monthly-public-stage-') as temporary:
        public = Path(temporary) / 'inputs'
        template.hooks.stage_inputs(template.private, template.instance(instance), public)
        public_manifest = inventory(public)
    if any(Path(name).name == DISALLOWED_PUBLIC_FILENAME for name in public_manifest):
        raise ValueError('Curated function excerpt must not be staged to actors')
    file_hashes = {str(path.relative_to(ROOT)): digest(path)
                  for path in template.folder.rglob('*') if path.is_file() and '__pycache__' not in path.parts}
    file_hashes.update({f'assessment/{name}': digest(ROOT / 'assessment' / name) for name in DECIDING})
    for name in SYSTEMS:
        file_hashes.update({f'systems/{name}/{file}': expected for file, expected in systems[name]['files'].items()})
    file_hashes['experiments/monthly_fragility.py'] = digest(Path(__file__))
    manifest_path = plan_path.with_name(plan_path.stem + '-contract.json')
    if manifest_path.exists():
        raise ValueError('Contract manifest already exists')
    write(manifest_path, file_hashes)
    evidence = [{'path': str(Path(path).relative_to(ROOT) if Path(path).is_absolute() else path),
                 'sha256': digest(path)} for path in preflight_evidence]
    plan = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'ready',
        'template': template_name, 'instance': instance, 'level': 1, 'fingerprint': template.fingerprint(),
        'max_new_agent_attempts': 2, 'agent_retries': 0, 'systems': systems,
        'design': 'One matched Luna/Astra pair on a prescribed scientific reproduction job; ordinary installed documentation only.',
        'selection': 'Fresh counterparts to historical Luna production-comparator/inference failures; single attempts probe reproducibility, not a persistent capability boundary.',
        'runtime_image': IMAGE, 'budget': BUDGET, 'no_judge': True,
        'cached_token_note': 'Cache tokens recorded without a total-token cap; usage checkpoint overshoot retained.',
        'codex_binary': str(Path(codex_binary).resolve()), 'codex_binary_sha256': digest(codex_binary),
        'contract_manifest': str(manifest_path.resolve().relative_to(ROOT)),
        'contract_manifest_sha256': digest(manifest_path),
        'private_source_manifest': source_files, 'public_input_manifest': public_manifest,
        'public_input_policy': 'Prescribed mathematical algorithm is supplied; curated library function excerpt is excluded. Ordinary installed library documentation is optional.',
        'preflight_evidence': evidence,
        'review_directory': str(review_directory.resolve().relative_to(ROOT)),
        'direct_paid_api_usd': 0, 'subscription_invoice_usd': None,
        'rules': ['No launch until root releases author-validation workers and explicitly gives go.',
                  'Exactly two fresh attempts; preserve all failures and frozen original assessments.',
                  'Use normal assessment.run with --no-judge; prose remains separately unresolved.',
                  'Report numeric science, reproducibility and packaging separately.',
                  'No capability boundary from one failure, budget exhaustion or API failure.']}
    write(plan_path, plan)
    return plan


def validate(plan):
    if plan.get('status') != 'ready' or plan.get('max_new_agent_attempts') != 2 or tuple(plan['systems']) != SYSTEMS:
        raise ValueError('A frozen ready two-attempt plan is required')
    template = Template(plan['template'])
    if template.fingerprint() != plan['fingerprint']:
        raise ValueError('Task/controller fingerprint changed')
    if inventory(template.private) != plan['private_source_manifest']:
        raise ValueError('Frozen private scientific data changed')
    public_manifest = plan.get('public_input_manifest', {})
    if not public_manifest or any(Path(name).name == DISALLOWED_PUBLIC_FILENAME for name in public_manifest):
        raise ValueError('Frozen public input audit is absent or includes curated function excerpt')
    if check_systems() != plan['systems']:
        raise ValueError('Matched system definition changed')
    if digest(plan['codex_binary']) != plan['codex_binary_sha256']:
        raise ValueError('Pinned Codex binary changed')
    contract = ROOT / plan['contract_manifest']
    if digest(contract) != plan['contract_manifest_sha256']:
        raise ValueError('Readiness contract manifest changed')
    for relative, expected in read(contract).items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f'Frozen contract changed: {relative}')
    for row in plan['preflight_evidence']:
        if digest(ROOT / row['path']) != row['sha256']:
            raise ValueError('Preflight evidence changed')
    return template


def _attempt(system, plan, plan_sha256):
    folder = ROOT / plan['review_directory'] / system
    folder.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-m', 'assessment', 'run', plan['template'], plan['instance'],
               '--system', system, '--no-judge']
    record = {'system': system, 'status': 'running', 'plan_sha256': plan_sha256,
              'started_at': datetime.now(timezone.utc).isoformat(), 'command': command,
              'agent_retries': 0, 'direct_paid_api_usd': 0}
    write(folder / 'invocation.json', record)
    started = time.monotonic()
    with (folder / 'stdout.json').open('w') as output, (folder / 'stderr.log').open('w') as errors:
        result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=errors,
            env={**os.environ, 'CODEX_BINARY': plan['codex_binary'], 'PYTHONDONTWRITEBYTECODE': '1',
                 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'})
    record.update(status='finished', exit_code=result.returncode, cli_seconds=time.monotonic()-started,
                  finished_at=datetime.now(timezone.utc).isoformat())
    if result.returncode == 0:
        record['result'] = read(folder / 'stdout.json')
    write(folder / 'invocation.json', record)
    return record


def run(plan_path):
    plan = read(plan_path)
    validate(plan)
    folder = ROOT / plan['review_directory']
    folder.mkdir(parents=True, exist_ok=False)  # A consumed plan cannot silently retry.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_attempt, system, plan, digest(plan_path)) for system in SYSTEMS]
        results = [future.result() for future in futures]
    write(folder / 'invocations.json', results)
    return results


def summarize(plan_path, output_path):
    plan = read(plan_path)
    rows = []
    for system in SYSTEMS:
        invocation = read(ROOT / plan['review_directory'] / system / 'invocation.json')
        if invocation.get('exit_code') != 0:
            rows.append({'system': system, 'invocation': invocation})
            continue
        folder = ROOT / invocation['result']['directory']
        metadata, assessment = read(folder / 'run.json'), read(folder / 'assessment.json')
        if metadata['fingerprint'] != plan['fingerprint'] or assessment['fingerprint'] != plan['fingerprint']:
            raise ValueError('Attempt assessment fingerprint differs from launch contract')
        for child, manifest in [('frozen', 'artifacts.json'), ('inputs', 'input-manifest.json'),
                                 ('system', 'substrate-manifest.json')]:
            if inventory(folder / child) != read(folder / manifest):
                raise ValueError(f'Immutable attempt bundle changed: {system}/{child}')
        actual_inputs = inventory(folder / 'inputs')
        if any(Path(name).name == DISALLOWED_PUBLIC_FILENAME for name in actual_inputs):
            raise ValueError('Actual actor inputs included curated library function excerpt')
        if actual_inputs != plan['public_input_manifest']:
            raise ValueError('Actual actor inputs differ from frozen public-stage audit')
        if digest(folder / 'logs/events.jsonl') != read(folder / 'controller/provenance.json')['trace']['sha256']:
            raise ValueError('Attempt trace changed')
        usage = metadata.get('usage')
        rows.append({'system': system, 'run': metadata['id'], 'status': metadata['status'],
            'computed_outcome': assessment['computed_outcome'], 'completion': assessment['outcome'],
            'checks': {key: {'state': value['state'], 'detail': value.get('detail')}
                       for key, value in assessment['checks'].items()},
            'skill': assessment.get('skill'), 'usage': usage,
            'fresh_input_plus_output_tokens': usage['input_tokens']-usage.get('cached_input_tokens', 0)+usage['output_tokens'] if usage else None,
            'agent_seconds': metadata.get('seconds'), 'cli_seconds': invocation['cli_seconds'],
            'tool_calls': metadata.get('tool_calls'), 'assessment_sha256': digest(folder / 'assessment.json'),
            'events_sha256': digest(folder / 'logs/events.jsonl')})
    value = {'schema_version': 1, 'plan_sha256': digest(plan_path), 'rows': rows, 'direct_paid_api_usd': 0,
             'subscription_invoice_usd': None,
             'scope': 'Two descriptive fresh attempts on genuine historical data; no repeatability or persistent capability-boundary claim.'}
    if Path(output_path).exists():
        raise ValueError('Never overwrite an earlier results summary')
    write(output_path, value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['validate', 'run', 'summarize'])
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.action == 'run':
        result = run(args.plan)
    elif args.action == 'summarize':
        if not args.output:
            parser.error('--output is required for summarize')
        result = summarize(args.plan, args.output)
    else:
        validate(read(args.plan)); result = {'validated': True, 'model_calls': 0}
    print(json.dumps(result, indent=2, allow_nan=False))
