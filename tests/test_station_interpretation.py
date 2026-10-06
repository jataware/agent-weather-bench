"""Guard against fabricated evidence and misleading calibration denominators."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('station_interpretation', ROOT / 'scripts/station_interpretation.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)
human_spec = importlib.util.spec_from_file_location('record_station_reference', ROOT / 'scripts/record_station_reference.py')
human = importlib.util.module_from_spec(human_spec)
# The record script imports the frozen study module under its ordinary name.
import sys
sys.modules['station_interpretation'] = study
human_spec.loader.exec_module(human)


def evidence_and_rating():
    evidence = {'x': {'criterion': 'uncertainty', 'task_contract': 'Use paired observations.',
                      'files': {'report.txt': {'available': True, 'complete': True, 'text': 'These results are inconclusive.'}}}}
    row = {'case': 'x', 'criterion': 'uncertainty', 'verdict': 'pass', 'reason': 'Honest bounded conclusion.',
           'confidence': .8, 'citations': [{'source': 'report.txt', 'quote': 'results are inconclusive'}]}
    return evidence, {'ratings': [row]}


def test_fabricated_or_unavailable_evidence_is_rejected():
    evidence, ratings = evidence_and_rating()
    assert study.validate(ratings, evidence)['x']['verdict'] == 'pass'
    ratings['ratings'][0]['citations'][0]['quote'] = 'The results prove significance.'
    with pytest.raises(AssertionError, match='exact evidence passage'):
        study.validate(ratings, evidence)
    evidence['x']['files']['report.txt']['available'] = False
    with pytest.raises(AssertionError, match='unavailable text'):
        study.validate(ratings, evidence)


def test_missing_assessment_evidence_can_be_cited_without_inventing_a_defect():
    evidence, ratings = evidence_and_rating()
    evidence['x']['files']['report.txt'] = {'available': False, 'complete': False, 'reason': 'Relevant evidence omitted from this packet.'}
    row = ratings['ratings'][0]
    row.update(verdict='unresolved', reason='Insufficient evidence.', citations=[{'source': 'availability:report.txt', 'quote': 'omitted from this packet'}])
    assert study.validate(ratings, evidence)['x']['verdict'] == 'unresolved'


def test_duplicates_missing_cases_and_wrong_criterion_are_rejected():
    evidence, ratings = evidence_and_rating()
    duplicate = copy.deepcopy(ratings)
    duplicate['ratings'].append(copy.deepcopy(duplicate['ratings'][0]))
    with pytest.raises(AssertionError, match='extra ratings'):
        study.validate(duplicate, evidence)
    with pytest.raises(AssertionError, match='Incomplete'):
        study.validate({'ratings': []}, evidence)
    ratings['ratings'][0]['criterion'] = 'another criterion'
    with pytest.raises(AssertionError, match='Wrong criterion'):
        study.validate(ratings, evidence)


@pytest.mark.parametrize('confidence', [True, float('nan'), float('inf'), 1.1])
def test_invalid_confidence_is_not_calibration_data(confidence):
    evidence, ratings = evidence_and_rating()
    ratings['ratings'][0]['confidence'] = confidence
    with pytest.raises(AssertionError, match='confidence'):
        study.validate(ratings, evidence)


def test_abstentions_and_missing_evidence_do_not_inflate_precision_or_recall():
    references = {k: {'verdict': v} for k, v in [('a', 'pass'), ('b', 'pass'), ('c', 'fail'), ('d', 'unresolved')]}
    ratings = {k: {'verdict': v} for k, v in [('a', 'pass'), ('b', 'unresolved'), ('c', 'pass'), ('d', 'fail')]}
    result = study.metrics(references, ratings)
    assert result['known_reference_cases'] == 3
    assert result['decision_coverage_on_known'] == {'numerator': 2, 'denominator': 3}
    assert result['pass_precision_on_known']['value'] == .5
    assert result['pass_recall_including_abstentions']['value'] == .5
    assert result['false_acceptance'] == 1
    assert result['unsupported_decisions_on_missing_evidence'] == 1


def test_no_known_passes_yields_undefined_precision_and_recall():
    result = study.metrics({'a': {'verdict': 'unresolved'}}, {'a': {'verdict': 'unresolved'}})
    assert result['pass_precision_on_known']['value'] is None
    assert result['pass_recall_including_abstentions']['value'] is None


def test_human_export_labels_only_explicitly_reviewed_cases():
    reference = {'reference_bundle_sha256': 'bundle', 'records': {'a': {'criterion': 'scope'}, 'b': {'criterion': 'scope'}}}
    value = {'schema_version': 1, 'kind': 'human_reference_judgments', 'review_bundle_sha256': 'bundle',
             'fields': {'a': 'unresolved', 'a-notes': 'Need more evidence.', 'b': '', 'b-notes': 'Unreviewed.'}}
    rows = human.validate_export(value, reference)
    assert set(rows) == {'a'}
    assert rows['a']['verdict'] == 'unresolved'
    value['review_bundle_sha256'] = 'another study'
    with pytest.raises(AssertionError, match='bundle mismatch'):
        human.validate_export(value, reference)


def test_empty_or_injected_human_review_is_rejected():
    reference = {'reference_bundle_sha256': 'bundle', 'records': {'a': {'criterion': 'scope'}}}
    value = {'schema_version': 1, 'kind': 'human_reference_judgments', 'review_bundle_sha256': 'bundle', 'fields': {'a': ''}}
    with pytest.raises(AssertionError, match='No explicit decisions'):
        human.validate_export(value, reference)
    value['fields']['unexpected-case'] = 'pass'
    with pytest.raises(AssertionError, match='Unknown review fields'):
        human.validate_export(value, reference)
