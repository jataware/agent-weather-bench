"""Information boundaries, immutable score inputs and comparable feedback budgets."""
import json
import os
from pathlib import Path

import pytest

from weatherbench.feedback import DevelopmentFeedback, read_submission


def test_each_feedback_query_freezes_exact_bytes_and_limit_includes_errors(tmp_path):
    work = tmp_path / 'work'
    (work / 'submission').mkdir(parents=True)
    prediction = work / 'submission/development.nc'
    prediction.write_bytes(b'first prediction')
    seen = []
    def score(path):
        seen.append(path.read_bytes())
        return {'mean_score': len(seen) / 10}
    feedback = DevelopmentFeedback(work, tmp_path / 'controller', score, max_submissions=3)
    a = feedback.query('development.nc')
    prediction.write_bytes(b'second prediction')
    b = feedback.query('development.nc')
    failed = feedback.query('missing.nc')
    denied = feedback.query('development.nc')
    assert seen == [b'first prediction', b'second prediction']
    assert a['prediction_sha256'] != b['prediction_sha256']
    assert (a['feedback_remaining'], b['feedback_remaining'], failed['feedback_remaining']) == (2, 1, 0)
    assert denied['exit_code'] == 1 and len(seen) == 2
    ledger = json.loads((tmp_path / 'controller/ledger.json').read_text())
    assert [row['status'] for row in ledger['attempts']] == ['scored', 'scored', 'failed']
    assert ledger['limit_denials'] == 1 and ledger['final_score_exposed'] is False
    assert (tmp_path / 'controller/prediction-001.nc').read_bytes() == b'first prediction'


@pytest.mark.parametrize('filename', ['../private.nc', '/private.nc', 'nested/forecast.nc', '.hidden.nc', 'code.py'])
def test_feedback_cannot_select_files_outside_submission(tmp_path, filename):
    with pytest.raises(ValueError):
        read_submission(tmp_path, filename, 100)


def test_feedback_refuses_file_and_directory_symlinks_and_special_files(tmp_path):
    work = tmp_path / 'work'
    (work / 'submission').mkdir(parents=True)
    private = tmp_path / 'private'
    private.mkdir()
    (private / 'secret.nc').write_bytes(b'controller-only observations')
    (work / 'submission/link.nc').symlink_to(private / 'secret.nc')
    with pytest.raises(OSError):
        read_submission(work, 'link.nc', 100)
    os.mkfifo(work / 'submission/pipe.nc')
    with pytest.raises(ValueError):
        read_submission(work, 'pipe.nc', 100)
    (work / 'submission').rename(work / 'old')
    (work / 'submission').symlink_to(private)
    with pytest.raises(OSError):
        read_submission(work, 'secret.nc', 100)


def test_feedback_bounds_bytes_and_redacts_private_scorer_errors(tmp_path):
    work = tmp_path / 'work'
    (work / 'submission').mkdir(parents=True)
    (work / 'submission/large.nc').write_bytes(b'x' * 11)
    (work / 'submission/small.nc').write_bytes(b'x')
    secret = 'hidden final observation 24.123 and /private/host/path'
    def score(path):
        raise ValueError(secret)
    feedback = DevelopmentFeedback(work, tmp_path / 'controller', score, max_file_bytes=10)
    large = feedback.query('large.nc')
    small = feedback.query('small.nc')
    assert large['exit_code'] == small['exit_code'] == 1
    assert secret not in json.dumps(small) and '24.123' not in json.dumps(small)
    assert secret in (tmp_path / 'controller/ledger.json').read_text()
    public = json.dumps(feedback.public_summary())
    assert secret not in public and 'snapshot' not in public and 'private_error' not in public


@pytest.mark.parametrize('metrics', [{'score': float('nan')}, {'score': float('inf')}, [], {}])
def test_feedback_never_returns_invalid_aggregate_metrics(tmp_path, metrics):
    work = tmp_path / 'work'
    (work / 'submission').mkdir(parents=True)
    (work / 'submission/prediction.nc').write_bytes(b'x')
    feedback = DevelopmentFeedback(work, tmp_path / 'controller', lambda _: metrics)
    assert feedback.query('prediction.nc')['exit_code'] == 1
