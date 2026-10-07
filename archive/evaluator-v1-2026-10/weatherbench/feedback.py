"""Bounded development-score queries; final targets never enter this interface."""
import hashlib
import json
import os
import re
import stat
import time
from pathlib import Path


SCORE_TOOL = {
    'type': 'function', 'name': 'score_development',
    'description': 'Score a prediction NetCDF in /work/submission on development cases. '
                   'Each request consumes one of the task feedback submissions, including errors. '
                   'Final-test scores and observations are unavailable.',
    'inputSchema': {'type': 'object', 'properties': {'prediction_file': {'type': 'string'}},
                    'required': ['prediction_file'], 'additionalProperties': False},
}


def read_submission(work, filename, limit):
    """Read a regular file through directory descriptors, never following symlinks."""
    if not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.nc', filename):
        raise ValueError('Use a NetCDF basename in /work/submission, without directories')
    descriptors = []
    try:
        parent = os.open(work, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(parent)
        parent = os.open('submission', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        descriptors.append(parent)
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        descriptors.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= limit:
            raise ValueError('Prediction must be a nonempty regular file within the declared size limit')
        data = bytearray()
        while len(data) <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        after = os.fstat(fd)
        if len(data) > limit or len(data) != before.st_size or before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
            raise ValueError('Prediction changed while being copied; finish writing before scoring')
        return bytes(data)
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


class DevelopmentFeedback:
    def __init__(self, work, controller, score, max_submissions=5, max_file_bytes=33554432):
        if type(max_submissions) is not int or not 1 <= max_submissions <= 100:
            raise ValueError('Invalid feedback submission limit')
        if type(max_file_bytes) is not int or not 1 <= max_file_bytes <= 33554432:
            raise ValueError('Invalid feedback file size limit')
        self.work, self.controller = Path(work), Path(controller)
        self.controller.mkdir(parents=True, exist_ok=False)
        self.score, self.limit, self.file_limit = score, max_submissions, max_file_bytes
        self.attempts, self.denials = [], 0
        self.finish()

    def finish(self):
        record = {'schema_version': 1, 'scope': 'development_only', 'max_submissions': self.limit,
                  'attempts': self.attempts, 'limit_denials': self.denials,
                  'final_score_exposed': False, 'final_observations_exposed': False}
        (self.controller / 'ledger.json').write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
        return record

    def public_summary(self):
        fields = ('query', 'prediction_file', 'status', 'prediction_sha256', 'bytes', 'metrics', 'seconds', 'error_type')
        return {'scope': 'development_only', 'max_submissions': self.limit,
                'requests': [{key: row[key] for key in fields if key in row} for row in self.attempts],
                'limit_denials': self.denials, 'final_score_exposed': False, 'final_observations_exposed': False}

    def query(self, prediction_file, timeout=60):
        started = time.monotonic()
        if len(self.attempts) >= self.limit:
            self.denials += 1
            self.finish()
            return {'exit_code': 1, 'stdout': '', 'stderr': 'Development feedback submission limit reached',
                    'feedback_scope': 'development_only', 'feedback_remaining': 0}
        index = len(self.attempts) + 1
        row = {'query': index, 'prediction_file': prediction_file, 'status': 'reserved'}
        self.attempts.append(row)
        self.finish()
        try:
            data = read_submission(self.work, prediction_file, self.file_limit)
            snapshot = self.controller / f'prediction-{index:03d}.nc'
            with snapshot.open('xb') as stream:
                stream.write(data)
            row.update(prediction_sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), snapshot=snapshot.name)
            metrics = self.score(snapshot)
            if not isinstance(metrics, dict) or not metrics:
                raise ValueError('The development scorer returned an invalid response')
            encoded = json.dumps(metrics, allow_nan=False)
            if len(encoded) > 8000:
                raise ValueError('Development feedback exceeds its aggregate response bound')
            if time.monotonic() - started > timeout:
                raise TimeoutError('Development feedback deadline')
            row.update(status='scored', metrics=metrics)
            result = {'exit_code': 0, 'stdout': encoded, 'stderr': '',
                      'prediction_sha256': row['prediction_sha256']}
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
            row.update(status='failed', error_type=type(error).__name__, private_error=str(error)[:1500])
            # Private scorer exceptions can contain target values or host paths.
            result = {'exit_code': 1, 'stdout': '',
                      'stderr': f'Development prediction could not be scored ({type(error).__name__}); check the published format and file limit'}
        row['seconds'] = time.monotonic() - started
        self.finish()
        result.update(seconds=row['seconds'], feedback_scope='development_only',
                      feedback_query=index, feedback_remaining=self.limit - index)
        return result
