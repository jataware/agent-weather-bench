"""The calibration's question/evidence boundary is tested without a model call."""
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / 'experiments/failure_judge_calibration.py'
SPEC = importlib.util.spec_from_file_location('failure_judge_calibration_test', PATH)
CAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAL)


def test_numeric_diagnostics_preserve_both_value_error_and_missing_units():
    path = CAL.ROOT / 'var/calibration/overnight-static-diagnostics' / (CAL.RUNS['monthly']+'.json')
    rows = CAL.numeric_rows(json.loads(path.read_text()))
    production = next(row for row in rows if row['file']=='forecast.nc' and row['variable']=='prediction')
    assert production['units']['status']=='missing'
    assert production['numeric']['status']=='compared'
    assert production['numeric']['max_abs_error']==pytest.approx(34.9690993608007)
    outer = next(row for row in rows if row['file']=='hindcasts.nc' and row['variable']=='prediction')
    assert outer['units']['status']=='match'
    assert outer['numeric']['max_abs_error']<1e-10


def test_station_units_are_correct_despite_diagnostic_value_error():
    path = CAL.ROOT / 'var/calibration/overnight-static-diagnostics' / (CAL.RUNS['station']+'.json')
    rows = CAL.numeric_rows(json.loads(path.read_text()))
    diagnostic = next(row for row in rows if row['variable']=='diagnostic_rmse')
    assert diagnostic['units']['status']=='match'
    assert diagnostic['numeric']['max_abs_error']>270
    headline = next(row for row in rows if row['variable']=='rmse')
    assert headline['numeric']['max_abs_error']<1e-10


@pytest.mark.parametrize('domain', ['monthly','station'])
def test_repairs_are_one_expression_and_keep_other_code_exact(domain):
    original = (CAL.ROOT/'var/runs'/CAL.RUNS[domain]/'frozen/workflow.py').read_text()
    repaired, change = CAL.correction(domain, original)
    assert repaired.replace(change['after'],change['before'])==original
    assert change['replacement_count']==1
    compile(repaired,'workflow.py','exec')  # Parse only; never execute the submission.


@pytest.mark.parametrize('domain', ['monthly','station'])
def test_source_only_control_cannot_inherit_original_numeric_evidence(domain):
    packet, _ = CAL.make_packet(domain, {}, corrected=True)
    assert set(packet['questions'])==set(CAL.questions(domain))
    assert 'report.txt' not in packet['files']
    assert 'answer.json' not in packet['files']
    assert 'controller/array-diagnostics.json' not in packet['files']
    assert 'No arrays have been regenerated' in packet['files']['controller/scope.txt']
    encoded=json.dumps(packet)
    assert 'expected' not in encoded.lower()
    assert CAL.RUNS[domain] not in encoded


def test_private_expectations_are_not_in_judge_packets(tmp_path):
    result=CAL.prepare(tmp_path/'public',tmp_path/'private')
    assert len(result['packets'])==4
    expected=json.loads((tmp_path/'private/expected.json').read_text())
    assert expected['sample-a']['expected']=={'production_method':'fail','validation_method':'pass'}
    assert expected['sample-b']['expected']=={'diagnostic_method':'pass','headline_method':'pass'}
    for row in result['packets']:
        packet=json.loads(Path(row['packet']).read_text())
        assert set(packet)=={'schema_version','questions','files'}
        assert 'expected' not in packet
        assert all('var/runs' not in name and 'failure' not in name for name in packet['files'])


def test_historical_judge_absence_is_not_reported_as_a_missed_fault(tmp_path):
    result=CAL.prepare(tmp_path/'public',tmp_path/'private')
    assert all(row['judge']=='none' for row in result['archival_judge'].values())
    assert all('No original model judge ran' in row['interpretation'] for row in result['archival_judge'].values())


def test_cap_rejects_excess_requests_before_backend(tmp_path,monkeypatch):
    CAL.prepare(tmp_path/'public',tmp_path/'private')
    monkeypatch.setattr(CAL.judge,'claude_cli',lambda *a,**k:pytest.fail('No backend call'))
    with pytest.raises(ValueError,match='four'):
        CAL.run_judges(tmp_path/'public',5)


def test_general_review_is_separate_and_excludes_hints_and_diagnostics(tmp_path):
    result=CAL.prepare(tmp_path/'public',tmp_path/'private')
    frozen={row['sample']:Path(row['packet']).read_bytes() for row in result['packets']}
    result=CAL.prepare_general(tmp_path/'public',tmp_path/'private')
    assert len(result['packets'])==6
    for row in result['packets']:
        path=Path(row['packet'])
        if row['sample'] in frozen:
            assert path.read_bytes()==frozen[row['sample']]
        else:
            packet=json.loads(path.read_text())
            assert set(packet['questions'])=={'consistency_across_artifacts','method_conformance'}
            assert packet['questions']['consistency_across_artifacts']==CAL.judge.interpretation_question('consistency_across_artifacts')
            assert not any(name.startswith('controller/') for name in packet['files'])
            assert 'constant-slope' not in packet['questions']['method_conformance']['requirement']
            assert 'combined' not in packet['questions']['method_conformance']['requirement']


def test_request_cap_and_durable_reservation_with_no_expected_label_load(tmp_path,monkeypatch):
    CAL.prepare(tmp_path/'public',tmp_path/'private')
    CAL.prepare_general(tmp_path/'public',tmp_path/'private')
    (tmp_path/'private/expected.json').unlink()
    calls=[]
    def backend(questions,files):
        calls.append((questions,files))
        reserved=json.loads((tmp_path/'public/requests.json').read_text())
        assert len(reserved)>=len(calls)
        return [], {'model':'fixture','usage':{}}
    monkeypatch.setattr(CAL.judge,'claude_cli',backend)
    assert len(CAL.run_judges(tmp_path/'public',4))==4
    assert len(CAL.run_judges(tmp_path/'public',2))==6
    assert len(calls)==6
    assert len(CAL.run_judges(tmp_path/'public',4))==6
    assert len(calls)==6  # No automatic citation retry or duplicate sample dispatch.


def test_ablation_removes_exactly_numeric_file_and_stops_at_eight(tmp_path,monkeypatch):
    CAL.prepare(tmp_path/'public',tmp_path/'private')
    CAL.prepare_general(tmp_path/'public',tmp_path/'private')
    calls=[]
    def backend(questions,files):
        calls.append((questions,files))
        return [], {'model':'fixture','usage':{}}
    monkeypatch.setattr(CAL.judge,'claude_cli',backend)
    CAL.run_judges(tmp_path/'public',4)
    CAL.run_judges(tmp_path/'public',2)
    result=CAL.prepare_ablation(tmp_path/'public',tmp_path/'private')
    assert len(result['packets'])==8
    for original,new in [('sample-a','sample-g'),('sample-c','sample-h')]:
        a=json.loads((tmp_path/'public/packets'/original/'packet.json').read_text())
        b=json.loads((tmp_path/'public/packets'/new/'packet.json').read_text())
        del a['files']['controller/array-diagnostics.json']
        assert a==b
    assert len(CAL.run_judges(tmp_path/'public',2))==8
    assert len(CAL.run_judges(tmp_path/'public',4))==8
    assert len(calls)==8
