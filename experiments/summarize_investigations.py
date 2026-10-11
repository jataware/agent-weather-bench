"""Summarize frozen investigation attempts without launching inference."""
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template
from assessment.storage import digest, inventory


def read(path):
    return json.loads(path.read_text())


def submission_imports(folder):
    names = set()
    for path in folder.rglob('*.py'):
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split('.')[0])
    return sorted(names)


def summarize():
    rows, pending, seen = [], [], set()
    for folder in sorted((ROOT / 'var/template-runs').glob('*-investigation-astra-*')):
        meta = read(folder / 'run.json')
        key = (meta['template'], meta['instance']['id'], meta['system'])
        if key in seen:
            raise ValueError(f'Duplicate attempt requires explicit review: {key}')
        seen.add(key)
        if meta['status'] in ('created', 'running') or not (folder / 'assessment.json').is_file():
            pending.append(meta['id'])
            continue
        assessment = read(folder / 'assessment.json')
        if meta['fingerprint'] != assessment['fingerprint']:
            raise ValueError('Contract drift: ' + meta['id'])
        from experiments.evidence_contracts import contract_status
        historical_status = contract_status(Template(meta['template']), assessment['fingerprint'])
        if digest(ROOT / 'systems' / meta['system'] / 'system.yaml') != meta['system_sha256']:
            raise ValueError('System definition drift: ' + meta['id'])
        for artifact, manifest in [('frozen', 'artifacts.json'), ('inputs', 'input-manifest.json')]:
            manifest_path = folder / manifest
            if inventory(folder / artifact) != read(manifest_path):
                raise ValueError(f'{artifact} changed: ' + meta['id'])
        checks = assessment['checks']
        provenance = read(folder / 'controller/provenance.json')
        rows.append({
            'run': meta['id'], 'directory': str(folder.relative_to(ROOT)),
            'template': meta['template'], 'instance': meta['instance']['id'],
            'system': meta['system'], 'system_sha256': meta['system_sha256'],
            'runtime_image': meta['runtime_image'], 'spec_version': meta['spec_version'],
            'fingerprint': meta['fingerprint'], 'status': meta['status'],
            'contract_status': historical_status,
            'completion': assessment['outcome'], 'computed': assessment['computed_outcome'],
            'supplementary': assessment['advisory_outcome'], 'skill': assessment.get('skill'),
            'seconds': meta['seconds'], 'tool_calls': meta['tool_calls'], 'usage': meta['usage'],
            'collection_recovery': meta.get('collection_recovery'),
            'failed_checks': [n for n, row in checks.items() if row['state'] == 'fail'],
            'unresolved_checks': [n for n, row in checks.items() if row['state'] == 'unresolved'],
            'check_counts': {state: sum(row['state'] == state for row in checks.values())
                             for state in ('pass', 'fail', 'unresolved')},
            'substrate_use': provenance['substrate_use'], 'sandbox': provenance['sandbox'],
            'declared_submission_imports': submission_imports(folder / 'frozen'),
            'import_note': 'Static imports in submitted Python; command-log tooling use is separate. Imports alone do not prove benefit.',
            'judge': assessment.get('judge') or {},
        })
    return {
        'schema_version': 1, 'plan': 'experiments/parallel-investigations.yaml',
        'completed_attempts': len(rows), 'pending_attempts': pending,
        'direct_api_key_calls': 0,
        'billing': 'Subscription-authenticated inference; provider list-price estimates are not invoices.',
        'agent_token_totals': {key: sum((row['usage'] or {}).get(key, 0) for row in rows)
                               for key in ('input_tokens', 'cached_input_tokens', 'output_tokens', 'total_tokens')},
        'judge_list_price_usd': sum(usage.get('list_price_usd', 0) or 0 for row in rows
                                  for usage in row['judge'].get('usage', [])),
        'rows': rows,
    }


if __name__ == '__main__':
    result = summarize()
    (ROOT / 'experiments/parallel-results-2026-10-08.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'rows'}, indent=2))
