"""Controller-owned chronological forecast execution. Private truth is never mounted.

Programs run only in Docker. One process persists across issues; the controller
releases completed observations and accepts one immutable forecast per issue.
"""
from datetime import date, timedelta
import json
import math
import os
from pathlib import Path
import selectors
import subprocess
import tempfile
import time
import uuid

from .storage import inventory


def _day(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError('Dates must use YYYY-MM-DD')
    return parsed


def _vector(value, size):
    if (not isinstance(value, list) or len(value) != size
        or any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in value)):
        raise ValueError('Expected a finite nonnegative vector covering every location')
    return [float(x) for x in value]


def validate_episode(episode):
    locations = episode['locations']
    if not locations or len({row['id'] for row in locations}) != len(locations):
        raise ValueError('Locations must be nonempty and unique')
    for row in locations:
        if not all(math.isfinite(row[key]) for key in ('latitude', 'longitude')):
            raise ValueError('Location coordinates must be finite')
        if not -90 <= row['latitude'] <= 90:
            raise ValueError('Invalid latitude')
    cases = episode['cases']
    if not cases:
        raise ValueError('An episode needs forecast cases')
    first = _day(cases[0]['issue_time'])
    identifiers = set()
    for group in ('training', 'pending', 'cases'):
        previous = None
        for row in episode[group]:
            issue, target, release = (_day(row[key]) for key in ('issue_time', 'target_start', 'release_time'))
            if target != issue + timedelta(days=14) or release != issue + timedelta(days=35):
                raise ValueError('Targets start at issue+14d and observations release at issue+35d')
            if previous is not None and issue <= previous:
                raise ValueError('Cases must be strictly chronological within each group')
            previous = issue
            if not isinstance(row['case_id'], str) or row['case_id'] in identifiers:
                raise ValueError('Case identifiers must be unique strings')
            identifiers.add(row['case_id'])
            _vector(row['raw_mm'], len(locations))
            _vector(row['observed_mm'], len(locations))
            if group == 'training' and (issue >= first or release > first):
                raise ValueError('Training observations must already be released')
            if group == 'pending' and (issue >= first or release <= first):
                raise ValueError('Pending observations must be past issues not yet released')
    return episode


def messages(episode):
    """Only past, released labels reach the program; current truth stays private."""
    validate_episode(episode)
    # JSON roundtrip prevents a consumer from mutating controller-owned truth.
    clone = lambda value: json.loads(json.dumps(value, allow_nan=False))
    yield {'type': 'initialize', 'locations': clone(episode['locations']),
           'training': clone(episode['training'])}
    waiting = list(episode['pending'])
    for row in episode['cases']:
        released = sorted((r for r in waiting if r['release_time'] <= row['issue_time']),
                          key=lambda r: (r['release_time'], r['case_id']))
        released_ids = {r['case_id'] for r in released}
        waiting = [r for r in waiting if r['case_id'] not in released_ids]
        yield {'type': 'forecast', 'case_id': row['case_id'], 'issue_time': row['issue_time'],
               'target_start': row['target_start'], 'raw_mm': clone(row['raw_mm']),
               'released_observations': clone(released)}
        waiting.append(row)


def validate_prediction(response, message, size):
    if not isinstance(response, dict) or set(response) != {'case_id', 'prediction_mm'}:
        raise ValueError('Reply must contain exactly case_id and prediction_mm')
    if response['case_id'] != message['case_id']:
        raise ValueError('Prediction must name the current case_id')
    return _vector(response['prediction_mm'], size)


def build_command(submission, argv, image, name, memory='1536m', cpus=2):
    inventory(Path(submission))  # Reject root links as well as links inside the bundle.
    submission = Path(submission).resolve()
    if (not isinstance(argv, list) or not argv or argv[0] not in ('python', 'python3')
        or not all(isinstance(arg, str) and arg for arg in argv)):
        raise ValueError('Declare Python argv as nonempty strings')
    if not image.startswith('sha256:') or len(image) != 71:
        raise ValueError('Pin the Docker image by content ID')
    return ['docker', 'run', '--rm', '-i', '--name', name, '--network', 'none',
            '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--pids-limit', '128', '--memory', memory, '--cpus', str(cpus),
            '--user', '65534:65534', '--workdir', '/submission',
            '--mount', f'type=bind,source={submission},target=/submission,readonly',
            '--tmpfs', '/state:rw,nosuid,nodev,size=256m,mode=1777',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m,mode=1777',
            *sum((['--env', f'{key}=1'] for key in
                  ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')), []),
            '--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', argv[0], image, *argv[1:]]


def evaluate(submission, argv, episode, image, seconds=120, step_seconds=5):
    """Return immutable predictions and controller trace; never execute host actor code."""
    validate_episode(episode)
    name = 'weather-sequential-' + uuid.uuid4().hex
    command = build_command(submission, argv, image, name)
    started = time.monotonic()
    result = {'state': 'fail', 'predictions': [], 'events': [], 'reason': None,
              'runtime_image': image, 'private_truth_mounted': False}
    process, selector = None, selectors.DefaultSelector()
    buffer = bytearray()
    with tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
            os.set_blocking(process.stdin.fileno(), False)
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)

            def send(payload, deadline):
                data = memoryview((json.dumps(payload, allow_nan=False) + '\n').encode())
                selector.register(process.stdin, selectors.EVENT_WRITE)
                try:
                    while data:
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Program did not consume input before deadline')
                        for key, _ in selector.select(min(.1, max(0, deadline-time.monotonic()))):
                            if key.fileobj is process.stdin:
                                count = os.write(process.stdin.fileno(), data[:65536])
                                data = data[count:]
                            else:
                                chunk = os.read(process.stdout.fileno(), 65536)
                                if chunk:
                                    buffer.extend(chunk)
                                    if len(buffer) > 65536:
                                        raise ValueError('Program stdout exceeds one bounded response')
                                elif process.poll() is not None:
                                    raise ValueError('Program exited before consuming input')
                finally:
                    selector.unregister(process.stdin)

            def receive(deadline):
                while b'\n' not in buffer:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Program did not return its forecast before deadline')
                    if selector.select(min(.1, max(0, deadline-time.monotonic()))):
                        chunk = os.read(process.stdout.fileno(), 65536)
                        if not chunk:
                            raise ValueError('Program exited before returning a forecast')
                        buffer.extend(chunk)
                        if len(buffer) > 65536:
                            raise ValueError('Program stdout exceeds one bounded response')
                line, _, rest = buffer.partition(b'\n')
                buffer[:] = rest
                return json.loads(line)

            for message in messages(episode):
                deadline = min(started+seconds, time.monotonic()+step_seconds)
                # Initial import and fitting share the total episode budget;
                # subsequent online replies have the per-issue time limit.
                if message['type'] == 'initialize' or not result['predictions']:
                    deadline = started+seconds
                send(message, deadline)
                if message['type'] == 'initialize':
                    result['events'].append({'type': 'initialized', 'training_cases': len(message['training'])})
                    continue
                response = receive(deadline)
                prediction = validate_prediction(response, message, len(episode['locations']))
                result['predictions'].append(prediction)
                result['events'].append({'type': 'forecast', 'case_id': message['case_id'],
                    'issue_time': message['issue_time'],
                    'released_cases': [r['case_id'] for r in message['released_observations']],
                    'prediction_mm': prediction.copy()})
            process.stdin.close()
            remaining = max(.01, started+seconds-time.monotonic())
            process.wait(timeout=remaining)
            extra = bytes(buffer) + process.stdout.read()
            if extra.strip():
                raise ValueError('Program returned extra output after the final forecast')
            if process.returncode:
                if process.returncode == 125:
                    result['state'] = 'unresolved'
                raise ValueError(f'Program exited with status {process.returncode}')
            result['state'] = 'pass'
        except (ValueError, KeyError, TypeError, OSError, TimeoutError, subprocess.TimeoutExpired) as error:
            result['reason'] = f'{type(error).__name__}: {error}'
            if isinstance(error, FileNotFoundError) and error.filename == 'docker':
                result['state'] = 'unresolved'
        finally:
            selector.close()
            if process is not None:
                try:
                    subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=10, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    result['cleanup_incomplete'] = True
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                # A Docker launch failure normally occurs before any response,
                # so classification must also cover the early pipe-error path.
                if process.returncode == 125 and result['state'] != 'pass':
                    result['state'] = 'unresolved'
                process.stdout.close()
                if not process.stdin.closed:
                    process.stdin.close()
            errors.seek(0, os.SEEK_END)
            errors.seek(max(0, errors.tell()-8000))
            result['stderr'] = errors.read().decode(errors='replace')
    result['seconds'] = time.monotonic()-started
    return result
