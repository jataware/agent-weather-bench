"""Disk is a hard budget: a run is refused under the floor, assessments run one at a time, scratch never outlives a crash,
and the inputs of an instance are staged once and hardlinked into each run."""
import json
import os
from types import SimpleNamespace

import pytest

import assessment.runner as runner


def test_the_gate_refuses_under_the_floor_and_reports_the_volume(monkeypatch):
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda path: SimpleNamespace(free=5e9))
    with pytest.raises(RuntimeError, match=r"Refusing to start a run: 5.0 GB free .* under the 12 GB floor"):
        runner.require_disk("start a run")
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda path: SimpleNamespace(free=40e9))
    assert runner.require_disk("start a run") == pytest.approx(40)
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda path: SimpleNamespace(free=8e9))
    assert runner.require_disk("assess a run", runner.MIN_FREE_GB_ASSESS) == pytest.approx(8)   # an assessment needs about 2 GB
    with pytest.raises(RuntimeError, match="under the 4 GB floor"):
        monkeypatch.setattr(runner.shutil, "disk_usage", lambda path: SimpleNamespace(free=3e9))
        runner.require_disk("assess a run", runner.MIN_FREE_GB_ASSESS)


def test_a_run_is_refused_before_any_folder_is_created(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda path: SimpleNamespace(free=1e9))
    monkeypatch.setattr(runner, "resolve_system", lambda system: tmp_path / "system.yaml")
    monkeypatch.setattr(runner, "validate", lambda path: {"driver": {"kind": "anthropic"}, "runtime": {"image": "sha256:x"}, "id": "s", "kind": "agent"})
    template = SimpleNamespace(name="objective-seasonal-outlook", spec={"spec_version": 2, "mode": "m"}, brief=lambda *a, **k: "brief")
    with pytest.raises(RuntimeError, match="Refusing to start a run"):
        runner.run(template, {"id": "one"}, "s")
    assert not (tmp_path / "runs").exists()


def test_assessment_scratch_is_removed_even_when_the_assessment_dies(monkeypatch, tmp_path):
    frozen = tmp_path / "frozen"; frozen.mkdir(); (frozen / "run.py").write_text("print()\n")
    runner.write(tmp_path / "run.json", {"instance": {"id": "one"}})
    runner.write(tmp_path / "system.json", {"runtime": {"image": "sha256:x", "memory": "1g", "cpus": 1}, "budget": {"command_seconds": 30}})
    runner.write(tmp_path / "artifacts.json", runner.inventory(frozen))
    runner.write(tmp_path / "controller/provenance.json", {"sandbox": {"state": "pass"}})
    monkeypatch.setattr(runner, "Docker", lambda *a, **k: object())
    monkeypatch.setattr(runner, "ASSESSMENT_LOCK", tmp_path / "lock")
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda path: SimpleNamespace(free=50e9))
    def dying_assess(template, params, submission, executor, scratch, **kwargs):
        scratch.mkdir(parents=True); (scratch / "big.bin").write_bytes(b"x" * 1024)
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(runner, "assess", dying_assess)
    template = SimpleNamespace(hooks=SimpleNamespace())
    with pytest.raises(OSError):
        runner._assess_run(template, tmp_path, judge=False)
    assert not (tmp_path / "controller/assessment-work").exists()
    assert (tmp_path / "lock").exists()


def test_inputs_are_staged_once_and_hardlinked_then_restaged_when_the_cache_changes(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "INPUTS_CACHE", tmp_path / "cache")
    private = tmp_path / "private"; private.mkdir(); (private / "provider.bin").write_bytes(b"snapshot")
    staged = []
    def stage_inputs(private_root, params, destination):
        destination.mkdir(parents=True); (destination / "instance.json").write_text(json.dumps(params)); (destination / "data.nc").write_bytes(b"d" * 100)
        staged.append(destination)
    template = SimpleNamespace(name="t", private=private, hooks=SimpleNamespace(stage_inputs=stage_inputs))
    first = runner.staged_inputs(template, {"id": "one"}, tmp_path / "run1/inputs")
    second = runner.staged_inputs(template, {"id": "one"}, tmp_path / "run2/inputs")
    assert len(staged) == 1 and first["reused"] is False and second["reused"] is True
    assert os.stat(tmp_path / "run1/inputs/data.nc").st_ino == os.stat(tmp_path / "run2/inputs/data.nc").st_ino
    assert runner.inventory(tmp_path / "run1/inputs") == runner.inventory(tmp_path / "run2/inputs")
    cache = tmp_path / "cache" / "t" / "one"
    (next(cache.glob("*/data.nc"))).write_bytes(b"corrupted")            # a damaged cache is re-staged, never reused
    third = runner.staged_inputs(template, {"id": "one"}, tmp_path / "run3/inputs")
    assert len(staged) == 2 and third["reused"] is False
    assert (tmp_path / "run3/inputs/data.nc").read_bytes() == b"d" * 100
    (private / "provider.bin").write_bytes(b"new snapshot")               # a new private snapshot is a new cache key
    runner.staged_inputs(template, {"id": "one"}, tmp_path / "run4/inputs")
    assert len(staged) == 3


def test_a_rung_edit_never_writes_through_a_hardlinked_practice_sheet(tmp_path):
    """The cut practice sheet replaces the run's link; the cache file keeps the published text."""
    cache = tmp_path / "cache/public"; cache.mkdir(parents=True)
    (cache / "practice.md").write_text("## Inputs\nx\n## Stream 1: WVG\ny\n")
    run_inputs = tmp_path / "run/inputs/public"; run_inputs.mkdir(parents=True)
    os.link(cache / "practice.md", run_inputs / "practice.md")
    from assessment.directions import drop_sections
    practice_path = run_inputs / "practice.md"
    practice = drop_sections(practice_path.read_text(), ["Stream 1: WVG"])
    practice_path.unlink(); practice_path.write_text(practice)          # what the runner does
    assert (cache / "practice.md").read_text() == "## Inputs\nx\n## Stream 1: WVG\ny\n"
    assert practice_path.read_text() == "## Inputs\nx\n"
