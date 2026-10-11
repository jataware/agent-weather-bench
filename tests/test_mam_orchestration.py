"""Task-owned acquisition routing and evidence retention through public entrypoints."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("mam_acquisition_orchestration", ROOT / "templates/mam-multimodel-outlook/acquisition.py")
acquisition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acquisition)


def write_log(scratch):
    path = Path(scratch) / "probe-replay/acquisition/requests.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"method": "GET", "status": 200, "resource": "models/ecmwf.nc", "bytes": 71, "sha256": "pinned", "seconds": .01}) + "\n")


def test_cli_keeps_acquisition_evidence_before_temporary_work_cleanup(monkeypatch, tmp_path):
    import assessment.__main__ as cli
    import assessment.assess as assessing
    import assessment.rubric as rubric
    executor = object()
    template = SimpleNamespace(hooks=SimpleNamespace(executor_factory=lambda base: executor,
                              acquisition_evidence=acquisition.acquisition_evidence),
                              instance=lambda name: {"id": name})
    monkeypatch.setattr(cli, "Template", lambda name: template)
    def fake_assess(template, params, submission, routed_executor, scratch):
        assert routed_executor is executor
        write_log(scratch)
        return {"rubric": {}, "computed_outcome": "pass"}
    monkeypatch.setattr(assessing, "assess", fake_assess)
    monkeypatch.setattr(rubric, "markdown", lambda *a: "review")
    args = SimpleNamespace(command="assess", template="mam-multimodel-outlook", instance="test",
                           submission=str(tmp_path / "frozen"), control=None, local_trusted=False,
                           image="sha256:test", output=str(tmp_path / "kept"), judge=False, format="json")
    value = cli.dispatch(args)
    probe = value["acquisition"]["probes"][0]
    assert not Path(probe["original_log_path"]).exists()
    assert Path(probe["log_path"]).is_file()
    assert acquisition.digest(probe["log_path"]) == probe["log_sha256"]
    saved = json.loads((tmp_path / "kept/assessment.json").read_text())
    assert saved["acquisition"]["bytes"] == 71
    assert saved["computed_outcome"] == "pass"


def test_runner_keeps_evidence_before_work_cleanup_and_preserves_scientific_result(monkeypatch, tmp_path):
    import assessment.runner as runner
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    (frozen / "solve.py").write_text("# immutable submission\n")
    runner.write(tmp_path / "run.json", {"instance": {"id": "test"}})
    runner.write(tmp_path / "system.json", {"runtime": {"image": "sha256:test", "memory": "256m", "cpus": 1}})
    runner.write(tmp_path / "artifacts.json", runner.inventory(frozen))
    runner.write(tmp_path / "controller/provenance.json", {"sandbox": {"state": "pass"}})
    executor = object()
    template = SimpleNamespace(hooks=SimpleNamespace(executor_factory=lambda base: executor,
                              acquisition_evidence=acquisition.acquisition_evidence))
    def fake_assess(template, params, submission, routed_executor, scratch, **kwargs):
        assert routed_executor is executor
        write_log(scratch)
        return {"fingerprint": "a" * 64, "computed_outcome": "pass"}
    monkeypatch.setattr(runner, "assess", fake_assess)
    value = runner._assess_run(template, tmp_path, judge=False)
    probe = value["acquisition"]["probes"][0]
    assert Path(probe["log_path"]).is_file()
    assert not (tmp_path / "controller/assessment-work").exists()
    assert acquisition.digest(probe["log_path"]) == probe["log_sha256"]
    assert value["computed_outcome"] == "pass"
    assert json.loads((tmp_path / "assessment.json").read_text())["acquisition"] == value["acquisition"]


def test_real_task_factories_do_not_change_legacy_executor_routing():
    from assessment.__main__ import _executor
    from assessment.execute import Docker
    from assessment.spec import Template
    args = SimpleNamespace(local_trusted=False, image="sha256:test")
    wrapped = _executor(args, Template("mam-multimodel-outlook"))
    assert wrapped.name == "docker-snapshot-http"
    assert wrapped.image == "sha256:test"
    assert isinstance(_executor(args, Template("kenya-forecast-revision")), Docker)


def test_frozen_provider_excludes_target_observations_and_has_training_only_dates():
    from assessment.spec import Template
    template = Template("mam-multimodel-outlook")
    catalog_path = template.private / "provider/catalog.json"
    if not catalog_path.is_file():
        pytest.skip("Reviewed private source snapshot is not installed")
    resources = acquisition.provider_manifest(template.private / "provider")
    assert len(resources) == 7  # six payload resources and their catalogue
    assert "observations/chirps-monthly-pre2016.nc" in resources
    assert not any(path.startswith("private-targets/") or path == "observations/chirps-monthly-2016.nc" for path in resources)
    assert (template.private / "private-targets/chirps-monthly-2016.nc").is_file()
    # Serial native file I/O inside this fresh pytest process.
    import xarray as xr
    with xr.open_dataset(template.private / "provider/observations/chirps-monthly-pre2016.nc", engine="h5netcdf") as ds:
        assert set(ds.time.dt.year.values.tolist()) == set(range(1993, 2016))
    with xr.open_dataset(template.private / "private-targets/chirps-monthly-2016.nc", engine="h5netcdf") as ds:
        assert set(ds.time.dt.year.values.tolist()) == {2016}
