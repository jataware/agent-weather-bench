"""No Docker, model calls, native imports or private weather data are needed."""
import importlib.util
import json
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[1] / 'experiments/sequential_actor.py'
SPEC = importlib.util.spec_from_file_location('sequential_actor_test', PATH)
ACTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACTOR)


def feedback(tmp_path, evaluate=None, limit=5):
    work = tmp_path / 'work'
    submission = work / 'submission'
    submission.mkdir(parents=True)
    (submission / 'forecast-program.json').write_text(json.dumps({'argv': ['python', '-u', 'forecast.py']}))
    (submission / 'forecast.py').write_text('# first candidate\n')
    episode = {'cases': [{'case_id': 'a'}]}
    if evaluate is None:
        evaluate = lambda *args, **kwargs: {'state': 'pass', 'predictions': [[2.0]], 'events': []}
    score = lambda *args: {'rmse_mm': 1.0, 'raw_model_rmse_mm': 2.0,
                           'climatology_rmse_mm': 3.0, 'issues': 1, 'cells': 1,
                           'yearwise': {'private': 'not returned'}, 'private_truth': 912.0}
    value = ACTOR.ProgramFeedback(work, tmp_path / 'controller', episode, 'image', evaluate, score,
                                  max_submissions=limit)
    return value, submission


def test_development_freezes_code_and_returns_only_aggregate_metrics(tmp_path):
    value, submission = feedback(tmp_path)
    reply = value.query('forecast-program.json')
    assert reply['exit_code'] == 0
    assert json.loads(reply['stdout']) == {'rmse_mm': 1.0, 'raw_model_rmse_mm': 2.0,
        'climatology_rmse_mm': 3.0, 'issues': 1, 'cells': 1}
    (submission / 'forecast.py').write_text('# changed candidate\n')
    assert (value.controller / 'query-001/frozen/forecast.py').read_text() == '# first candidate\n'
    assert value.public_summary()['final_score_exposed'] is False


def test_invalid_manifest_counts_before_validation_and_limit_is_enforced(tmp_path):
    value, _ = feedback(tmp_path, limit=1)
    first = value.query('../private.json')
    assert first['exit_code'] == 1 and first['feedback_remaining'] == 0
    assert len(value.attempts) == 1
    second = value.query('forecast-program.json')
    assert second['exit_code'] == 1 and value.denials == 1 and len(value.attempts) == 1


def test_private_evaluation_reason_is_not_returned_to_actor(tmp_path):
    def broken(*args, **kwargs):
        return {'state': 'fail', 'predictions': [], 'events': [{'observed_mm': [912.0]}],
                'reason': 'private target is 912.0'}
    value, _ = feedback(tmp_path, evaluate=broken)
    reply = value.query('forecast-program.json')
    assert reply['exit_code'] == 1
    assert '912' not in json.dumps(reply)
    assert '912' not in json.dumps(value.public_summary())
    assert '912' in (value.controller / 'query-001/evaluation.json').read_text()


def test_symlink_bundle_rejected_before_evaluation(tmp_path):
    def unexpected(*args, **kwargs):
        pytest.fail('A linked bundle must never be evaluated')
    value, submission = feedback(tmp_path, evaluate=unexpected)
    (submission / 'linked.py').symlink_to('forecast.py')
    assert value.query('forecast-program.json')['exit_code'] == 1
    assert len(value.attempts) == 1


def test_evaluator_cannot_silently_mutate_frozen_program(tmp_path):
    def changed(submission, *args, **kwargs):
        (Path(submission) / 'forecast.py').write_text('# altered frozen code\n')
        return {'state': 'pass', 'predictions': [[2.0]], 'events': []}
    value, _ = feedback(tmp_path, evaluate=changed)
    assert value.query('forecast-program.json')['exit_code'] == 1
    assert value.attempts[0]['status'] == 'failed'
    assert 'changed during evaluation' in value.attempts[0]['private_error']


def test_case_alignment_and_strict_manifest(tmp_path):
    assert ACTOR.normalize_predictions({'cases': [{'case_id': 'b'}, {'case_id': 'a'}]}, [[2], [1]]) == [
        {'case_id': 'b', 'prediction_mm': [2]}, {'case_id': 'a', 'prediction_mm': [1]}]
    with pytest.raises(ValueError):
        ACTOR.normalize_predictions({'cases': [{'case_id': 'a'}]}, [])
    (tmp_path / 'bad.json').write_text(json.dumps({'argv': ['python', 'forecast.py'], 'private': 'extra'}))
    with pytest.raises(ValueError):
        ACTOR.load_manifest(tmp_path, 'bad.json')


def test_nonready_plan_never_invokes_actor(tmp_path, monkeypatch):
    plan = tmp_path / 'plan.json'
    plan.write_text(json.dumps({'status': 'draft', 'max_new_agent_attempts': 1}))
    monkeypatch.setattr(ACTOR, 'launch_actor', lambda *a, **k: pytest.fail('No inference on draft plan'))
    with pytest.raises(ValueError, match='ready'):
        ACTOR.launch_plan(plan)


def test_trusted_actor_protocol_runs_score_feedback_without_model_or_docker(tmp_path, monkeypatch):
    system = tmp_path / 'system'
    system.mkdir()
    (system / 'adapter.py').write_text(
        'import json,sys\n'
        'request=json.loads(sys.stdin.readline())\n'
        'assert request["tools"][0]["name"]=="score_development"\n'
        'print(json.dumps({"type":"execute","id":"write","command":"trusted-fixture"}),flush=True)\n'
        'assert json.loads(sys.stdin.readline())["exit_code"]==0\n'
        'print(json.dumps({"type":"score_development","id":"score","prediction_file":"forecast-program.json"}),flush=True)\n'
        'feedback=json.loads(sys.stdin.readline())\n'
        'assert feedback["exit_code"]==0 and feedback["feedback_remaining"]==4\n'
        'print(json.dumps({"type":"final","message":"trusted fixture done"}),flush=True)\n')
    config = {'schema_version': 1, 'id': 'sequential-fixture', 'kind': 'harness_fixture',
        'runtime': {'image': 'sha256:'+'0'*64, 'memory': '1536m', 'cpus': 2},
        'driver': {'kind': 'command', 'argv': ['{python}', '{driver}/adapter.py'], 'env': []},
        'budget': {'max_seconds': 10, 'max_tool_calls': 3, 'command_seconds': 5},
        'substrate': {'paths': ['adapter.py'], 'instructions': 'No task recipe'}}
    (system / 'system.yaml').write_text(json.dumps(config))
    inputs = tmp_path / 'public'
    inputs.mkdir()
    (inputs / 'training.json').write_text('{"training": []}')

    class FakeBox:
        def __init__(self, image, work, *args, feedback, **kwargs):
            self.work, self.feedback = Path(work), feedback
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def inspect(self):
            return {'passed': True, 'fixture': True}
        def execute(self, command, timeout):
            assert command == 'trusted-fixture'
            (self.work / 'submission/forecast-program.json').write_text('{"argv":["python","forecast.py"]}')
            (self.work / 'submission/forecast.py').write_text('# trusted fixture\n')
            return {'exit_code': 0, 'stdout': '', 'stderr': ''}
        def score_development(self, prediction_file, timeout):
            return self.feedback.query(prediction_file, timeout)

    monkeypatch.setattr(ACTOR, 'preflight', lambda image: None)
    monkeypatch.setattr(ACTOR, 'ToolSandbox', FakeBox)
    episode = {'cases': [{'case_id': 'case'}]}
    evaluate = lambda *a, **k: {'state': 'pass', 'predictions': [[1.0]], 'events': []}
    score = lambda *a: {'rmse_mm': 1.0, 'raw_model_rmse_mm': 2.0}
    folder = tmp_path / 'run'
    result = ACTOR.launch_actor(system / 'system.yaml', inputs, 'Forecast rainfall.', episode, evaluate, score, folder)
    assert result['status'] == 'submitted' and result['tool_calls'] == 2
    assert json.loads((folder / 'controller/feedback-public.json').read_text())['requests'][0]['status'] == 'scored'
    assert (folder / 'frozen/forecast.py').read_text() == '# trusted fixture\n'
    assert not (folder / 'inputs/development.json').exists()


@pytest.mark.parametrize('drift,expected', [(0.0, 'pass'), (0.01, 'fail')])
def test_terminal_replay_distinguishes_valid_drifting_program(tmp_path, drift, expected):
    frozen = tmp_path / 'frozen'
    frozen.mkdir()
    (frozen / 'forecast-program.json').write_text('{"argv":["python","forecast.py"]}')
    (frozen / 'forecast.py').write_text('# trusted fixture\n')
    calls = []
    def evaluate(*args, **kwargs):
        calls.append(1)
        return {'state': 'pass', 'predictions': [[1.0 + (drift if len(calls) == 2 else 0.0)]],
                'events': [{'private_diagnostic': 'not in summary'}]}
    result = ACTOR.evaluate_final(frozen, 'forecast-program.json', {'cases': [{'case_id': 'a'}]},
        'image', evaluate, lambda *a: {'rmse_mm': 1.0}, tmp_path / 'controller')
    assert result['state'] == expected and len(calls) == 2
    assert result['final_score_exposed_to_actor'] is False
    assert 'private_diagnostic' not in json.dumps(result)
