"""Standalone actor integration for controller-owned chronological forecasting.

No normal assessment runner/scorer is changed. Native evaluation is delegated to
assessment.sequential; all development/final episode files stay controller-side.
Importing this module neither starts Docker nor invokes a model.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
import re
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment import adapters
from assessment.runtime import ToolSandbox, preflight
from assessment.storage import copy_bundle, digest, inventory, read, write
from assessment.systems import snapshot, validate


SCORE_TOOL = {
    'type': 'function', 'name': 'score_development',
    'description': 'Freeze the entire submission and evaluate its JSON program manifest on the development episode. '
                   'prediction_file names a JSON manifest in /work/submission, not a forecast array. '
                   'Every evaluator request counts, including invalid manifests/programs. Five requests are allowed. '
                   'Only aggregate development metrics return; final scores and unreleased observations are unavailable.',
    'inputSchema': {'type': 'object', 'properties': {'prediction_file': {'type': 'string'}},
                    'required': ['prediction_file'], 'additionalProperties': False},
}
PUBLIC_METRICS = {
    'rmse_mm', 'raw_model_rmse_mm', 'raw_rmse_mm', 'climatology_rmse_mm',
    'skill_vs_raw_model', 'skill_vs_climatology', 'cases', 'issues', 'cells',
}


def load_manifest(submission, name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.json', name):
        raise ValueError('Use a JSON manifest filename without directories')
    path = Path(submission) / name
    if path.is_symlink() or not path.is_file():
        raise ValueError('Manifest must be a regular file')
    if path.stat().st_size > 65536:
        raise ValueError('Manifest exceeds its size limit')
    value = json.loads(path.read_text())
    if (not isinstance(value, dict) or set(value) != {'argv'} or not isinstance(value['argv'], list)
        or not value['argv'] or not all(isinstance(arg, str) and arg.strip() for arg in value['argv'])):
        raise ValueError('Manifest must contain only a nonempty argv string array')
    return value['argv']


def normalize_predictions(episode, predictions):
    """Join positional evaluator output to declared cases, never to sorted dates."""
    if not isinstance(predictions, list) or len(predictions) != len(episode['cases']):
        raise ValueError('Evaluator prediction coverage mismatch')
    if predictions and isinstance(predictions[0], dict):
        return predictions
    return [{'case_id': case['case_id'], 'prediction_mm': row}
            for case, row in zip(episode['cases'], predictions)]


class ProgramFeedback:
    """ToolSandbox feedback protocol with immutable whole-program query snapshots."""
    def __init__(self, work, controller, episode, image, evaluate, score,
                 max_submissions=5, max_bundle_bytes=33554432, max_bundle_files=20000):
        self.work, self.controller = Path(work), Path(controller)
        self.controller.mkdir(parents=True, exist_ok=False)
        self.episode = episode
        self.image, self.evaluate, self.score = image, evaluate, score
        self.limit = max_submissions
        if type(self.limit) is not int or self.limit < 1:
            raise ValueError('Invalid development query limit')
        self.max_bundle_bytes, self.max_bundle_files = max_bundle_bytes, max_bundle_files
        self.attempts, self.denials = [], 0
        self.finish()

    def finish(self):
        value = {'schema_version': 1, 'scope': 'development_only', 'max_submissions': self.limit,
                 'attempts': self.attempts, 'limit_denials': self.denials,
                 'final_score_exposed': False, 'final_observations_exposed': False}
        write(self.controller / 'ledger.json', value)
        return value

    def public_summary(self):
        fields = ('query', 'prediction_file', 'status', 'files', 'bytes', 'bundle_sha256',
                  'metrics', 'seconds', 'error_type')
        return {'scope': 'development_only', 'max_submissions': self.limit,
                'limit_denials': self.denials, 'final_score_exposed': False,
                'final_observations_exposed': False,
                'requests': [{key: row[key] for key in fields if key in row} for row in self.attempts]}

    def query(self, prediction_file, timeout=120):
        if len(self.attempts) >= self.limit:
            self.denials += 1
            self.finish()
            return {'exit_code': 1, 'stdout': '', 'stderr': 'Development query limit reached',
                    'feedback_scope': 'development_only', 'feedback_remaining': 0}
        started = time.monotonic()
        index = len(self.attempts) + 1
        row = {'query': index, 'prediction_file': prediction_file, 'status': 'reserved'}
        self.attempts.append(row)
        self.finish()  # Count before parsing, copying, evaluating or scoring.
        try:
            source = self.work / 'submission'
            manifest = inventory(source)
            total = sum(item['bytes'] for item in manifest.values())
            if total > self.max_bundle_bytes or len(manifest) > self.max_bundle_files:
                raise ValueError('Program bundle exceeds the declared size limit')
            frozen = self.controller / f'query-{index:03d}' / 'frozen'
            frozen.parent.mkdir()
            frozen_manifest = copy_bundle(source, frozen)
            write(frozen.parent / 'artifacts.json', frozen_manifest)
            row.update(files=len(frozen_manifest), bytes=total,
                       bundle_sha256=digest(frozen.parent / 'artifacts.json'))
            argv = load_manifest(frozen, prediction_file)
            result = self.evaluate(frozen, argv, self.episode, self.image,
                                   seconds=min(float(timeout), 120), step_seconds=5)
            write(frozen.parent / 'evaluation.json', result)
            row['evaluation_sha256'] = digest(frozen.parent / 'evaluation.json')
            if inventory(frozen) != frozen_manifest:
                raise ValueError('Frozen development program changed during evaluation')
            if result.get('state') != 'pass':
                row['evaluation_state'] = result.get('state', 'unresolved')
                raise ValueError('Program evaluation did not pass')
            full_metrics = self.score(self.episode, normalize_predictions(self.episode, result['predictions']))
            write(frozen.parent / 'metrics.json', full_metrics)
            metrics = {key: value for key, value in full_metrics.items() if key in PUBLIC_METRICS}
            if ('rmse_mm' not in metrics or any(isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) for value in metrics.values())):
                raise ValueError('Development metric contract mismatch')
            row.update(status='scored', metrics=metrics)
            result = {'exit_code': 0, 'stdout': json.dumps(metrics, allow_nan=False), 'stderr': ''}
        except Exception as error:
            # Private evaluator reasons/events can contain observations. Never return them.
            row.update(status='failed', error_type=type(error).__name__, private_error=str(error)[:1500])
            result = {'exit_code': 1, 'stdout': '',
                      'stderr': f'Development program could not be evaluated ({type(error).__name__}); check the program contract'}
        row['seconds'] = time.monotonic() - started
        self.finish()
        result.update(seconds=row['seconds'], feedback_scope='development_only',
                      feedback_query=index, feedback_remaining=self.limit - index)
        return result


def launch_actor(system, public_inputs, brief, development_episode, evaluate, score, folder):
    """One actual actor call; caller must first freeze a reviewed readiness plan."""
    system, public_inputs, folder = Path(system), Path(public_inputs), Path(folder)
    config = validate(system)
    preflight(config['runtime']['image'])
    folder.mkdir(parents=True, exist_ok=False)
    config, bundle = snapshot(system, folder / 'system')
    write(folder / 'system.json', config)
    write(folder / 'substrate-manifest.json', bundle)
    inputs_manifest = copy_bundle(public_inputs, folder / 'inputs')
    write(folder / 'input-manifest.json', inputs_manifest)
    for path in ('task', 'work/submission', 'work/state', 'work/prior', 'logs', 'controller'):
        (folder / path).mkdir(parents=True, exist_ok=True)
    (folder / 'task/brief.md').write_text(brief)
    request = {'schema_version': 1, 'type': 'start', 'task': 'weekly-updating-rainfall', 'prompt': brief,
               'paths': {'work': '/work', 'inputs': '/work/inputs', 'submission': '/work/submission',
                         'state': '/work/state', 'task': '/task', 'substrate': '/substrate'},
               'budget': config['budget'], 'substrate_instructions': config['substrate']['instructions'],
               'tools': [SCORE_TOOL], 'development_feedback': {'scope': 'development_only', 'max_submissions': 5},
               'protocol': 'execute / score_development / tool_result / usage / final as JSON lines'}
    write(folder / 'request.json', request)
    feedback = ProgramFeedback(folder / 'work', folder / 'controller/development-feedback',
                               development_episode, config['runtime']['image'], evaluate, score)
    record = {'schema_version': 1, 'system': config['id'], 'system_sha256': digest(system),
              'runtime_image': config['runtime']['image'], 'status': 'running',
              'started_at': datetime.now(timezone.utc).isoformat(), 'agent_retries': 0, 'direct_paid_api_usd': 0}
    write(folder / 'run.json', record)
    try:
        with ToolSandbox(config['runtime']['image'], folder / 'work', folder / 'task', folder / 'system',
                         folder / 'inputs', memory=config['runtime']['memory'], cpus=config['runtime']['cpus'],
                         feedback=feedback) as box:
            result = adapters.command_driver(config, folder / 'system', request, box,
                                             folder / 'logs/events.jsonl', folder / 'logs/driver.stderr')
            write(folder / 'controller/sandbox.json', box.inspect())
        record.update(result)
    except Exception as error:
        record.update(status='execution_error', private_error=f'{type(error).__name__}: {error}')
    finally:
        write(folder / 'controller/feedback-public.json', feedback.public_summary())
        write(folder / 'artifacts.json', copy_bundle(folder / 'work/submission', folder / 'frozen'))
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        write(folder / 'run.json', record)
    return record


def evaluate_final(frozen, manifest_name, episode, image, evaluate, score, controller,
                   replay_atol_mm=1.0e-6):
    """Optional terminal evaluation/replay; never returns observations to an actor.

    The caller freezes the tolerance before inference. Full traces remain in the
    supplied private controller directory; the returned object holds aggregates.
    """
    frozen, controller = Path(frozen), Path(controller)
    controller.mkdir(parents=True, exist_ok=False)
    before = inventory(frozen)
    write(controller / 'artifacts.json', before)
    argv = load_manifest(frozen, manifest_name)
    results = []
    for name in ('final', 'replay'):
        result = evaluate(frozen, argv, episode, image, seconds=120, step_seconds=5)
        write(controller / f'{name}-evaluation.json', result)
        if inventory(frozen) != before:
            raise ValueError('Frozen final program changed during evaluation')
        results.append(result)
    record = {'state': 'unresolved' if any(r.get('state') == 'unresolved' for r in results) else 'fail',
              'runtime_image': image, 'bundle_sha256': digest(controller / 'artifacts.json'),
              'replay_atol_mm': replay_atol_mm,
              'trace_sha256': {name: digest(controller / f'{name}-evaluation.json') for name in ('final', 'replay')},
              'final_score_exposed_to_actor': False, 'private_truth_mounted': False}
    if all(result.get('state') == 'pass' for result in results):
        left, right = (normalize_predictions(episode, result['predictions']) for result in results)
        gap = max(abs(x-y) for a, b in zip(left, right)
                  for x, y in zip(a['prediction_mm'], b['prediction_mm']))
        record.update(state='pass' if gap <= replay_atol_mm else 'fail', replay_max_abs_mm=gap,
                      metrics=score(episode, left))
    write(controller / 'summary.json', record)
    return record


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def launch_plan(path):
    """Explicit CLI entry; a non-ready or changed contract never invokes an actor."""
    plan = read(path)
    if plan.get('status') != 'ready' or plan.get('max_new_agent_attempts') != 1:
        raise ValueError('A frozen, ready one-attempt plan is required')
    contract = plan.get('contract_files', {})
    if not contract:
        raise ValueError('Plan must freeze controller, source, brief, system and adapter hashes')
    for relative, expected in contract.items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f'Readiness contract changed: {relative}')
    from assessment.sequential import evaluate
    science = module(ROOT / plan['data_module'], 'sequential_forecast_data')
    return launch_actor(ROOT / plan['system'], ROOT / plan['public_inputs'],
                        (ROOT / plan['brief']).read_text(), read(ROOT / plan['development_episode']),
                        evaluate, science.score_predictions, ROOT / plan['run_directory'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--launch', action='store_true', required=True,
                        help='Actually launch one actor after the frozen readiness plan passes')
    args = parser.parse_args()
    print(json.dumps(launch_plan(args.plan), indent=2, allow_nan=False))
