"""A pre-driver infrastructure launch cannot satisfy the real-model trial gate."""
import json
import pytest
from types import SimpleNamespace
from assessment.certify import model_attempts


def test_environment_failures_do_not_unlock_model_trials_but_real_attempts_do(tmp_path, monkeypatch):
    import assessment.runner
    monkeypatch.setattr(assessment.runner, "RUNS", tmp_path)
    template = SimpleNamespace(name="task", fingerprint=lambda: "current")

    def add(name, failure=False, events=False):
        folder = tmp_path / name
        folder.mkdir()
        meta = {"id": name, "template": "task", "kind": "agent", "system": "system", "instance": {"id": "one"},
                "status": "execution_error" if failure else "submitted", "usage": None, "tool_calls": None}
        if failure:
            meta["reason"] = "ValueError: Missing controller environment variable: CODEX_BINARY"
        assessment = {"fingerprint": "current", "outcome": "fail" if failure else "pass",
                      "computed_outcome": "fail" if failure else "pass", "checks": {}}
        (folder / "run.json").write_text(json.dumps(meta))
        (folder / "assessment.json").write_text(json.dumps(assessment))
        if events:
            (folder / "logs").mkdir()
            (folder / "logs/events.jsonl").write_text('{"type":"adapter","event":{"type":"execute"}}\n')

    add("infra-a", failure=True)
    add("infra-b", failure=True)
    first = model_attempts(template)
    assert first["attempts"] == 0 and first["passed"] is None
    assert len(first["excluded_before_model_launch"]) == 2
    add("real-a")
    add("real-b")
    second = model_attempts(template)
    assert second["attempts"] == 2 and second["passed"] is True
    add("event-bearing-failure", failure=True, events=True)
    third = model_attempts(template)
    assert third["attempts"] == 3 and len(third["excluded_before_model_launch"]) == 2


def test_missing_driver_environment_is_rejected_before_runtime_or_run_creation(tmp_path, monkeypatch):
    import assessment.runner as runner
    key = "WEATHER_BENCH_TEST_REQUIRED_ENV"
    monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(runner, "RUNS", tmp_path)
    monkeypatch.setattr(runner, "resolve_system", lambda _: "unused")
    monkeypatch.setattr(runner, "validate", lambda _: {"driver": {"kind": "command", "env": [key]}})
    monkeypatch.setattr(runner, "preflight", lambda _: pytest.fail("Docker must not start before environment validation"))
    with pytest.raises(ValueError, match=key):
        runner.run(None, None, "test")
    assert list(tmp_path.iterdir()) == []


def test_invalid_brief_is_rejected_before_runtime_or_run_creation(tmp_path, monkeypatch):
    import assessment.runner as runner
    monkeypatch.setattr(runner, "RUNS", tmp_path)
    monkeypatch.setattr(runner, "resolve_system", lambda _: "unused")
    monkeypatch.setattr(runner, "validate", lambda _: {
        "driver": {"kind": "command", "env": []}, "runtime": {"image": "unused"}})
    monkeypatch.setattr(runner, "preflight", lambda _: pytest.fail("Docker must not start before brief validation"))

    def broken_brief(*_):
        raise IndexError("Replacement index 0 out of range")

    template = SimpleNamespace(spec={}, brief=broken_brief)
    with pytest.raises(ValueError, match="Task brief could not be rendered"):
        runner.run(template, {}, "test")
    assert list(tmp_path.iterdir()) == []
