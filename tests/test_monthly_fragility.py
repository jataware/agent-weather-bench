"""Agent-launch guards tested without Docker, models or scientific file reads."""
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / 'experiments/monthly_fragility.py'
SPEC = importlib.util.spec_from_file_location('monthly_fragility_test', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_real_pair_environment_and_adapter_differ_only_by_model_identity():
    systems = MODULE.check_systems()
    assert [value['model'] for value in systems.values()] == ['gpt-6-luna', 'gpt-6-astra']
    assert all(value['reasoning_effort'] == 'high' for value in systems.values())


def test_draft_plan_rejected_before_template_import_or_actor_call():
    with pytest.raises(ValueError, match='ready'):
        MODULE.validate({'status': 'draft', 'max_new_agent_attempts': 2, 'systems': {}})


def test_exactly_one_pair_and_consumed_plan_never_retries(tmp_path, monkeypatch):
    plan = tmp_path / 'plan.json'
    plan.write_text(json.dumps({'review_directory': 'run', 'systems': list(MODULE.SYSTEMS)}))
    monkeypatch.setattr(MODULE, 'ROOT', tmp_path)
    monkeypatch.setattr(MODULE, 'validate', lambda plan: None)
    calls = []
    def attempt(system, plan, digest):
        calls.append(system)
        return {'system': system, 'exit_code': 0}
    monkeypatch.setattr(MODULE, '_attempt', attempt)
    result = MODULE.run(plan)
    assert len(result) == 2 and sorted(calls) == sorted(MODULE.SYSTEMS)
    with pytest.raises(FileExistsError):
        MODULE.run(plan)
    assert len(calls) == 2


def test_private_source_drift_stops_before_actor_creation(tmp_path, monkeypatch):
    class Template:
        private = tmp_path / 'private'
        def __init__(self, name):
            pass
        def fingerprint(self):
            return 'frozen-fingerprint'
    Template.private.mkdir()
    (Template.private / 'source.json').write_text('{"unchanged":false}')
    monkeypatch.setattr(MODULE, 'Template', Template)
    plan = {'status': 'ready', 'max_new_agent_attempts': 2, 'systems': dict.fromkeys(MODULE.SYSTEMS),
            'template': 'fixture', 'fingerprint': 'frozen-fingerprint', 'private_source_manifest': {}}
    with pytest.raises(ValueError, match='private scientific data changed'):
        MODULE.validate(plan)


def test_curated_function_excerpt_in_public_manifest_rejected(tmp_path, monkeypatch):
    class Template:
        private = tmp_path / 'private'
        def __init__(self, name):
            pass
        def fingerprint(self):
            return 'frozen-fingerprint'
    Template.private.mkdir()
    monkeypatch.setattr(MODULE, 'Template', Template)
    plan = {'status': 'ready', 'max_new_agent_attempts': 2, 'systems': dict.fromkeys(MODULE.SYSTEMS),
            'template': 'fixture', 'fingerprint': 'frozen-fingerprint', 'private_source_manifest': {},
            'public_input_manifest': {'nested/africas2s-smoothed-method.py.txt': {'sha256': 'forbidden'}}}
    with pytest.raises(ValueError, match='curated function excerpt'):
        MODULE.validate(plan)
