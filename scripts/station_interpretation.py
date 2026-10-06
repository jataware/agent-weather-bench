"""Validate and compare small, explicitly provisional judge-calibration records."""
from pathlib import Path
import argparse
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'var/calibration/station-interpretation-v1'
VERDICTS = ('pass', 'fail', 'unresolved')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def packets(study=STUDY):
    folder = study / 'reviewer'
    manifest = read(folder / 'manifest.json')
    assert digest(folder / 'instructions.txt') == manifest['instructions_sha256'], 'Judge instructions drifted'
    output = {}
    for row in manifest['packets']:
        path = folder / row['file']
        assert path.resolve().is_relative_to(folder.resolve()), 'Unsafe packet path'
        assert digest(path) == row['sha256'], 'Packet drift: ' + row['case']
        packet = read(path)
        assert packet['case'] == row['case'] and packet['criterion'] == row['criterion']
        assert row['case'] not in output, 'Duplicate manifest case'
        for item in packet['files'].values():
            if item['available']:
                assert item['complete'] and hashlib.sha256(item['text'].encode()).hexdigest() == item['sha256']
        output[row['case']] = packet
    return output


def validate(value, evidence):
    rows = value['ratings']
    assert isinstance(rows, list), 'ratings must be a list'
    assert len(rows) == len(evidence), 'Incomplete or extra ratings'
    output = {}
    for row in rows:
        case = row['case']
        assert case in evidence and case not in output, 'Unknown/duplicate case: ' + case
        packet = evidence[case]
        assert row['criterion'] == packet['criterion'], 'Wrong criterion'
        assert row['verdict'] in VERDICTS, 'Invalid verdict'
        assert isinstance(row['reason'], str) and row['reason'].strip(), 'Reason required'
        confidence = row['confidence']
        assert type(confidence) in (float, int) and math.isfinite(confidence) and 0 <= confidence <= 1, 'Invalid confidence'
        citations = row['citations']
        assert isinstance(citations, list) and 1 <= len(citations) <= 10, 'Evidence citations required'
        for citation in citations:
            source, quote = citation['source'], citation['quote']
            assert isinstance(quote, str) and quote.strip(), 'Empty citation'
            if source == 'task_contract':
                text = packet['task_contract']
            elif source.startswith('availability:'):
                item = packet['files'][source.partition(':')[2]]
                assert item['available'] is False, 'Unavailable citation points to available evidence'
                text = item['reason']
            else:
                item = packet['files'][source]
                assert item['available'] and item['complete'], 'Cannot cite unavailable text'
                text = item['text']
            assert quote in text, 'Citation is not an exact evidence passage: ' + case
        output[case] = row
    assert set(output) == set(evidence)
    return output


def freeze_reference(study=STUDY):
    path = study / 'private/reference.json'
    if path.exists():
        raise ValueError('Reference already frozen; create a new version rather than overwrite.')
    evidence = packets(study)
    initial = read(study / 'private/initial-expectations.json')
    reviews = [validate(read(study / f'reviews/reference-{name}.json'), evidence) for name in ('a', 'b')]
    decisions_path = study / 'private/adjudication-decisions.json'
    decisions = read(decisions_path) if decisions_path.exists() else {}
    records, disagreements = {}, []
    for case, expected in initial.items():
        ratings = [r[case]['verdict'] for r in reviews]
        if ratings == [expected['verdict']] * 2:
            verdict, reason = expected['verdict'], expected['reason']
            basis = 'contract_backed_expectation_and_two_independent_assistant_reviews'
        else:
            disagreements.append(case)
            if case not in decisions:
                raise ValueError('Explicit adjudication required for ' + case)
            decision = decisions[case]
            assert decision['verdict'] in VERDICTS and decision['reason'].strip()
            verdict, reason = decision['verdict'], decision['reason']
            basis = 'explicit_assistant_adjudication_of_review_disagreement'
        records[case] = {'criterion': evidence[case]['criterion'], 'verdict': verdict, 'reason': reason,
                         'basis': basis, 'human_label': None, 'initial_verdict': expected['verdict'], 'review_verdicts': ratings}
    paths = [study / 'reviewer/manifest.json', study / 'reviewer/instructions.txt',
             study / 'private/initial-expectations.json', study / 'private/lineage.json',
             ROOT / 'studies/station-interpretation-v1/protocol.yaml', Path(__file__),
             ROOT / 'scripts/prepare_station_interpretation.py',
             study / 'reviews/reference-a.json', study / 'reviews/reference-b.json']
    if decisions_path.exists():
        paths.append(decisions_path)
    sources = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    value = {'schema_version': 1, 'study': 'station-interpretation-v1', 'status': 'provisional_assistant_reviewed_references',
             'records': records, 'disagreements': disagreements, 'human_labels': None,
             'fresh_check_parents': 0, 'sources_sha256': sources,
             'judge_prompt_sha256': digest(study / 'reviewer/instructions.txt'),
             'reference_bundle_sha256': hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()}
    write(path, value)
    return {'frozen_cases': len(records), 'review_disagreements': disagreements, 'human_labels': None}


def metrics(reference, ratings):
    matrix = {a: {b: 0 for b in VERDICTS} for a in VERDICTS}
    for case, ref in reference.items():
        matrix[ref['verdict']][ratings[case]['verdict']] += 1
    known = sum(sum(matrix[v].values()) for v in ('pass', 'fail'))
    decided = sum(matrix[a][b] for a in ('pass', 'fail') for b in ('pass', 'fail'))
    true_pass = matrix['pass']['pass']
    predicted_pass = true_pass + matrix['fail']['pass']
    actual_pass = sum(matrix['pass'].values())
    return {'cases': len(reference), 'confusion_reference_then_judge': matrix,
            'exact_agreement': {'numerator': sum(matrix[v][v] for v in VERDICTS), 'denominator': len(reference)},
            'false_acceptance': matrix['fail']['pass'], 'false_rejection': matrix['pass']['fail'],
            'known_reference_cases': known, 'judge_abstentions_on_known': known - decided,
            'decision_coverage_on_known': {'numerator': decided, 'denominator': known},
            'pass_precision_on_known': {'numerator': true_pass, 'denominator': predicted_pass, 'value': true_pass / predicted_pass if predicted_pass else None},
            'pass_recall_including_abstentions': {'numerator': true_pass, 'denominator': actual_pass, 'value': true_pass / actual_pass if actual_pass else None},
            'unsupported_decisions_on_missing_evidence': matrix['unresolved']['pass'] + matrix['unresolved']['fail']}


def compare(study=STUDY):
    evidence = packets(study)
    frozen = read(study / 'private/reference.json')
    for name, expected in frozen['sources_sha256'].items():
        assert digest(ROOT / name) == expected, 'Frozen reference source drift: ' + name
    judge_path = study / 'reviews/judge-luna.json'
    ratings = validate(read(judge_path), evidence)
    references = frozen['records']
    groups = {}
    for criterion in sorted({p['criterion'] for p in evidence.values()}):
        selected = {k: v for k, v in references.items() if v['criterion'] == criterion}
        groups[criterion] = metrics(selected, ratings)
    lineage = read(study / 'private/lineage.json')
    natural = {k: v for k, v in references.items() if lineage[k]['kind'] == 'natural_report'}
    result = {'schema_version': 1, 'study': 'station-interpretation-v1',
              'status': 'development_comparison_against_provisional_assistant_references',
              'reference_bundle_sha256': frozen['reference_bundle_sha256'], 'judge_output_sha256': digest(judge_path),
              'judge_prompt_sha256': frozen['judge_prompt_sha256'], 'all': metrics(references, ratings),
              'by_criterion': groups, 'natural_criterion_cases': metrics(natural, ratings),
              'disagreements': [k for k in references if references[k]['verdict'] != ratings[k]['verdict']],
              'schema_valid_records': len(ratings), 'exact_evidence_citations_validated': True,
              'human_confirmed_accuracy': None, 'fresh_check_parents': 0, 'human_labels': None,
              'separately_billed_calls': 0, 'measured_provider_cost_usd': None,
              'limitations': ['18 criterion cases share one inspected parent; not 18 independent workflows.',
                              'References reviewed by assistants; Ezekiel has not confirmed labels.',
                              'Same subscription model context may correlate reference-review errors.',
                              'Candidate is a one-batch subscription helper judge, not locked native auto-v1.',
                              'Exact citation validity does not establish semantic justification.',
                              'No held-out judge accuracy, task-transfer result or calibrated ranking established.']}
    write(study / 'comparison.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('validate', 'freeze', 'compare'))
    parser.add_argument('path', nargs='?')
    args = parser.parse_args()
    if args.command == 'validate':
        rows = validate(read(args.path), packets())
        result = {'valid_records': len(rows)}
    elif args.command == 'freeze':
        result = freeze_reference()
    else:
        result = compare()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
