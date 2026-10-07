"""Controller retrieval boundaries and accounting, without inference or providers."""
import json
import subprocess
from copy import deepcopy

import pytest

from weatherbench import acquisition, runtime
from weatherbench.acquisition import FrozenReplay, assess_acquisition
from weatherbench.storage import ROOT, digest, read, write


@pytest.fixture
def replay(tmp_path, monkeypatch):
    source = tmp_path / "native-sources"
    source.mkdir()
    plan_file = source / "source-plan.json"
    plan = read(ROOT / "tasks/seasonal-calibration/source-plan.json")
    plan_file.write_bytes((ROOT / "tasks/seasonal-calibration/source-plan.json").read_bytes())
    rows, observation_rows = [], []
    for index, url in enumerate(plan["sources"]):
        name = "forecast-native.nc" if index == 0 else f"observation-native-{index}.tif"
        file = source / name
        file.write_bytes(f"native provider bytes {index}".encode())
        row = {"url":url, "file":name, "sha256":digest(file), "bytes":file.stat().st_size,
               "format":"NetCDF" if index == 0 else "GeoTIFF", "units":"m s**-1" if index == 0 else "mm/month",
               "representation":"native_training_subset"}
        if index == 0:
            row["provider_request"] = plan["forecast"]["request"]
        else:
            observation_rows.append({"url":url, "provider_response_ranges":[], "source_pixel_window":{},
                                     "grid":{}, "mask":{}, "units_provenance":"native monthly totals"})
        rows.append(row)
    mapping = {"source_plan_sha256":digest(plan_file), "entries":rows, "provider_download_bytes_observations":1234}
    write(source / "frozen-replay-map.json", mapping)
    write(source / "observations-index.json", {"entries":observation_rows})
    monkeypatch.setattr(acquisition, "REVIEWED_MAP_SHA256", digest(source / "frozen-replay-map.json"))
    monkeypatch.setattr(acquisition, "REVIEWED_INDEX_SHA256", digest(source / "observations-index.json"))
    controller = tmp_path / "run/controller"
    box = FrozenReplay(plan_file, controller, source)
    return box, controller.parent, source, plan_file


def deliver(destination, data, expected, timeout):
    import hashlib
    assert hashlib.sha256(data).hexdigest() == expected
    return {"exit_code":0,"stdout":"native bytes delivered","stderr":"","transfer_bytes":len(data),"cache_hit":False}


def test_training_sources_acquired_with_native_units_and_trusted_accounting(replay):
    box, run, _, _ = replay
    for index, row in enumerate(box.mapping["entries"]):
        result = box.acquire(row["url"], f"/work/raw/{index}", row.get("provider_request"), deliver, 5)
        assert result["exit_code"] == 0
        assert result["acquisition"]["units"] == row["units"]
        assert result["acquisition"]["artifact_sha256"] == row["sha256"]
    summary = box.finish()
    assert summary["state"] == "pass" and len(summary["acquired_sources"]) == 37
    assert summary["provider_download_bytes_during_attempt"] == 0
    assert summary["source_preparation_provider_download_bytes"] == 1234
    assert summary["replay_transfer_bytes"] == sum(row["bytes"] for row in box.mapping["entries"])
    assert assess_acquisition(run)["state"] == "pass"


@pytest.mark.parametrize("destination", ["/private/leak", "/work/../private/leak", "/work/inputs/source", "relative", "/work"])
def test_unsafe_destinations_are_denied_before_native_bytes_are_read(replay, destination):
    box, _, _, _ = replay
    row = box.mapping["entries"][1]
    result = box.acquire(row["url"], destination, None, lambda *args:pytest.fail("unsafe transfer"), 5)
    assert result["exit_code"] == 1 and result["acquisition"]["status"] == "denied"
    assert box.finish()["denied_requests"] == 1


def test_forbidden_observation_url_and_expanded_forecast_request_are_denied(replay):
    box, _, _, _ = replay
    forecast = box.mapping["entries"][0]
    expanded = deepcopy(forecast["provider_request"])
    expanded["year"].append("2005")
    for url, request in [(forecast["url"],expanded), (box.mapping["entries"][1]["url"].replace("1993", "2005"),None)]:
        result = box.acquire(url, "/work/raw/source", request, lambda *args:pytest.fail("forbidden transfer"), 5)
        assert result["exit_code"] == 1
    assert box.finish()["acquired_sources"] == []


def test_changed_native_source_and_forged_log_are_detected(replay):
    box, run, _, _ = replay
    row = box.mapping["entries"][1]
    (box.sources / row["file"]).write_bytes(b"normalized substitute")
    result = box.acquire(row["url"], "/work/raw/source", None, lambda *args:pytest.fail("changed transfer"), 5)
    assert result["exit_code"] == 1 and "changed" in result["stderr"]
    box.finish()
    with box.events.open("a") as stream:
        stream.write(json.dumps({"status":"success"}) + "\n")
    assert assess_acquisition(run)["state"] == "unresolved"


def test_replay_cache_hit_is_distinct_from_provider_download_and_replay_transfer(replay):
    box, _, _, _ = replay
    row = box.mapping["entries"][1]
    result = box.acquire(row["url"], "/work/raw/source", None,
                         lambda *args:{"exit_code":0,"cache_hit":True,"transfer_bytes":0}, 5)
    assert result["exit_code"] == 0
    summary = box.finish()
    assert summary["replay_transfer_bytes"] == 0 and summary["agent_cache_hits"] == 1


def test_preflight_rejects_provider_snapshot_drift(replay):
    _, _, source, plan = replay
    (source / "forecast-native.nc").write_bytes(b"new provider response")
    with pytest.raises(ValueError, match="changed"):
        acquisition.preflight(plan, source)


def test_missing_docker_is_infrastructure_failure(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("docker unavailable")
    monkeypatch.setattr(runtime.subprocess, "run", missing)
    with pytest.raises(runtime.InfrastructureUnavailable):
        runtime.preflight("image")


@pytest.mark.parametrize("code,infrastructure", [(125,True),(126,False),(127,False),(1,False),(0,False)])
def test_container_start_failure_is_distinct_from_scientific_exit(tmp_path, monkeypatch, code, infrastructure):
    monkeypatch.setattr(runtime,"preflight",lambda image:None)
    monkeypatch.setattr(runtime,"docker",lambda *args,**kwargs:subprocess.CompletedProcess(args,code,"",""))
    result = runtime.offline("image",tmp_path,tmp_path / "output",["python","bad-solver.py"])
    assert result["infrastructure_unavailable"] is infrastructure


def test_native_transfer_parent_symlink_is_rejected_in_runtime(tmp_path):
    # Exercise the actual container transfer program against a temporary work
    # directory without Docker; retain its dirfd/no-follow operations unchanged.
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (work / "redirect").symlink_to(outside, target_is_directory=True)
    import hashlib
    script = runtime.NATIVE_TRANSFER.replace("os.open('/work',", f"os.open({str(work)!r},")
    result = subprocess.run(["python3","-c",script,"write","/work/redirect/leak",hashlib.sha256(b"native").hexdigest(),"6"],
                            input=b"native",capture_output=True)
    assert result.returncode != 0 and not (outside / "leak").exists()


def test_seasonal_runner_starts_with_source_plan_only_and_no_normalized_fixture(replay, monkeypatch):
    from weatherbench import runner, judge, adapters
    _, _, source, _ = replay
    monkeypatch.setattr(acquisition,"SOURCE_ROOT",source)
    target = source.parent / "runner-test"
    target.mkdir()
    config = {"id":"test-system","kind":"agent","driver":{"kind":"command"},
              "runtime":{"image":"test-image","memory":"4g","cpus":2},
              "budget":{"max_seconds":1,"max_tool_calls":1,"command_seconds":1}}
    monkeypatch.setattr(runner,"new_run",lambda *args:target)
    monkeypatch.setattr(runner,"resolve_system",lambda value:ROOT / "systems/codex-luna/system.yaml")
    monkeypatch.setattr(runner,"validate",lambda path:config)
    monkeypatch.setattr(runner,"reference_integrity",lambda task:None)
    monkeypatch.setattr(runner,"preflight",lambda image:None)
    launch_lock={'fingerprint':'test-launch-policy','files':{}}
    monkeypatch.setattr(judge,"verify_lock",lambda:launch_lock)
    monkeypatch.setattr(judge,"assess",lambda *args,**kwargs:None)
    def snapshot(path,destination):
        destination.mkdir()
        return config,{}
    monkeypatch.setattr(runner,"snapshot",snapshot)
    class Box:
        def __init__(self,image,work,task,substrate,inputs,**kwargs):
            self.inputs=inputs
            self.acquisition=kwargs["acquisition"]
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def inspect(self):return {"passed":True,"network":"none"}
    monkeypatch.setattr(runner,"ToolSandbox",Box)
    def driver(config,substrate,request,box,*args):
        assert sorted(path.name for path in box.inputs.iterdir()) == ["source-plan.json"]
        assert request["acquisition"]["mode"] == "frozen_replay"
        assert request["tools"] == [acquisition.ACQUIRE_TOOL]
        assert box.acquisition is not None
        return {"status":"submitted","tool_calls":0,"usage":None,"seconds":0}
    monkeypatch.setattr(adapters,"command_driver",driver)
    result = runner.run_task("seasonal-calibration","test-system",judge="none")
    assert json.loads((target/'controller/launch-lock.json').read_text())==launch_lock
    assert json.loads((target/'run.json').read_text())['launch_policy_fingerprint']==launch_lock['fingerprint']
    assert result["status"] == "submitted"
    assert sorted(read(target / "input-manifest.json")) == ["source-plan.json"]
