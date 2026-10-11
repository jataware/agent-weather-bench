"""Snapshot acquisition tests use plain bytes, never native scientific I/O."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("mam_snapshot_acquisition", ROOT / "templates/mam-multimodel-outlook/acquisition.py")
acquisition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acquisition)


def snapshot(tmp_path, payload=b"first-provider-bytes"):
    inputs = tmp_path / "inputs"
    public, provider = inputs / "public", inputs / "provider"
    public.mkdir(parents=True)
    (provider / "models").mkdir(parents=True)
    (public / "acquisition.json").write_text(json.dumps({"base_url": acquisition.BASE_URL, "catalog_path": "catalog.json"}))
    (public / "instance.json").write_text('{"instance_id":"test"}')
    raw = provider / "models/model.nc"
    raw.write_bytes(payload)
    (provider / "catalog.json").write_text(json.dumps({"resources": [{"path": "models/model.nc", "sha256": acquisition.digest(raw), "bytes": len(payload)}]}))
    (provider / "private-target.nc").write_bytes(b"DO NOT SERVE")
    return inputs


def test_http_allowlist_delivery_headers_and_private_evidence(tmp_path):
    inputs = snapshot(tmp_path)
    logs = tmp_path / "controller-logs"
    with acquisition.LocalProvider(inputs / "provider", logs) as server:
        response = urllib.request.urlopen(server.base_url + "/models/model.nc", timeout=3)
        assert response.read() == b"first-provider-bytes"
        assert response.headers["X-Content-SHA256"] == acquisition.digest(inputs / "provider/models/model.nc")
        assert response.headers["Cache-Control"] == "no-store"
        urllib.request.urlopen(urllib.request.Request(server.base_url + "/models/model.nc", method="HEAD"), timeout=3).read()
        for path in ("private-target.nc", "../private-target.nc", "%2e%2e/private-target.nc", "models%2f..%2fprivate-target.nc", "catalog.json?escape=1"):
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(server.base_url + "/" + path, timeout=3)
            assert error.value.code == 404
    record = acquisition.summarize(logs)
    assert record["bytes"] == len(b"first-provider-bytes")
    assert record["retrieved_resources"] == ["models/model.nc"]
    assert record["provider_download_bytes"] == 0
    assert len(record["requests"]) == 7
    assert acquisition.digest(logs / "requests.jsonl") == record["log_sha256"]
    assert server.process.poll() is not None


def test_provider_rejects_symlink_and_unpinned_changes(tmp_path):
    inputs = snapshot(tmp_path)
    raw = inputs / "provider/models/model.nc"
    raw.write_bytes(b"changed")
    with pytest.raises(ValueError, match="differs"):
        acquisition.provider_manifest(inputs / "provider")
    raw.unlink()
    raw.symlink_to(inputs / "provider/private-target.nc")
    with pytest.raises(ValueError, match="symlink"):
        acquisition.provider_manifest(inputs / "provider")
    for relative in ("/etc/passwd", "../outside", "models/../model.nc", "models//model.nc", "models/./model.nc"):
        with pytest.raises(ValueError):
            acquisition.plain_file(inputs / "provider", relative)


def test_local_replays_reacquire_changed_provider_and_stage_public_only(tmp_path):
    inputs = snapshot(tmp_path)
    submission = tmp_path / "submission"
    submission.mkdir()
    # Pretend a frozen submission retains an acquired old cache. Every replay
    # must nevertheless fetch the current server bytes through its descriptor.
    (submission / "old-cache.nc").write_bytes(b"first-provider-bytes")
    (submission / "solve.py").write_text('''import json,sys,urllib.request
from pathlib import Path
inputs,out=map(Path,sys.argv[1:])
assert not (inputs/'provider').exists()
assert not (inputs/'models').exists()
a=json.loads((inputs/'acquisition.json').read_text())
c=json.load(urllib.request.urlopen(a['base_url']+'/'+a['catalog_path']))
b=urllib.request.urlopen(a['base_url']+'/'+c['resources'][0]['path']).read()
(out/'answer.json').write_text(json.dumps({'payload':b.decode()}))
''')
    executor = acquisition.AcquisitionLocal()
    argv = ["python", "solve.py", "{input_dir}", "{output_dir}"]
    first = executor.run(submission, inputs, argv, tmp_path / "replay-first")
    assert first["exit_code"] == 0, first
    assert first["answer"] == {"payload": "first-provider-bytes"}
    raw = inputs / "provider/models/model.nc"
    raw.write_bytes(b"perturbed-provider")
    catalog = {"resources": [{"path": "models/model.nc", "sha256": acquisition.digest(raw), "bytes": raw.stat().st_size}]}
    (inputs / "provider/catalog.json").write_text(json.dumps(catalog))
    second = executor.run(submission, inputs, argv, tmp_path / "replay-second")
    assert second["exit_code"] == 0, second
    assert second["answer"] == {"payload": "perturbed-provider"}
    assert second["acquisition"]["retrieved_resources"] == ["catalog.json", "models/model.nc"]
    assert first["acquisition"]["log_path"] != second["acquisition"]["log_path"]
    assert json.loads((inputs / "public/acquisition.json").read_text())["base_url"] == acquisition.BASE_URL
    assert not (tmp_path / "replay-second/stage/_controller_inputs/provider").exists()


def container_config():
    return {"Image": "sha256:test", "HostConfig": {"NetworkMode": "testnet", "ReadonlyRootfs": True,
             "Privileged": False, "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges"],
             "Memory": 1000, "PidsLimit": 32}, "Config": {"User": "501:20"},
            "NetworkSettings": {"Networks": {"testnet": {}}},
            "Mounts": [{"Type": "bind", "Source": "/public", "Destination": "/work/inputs", "RW": False}]}


@pytest.mark.parametrize("violation", ["private-mount", "network", "root", "ports", "hosts", "writable", "privileged", "capabilities", "newprivileges"])
def test_boundary_rejects_private_mounts_and_escape_routes(monkeypatch, violation):
    from assessment.runtime import InfrastructureUnavailable
    config = container_config()
    acquisition.inspect_container  # Keep test tied to actual validator, not command text.
    if violation == "private-mount":
        config["Mounts"].append({"Type": "bind", "Source": "/provider", "Destination": "/provider", "RW": False})
    elif violation == "network":
        config["NetworkSettings"]["Networks"]["bridge"] = {}
    elif violation == "root":
        config["Config"]["User"] = "root"
    elif violation == "ports":
        config["HostConfig"]["PortBindings"] = {"8000/tcp": [{"HostPort": "8000"}]}
    elif violation == "hosts":
        config["HostConfig"]["ExtraHosts"] = ["host.docker.internal:host-gateway"]
    elif violation == "writable":
        config["Mounts"][0]["RW"] = True
    elif violation == "privileged":
        config["HostConfig"]["Privileged"] = True
    elif violation == "capabilities":
        config["HostConfig"]["CapDrop"] = []
    elif violation == "newprivileges":
        config["HostConfig"]["SecurityOpt"] = []
    monkeypatch.setattr(acquisition, "_docker", lambda *a, **k: SimpleNamespace(stdout=json.dumps([config])))
    with pytest.raises(InfrastructureUnavailable, match="boundary"):
        acquisition.inspect_container("actor", "sha256:test", "testnet", [("/public", "/work/inputs", False)])


def test_internal_bridge_without_isolated_gateway_is_rejected(monkeypatch, tmp_path):
    from assessment.runtime import InfrastructureUnavailable
    gateway = acquisition.DockerProvider("sha256:test", tmp_path, tmp_path / "logs")
    config = {"Internal": True, "Driver": "bridge", "Options": {}, "Containers": {"id": {"Name": gateway.name}}}
    monkeypatch.setattr(acquisition, "_docker", lambda *a, **k: SimpleNamespace(stdout=json.dumps([config])))
    with pytest.raises(InfrastructureUnavailable, match="isolated"):
        gateway.inspect_network({gateway.name})
    config["Options"]["com.docker.network.bridge.gateway_mode_ipv4"] = "isolated"
    gateway.inspect_network({gateway.name})
    config["Containers"]["foreign"] = {"Name": "unrelated-container"}
    with pytest.raises(InfrastructureUnavailable, match="isolated"):
        gateway.inspect_network({gateway.name})


def test_factories_preserve_standard_executor_parameters():
    from assessment.execute import Docker, Local
    assert isinstance(acquisition.executor_factory(Local()), acquisition.AcquisitionLocal)
    wrapped = acquisition.executor_factory(Docker("sha256:test", memory="2g", cpus=1))
    assert (wrapped.image, wrapped.memory, wrapped.cpus) == ("sha256:test", "2g", 1)
    assert acquisition.executor_factory(wrapped) is wrapped


@pytest.mark.skipif(__import__('os').environ.get('WEATHER_BENCH_SNAPSHOT_DOCKER_TEST') != '1', reason='explicit Docker integration opt-in')
def test_actual_docker_snapshot_actor_and_fresh_replay_isolation(tmp_path):
    import shlex
    inputs = snapshot(tmp_path)
    work, task, substrate = tmp_path / "work", tmp_path / "task", tmp_path / "system"
    task.mkdir(); substrate.mkdir()
    image = "sha256:cfbde79dea2813f21e192e9671a56f7de77ccc1c768d378675850ca3569b837a"
    probe = '''import json,socket,urllib.request
from pathlib import Path
assert not Path('/provider').exists()
a=json.loads(Path('/work/inputs/acquisition.json').read_text())
b=urllib.request.urlopen(a['base_url']+'/models/model.nc',timeout=3).read()
blocked={}
for host in ['1.1.1.1','host.docker.internal']:
 try:
  s=socket.create_connection((host,80),timeout=1);s.close();blocked[host]=False
 except OSError: blocked[host]=True
assert all(blocked.values()),blocked
print(json.dumps({'payload':b.decode(),'blocked':blocked}))
'''
    with acquisition.AcquisitionToolSandbox(image, work, task, substrate, inputs, memory="256m", cpus=1) as box:
        result = box.execute("python -I -S -c " + shlex.quote(probe), 10)
        assert result["exit_code"] == 0, result
        final = box.inspect()
        assert final["passed"]
        assert final["acquisition"]["retrieved_resources"] == ["models/model.nc"]
        assert str(inputs / "provider") not in json.dumps(final["mounts"])
        network, actor, provider = box.gateway.network, box.name, box.gateway.name
    assert acquisition._docker("network", "inspect", network, check=False).returncode != 0
    for name in (actor, provider):
        assert acquisition._docker("inspect", name, check=False).returncode != 0
    submission = tmp_path / "submission"
    submission.mkdir()
    (submission / "solve.py").write_text('''import json,sys,urllib.request
from pathlib import Path
inputs,out=map(Path,sys.argv[1:])
a=json.loads((inputs/'acquisition.json').read_text())
b=urllib.request.urlopen(a['base_url']+'/models/model.nc',timeout=3).read()
(out/'answer.json').write_text(json.dumps({'payload':b.decode()}))
''')
    executor = acquisition.AcquisitionDocker(image, memory="256m", cpus=1)
    argv = ["python", "-I", "-S", "solve.py", "{input_dir}", "{output_dir}"]
    first = executor.run(submission, inputs, argv, tmp_path / "replay-first", seconds=20)
    assert first["exit_code"] == 0, first
    assert first["answer"]["payload"] == "first-provider-bytes"
    raw = inputs / "provider/models/model.nc"
    raw.write_bytes(b"changed-for-Docker-replay")
    (inputs / "provider/catalog.json").write_text(json.dumps({"resources": [{"path": "models/model.nc", "sha256": acquisition.digest(raw), "bytes": raw.stat().st_size}]}))
    second = executor.run(submission, inputs, argv, tmp_path / "replay-second", seconds=20)
    assert second["exit_code"] == 0, second
    assert second["answer"]["payload"] == "changed-for-Docker-replay"
    assert second["acquisition"]["retrieved_resources"] == ["models/model.nc"]
    assert second["acquisition"]["requests"][0]["sha256"] == acquisition.digest(raw)


def test_acquisition_evidence_survives_scratch_cleanup_ignores_agent_logs(tmp_path):
    import shutil
    scratch = tmp_path / "assessment-work"
    real = scratch / "probe-replay/acquisition"
    fake = scratch / "probe-replay/stage/probe-fake/acquisition"
    for path in (real, fake):
        path.mkdir(parents=True)
        (path / "requests.jsonl").write_text(json.dumps({"method": "GET", "status": 200, "resource": "models/model.nc", "sha256": "abc", "bytes": 19, "seconds": 0.1}) + "\n")
    evidence = acquisition.acquisition_evidence(scratch, tmp_path / "retained")
    assert evidence["probe_count"] == 1
    assert evidence["bytes"] == 19
    assert evidence["probes"][0]["probe"] == "replay"
    shutil.rmtree(scratch)
    log = Path(evidence["probes"][0]["log_path"])
    assert log.is_file()
    assert acquisition.digest(log) == evidence["probes"][0]["log_sha256"]
    assert evidence["probes"][0]["evidence_persisted"]
