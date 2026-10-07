"""Record only explicit exported human decisions, leaving every other case unset."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import station_interpretation as study


def validate_export(value, reference):
    assert value.get('schema_version') == 1 and value.get('kind') == 'human_reference_judgments', 'Not a human reference export'
    assert value.get('review_bundle_sha256') == reference['reference_bundle_sha256'], 'Review bundle mismatch; no decisions saved'
    fields = value.get('fields')
    assert isinstance(fields, dict), 'Fields must be an object'
    known = reference['records']
    allowed = set(known) | {k + '-notes' for k in known}
    assert set(fields).issubset(allowed), 'Unknown review fields'
    rows = {}
    for case, ref in known.items():
        verdict, notes = fields.get(case, ''), fields.get(case + '-notes', '')
        assert verdict in ('', *study.VERDICTS), 'Invalid verdict'
        assert isinstance(notes, str) and len(notes) <= 12000, 'Invalid notes'
        if verdict:
            rows[case] = {'criterion': ref['criterion'], 'verdict': verdict, 'notes': notes, 'basis': 'explicit_human_export'}
    assert rows, 'No explicit decisions in export'
    return rows


def record(path):
    reference = study.read(study.STUDY / 'private/reference.json')
    study.packets()  # Verify the packet and instruction freeze before recording labels.
    exported = study.read(path)
    rows = validate_export(exported, reference)
    if exported.get('review_presentation_version') == 2:
        context_path = study.ROOT / 'var/review/station-reference.context.json'
        assert exported.get('review_context_sha256') == study.digest(context_path), 'Human review context mismatch; no decisions saved'
    for row in rows.values():
        row['review_presentation_version'] = exported.get('review_presentation_version', 1)
        row['review_context_sha256'] = exported.get('review_context_sha256')
    target = study.STUDY / 'human-reference.json'
    old = study.read(target) if target.exists() else {'records': {}}
    if old.get('reference_bundle_sha256'):
        assert old['reference_bundle_sha256'] == reference['reference_bundle_sha256'], 'Existing labels use another bundle'
    merged = {**old['records'], **rows}
    judge = study.validate(study.read(study.STUDY / 'reviews/judge-luna.json'), study.packets())
    value = {'schema_version': 1, 'reference_bundle_sha256': reference['reference_bundle_sha256'],
             'records': merged, 'explicit_human_cases': len(merged), 'unreviewed_cases': len(reference['records']) - len(merged),
             'selected_case_judge_comparison': study.metrics(merged, judge),
             'scope': 'Targeted human-reviewed subset; do not extrapolate its agreement to unreviewed cases.',
             'received_at': datetime.now(timezone.utc).isoformat(), 'last_export_sha256': study.digest(path)}
    # Preserve every received export separately before updating the combined view.
    study.write(study.STUDY / 'human-exports' / (study.digest(path) + '.json'), study.read(path))
    study.write(target, value)
    return {'human_cases': len(merged), 'unreviewed_cases': value['unreviewed_cases'],
            'selected_case_judge_comparison': value['selected_case_judge_comparison']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    args = parser.parse_args()
    print(json.dumps(record(args.export), indent=2))
