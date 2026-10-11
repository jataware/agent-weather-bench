"""Validate explicitly reviewed historical contracts without changing their verdicts."""
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def contract_status(template, fingerprint):
    current = template.fingerprint()
    if fingerprint == current:
        return 'current'
    if template.name == 'mam-multimodel-outlook':
        ledger_path = ROOT / 'experiments/mam-probe-dtype-revision-2026-10-08.json'
        if ledger_path.is_file():
            revision = json.loads(ledger_path.read_text())
            if (fingerprint == revision.get('before_fingerprint')
                    and current == revision.get('after_fingerprint')
                    and template.spec['spec_version'] == revision.get('after_spec_version') == 2
                    and revision.get('original_assessments_preserved') is True):
                manifest_path = ROOT / revision['contract_snapshot']
                if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != revision['contract_snapshot_sha256']:
                    raise ValueError('Archived MAM contract manifest changed')
                manifest = json.loads(manifest_path.read_text())
                archive = ROOT / manifest['snapshot_root']
                digest = hashlib.sha256()
                for row in manifest['fingerprint_inputs']:
                    value = hashlib.sha256((archive / row['path']).read_bytes()).hexdigest()
                    if value != row['sha256']:
                        raise ValueError('Archived MAM contract changed: ' + row['path'])
                    digest.update(row['path'].encode() + b'\0' + bytes.fromhex(value))
                if digest.hexdigest() != fingerprint:
                    raise ValueError('Archived MAM fingerprint does not reproduce')
                return 'historical v1; probe dtype confound repaired in v2; original verdict preserved'
    erratum_path = ROOT / 'experiments/audit-brief-erratum-2026-10-08.json'
    if template.name == 'seasonal-forecast-audit' and erratum_path.is_file():
        erratum = json.loads(erratum_path.read_text())
        if (erratum.get('template') == template.name
                and fingerprint == erratum.get('before_fingerprint')
                and current == erratum.get('after_fingerprint')
                and erratum.get('before_spec_version') == 1
                and erratum.get('after_spec_version') == template.spec['spec_version'] == 2
                and erratum.get('scientific_implementation_unchanged') is True
                and erratum.get('original_assessments_preserved') is True):
            changed = {row['path']: row for row in erratum['changed_files']
                       if Path(row['path']).name != 'certification.json'}
            expected = {f'templates/{template.name}/{name}' for name in ('brief.md', 'spec.yaml')}
            if set(changed) != expected:
                raise ValueError('Audit erratum changes more than its declared brief/version')
            for relative, expected_hash in erratum['unchanged_files'].items():
                if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected_hash:
                    raise ValueError('Audit erratum scientific-file drift: ' + relative)
            for relative, row in changed.items():
                if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != row['after_sha256']:
                    raise ValueError('Audit erratum brief/version drift: ' + relative)
            return 'historical v1; objective path corrected in v2; original verdict preserved'
    ledger = ROOT / 'experiments/response-projection-revision-2026-10-08.json'
    revision = json.loads(ledger.read_text()) if ledger.is_file() else {}
    row = revision.get('legacy_templates', {}).get(template.name, {})
    accepted = [row.get('before_fingerprint'), *row.get('intermediate_fingerprints', [])]
    if (fingerprint not in accepted
            or row.get('after_fingerprint') != current
            or row.get('spec_version') != template.spec['spec_version']
            or callable(getattr(template.hooks, 'response_results', None))):
        raise ValueError(f'Unreviewed contract drift for {template.name}: {fingerprint} -> {current}')
    return 'historical; added response hooks unused; original verdict preserved'
