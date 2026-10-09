"""Task-owned HTTP transport for an immutable, training-only provider snapshot.

This is snapshot HTTP, not a live CDS client. Only the public descriptor mounts
in the actor. A fresh provider and private request log accompany every replay.
The server entrypoint deliberately imports no scientific libraries and runs
single-threaded, also when trusted controls execute on the controller.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import time
from urllib.parse import unquote, urlsplit
import uuid

BASE_URL = "http://weather-source:8000"
SCRIPT = Path(__file__).resolve()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def plain_file(root, relative):
    """Never resolve a source symlink or accept a non-canonical URL path."""
    path = PurePosixPath(relative)
    if not relative or path.is_absolute() or any(p in ("", ".", "..") for p in relative.split("/")) or "\\" in relative:
        raise ValueError("Non-canonical provider path")
    current = Path(root)
    if current.is_symlink():
        raise ValueError("Provider root is a symlink")
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Provider symlinks are forbidden")
    if not current.is_file():
        raise ValueError("Provider resource is not a plain file")
    return current


def provider_manifest(root):
    catalog = plain_file(root, "catalog.json")
    data = json.loads(catalog.read_text())
    rows = data["resources"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Provider must declare resources")
    resources = {"catalog.json": {"path": "catalog.json", "sha256": digest(catalog), "bytes": catalog.stat().st_size}}
    for row in rows:
        relative = row["path"]
        if relative in resources:
            raise ValueError("Duplicate provider resource")
        path = plain_file(root, relative)
        if (type(row["bytes"]) is not int or path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]):
            raise ValueError("Provider resource differs from catalog: " + relative)
        resources[relative] = {"path": relative, "sha256": row["sha256"], "bytes": row["bytes"]}
    return resources


def serve(provider, logs, host, port, ready=None):
    root, log_path = Path(provider), Path(logs)
    resources = provider_manifest(root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents a controller from accidentally reusing evidence.
    log_path.touch(exist_ok=False)

    class Handler(BaseHTTPRequestHandler):
        server_version = "WeatherSnapshot/1"

        def log_message(self, *_):
            pass

        def do_GET(self):
            self.respond(True)

        def do_HEAD(self):
            self.respond(False)

        def respond(self, body):
            started = time.monotonic()
            status, sent, relative, sha = 404, 0, None, None
            try:
                parsed = urlsplit(self.path)
                if parsed.path == "/_health" and not parsed.query and not parsed.fragment:
                    self.send_response(204); self.end_headers()
                    return
                decoded = unquote(parsed.path, errors="strict")
                relative = decoded[1:] if decoded.startswith("/") else decoded
                if parsed.query or parsed.fragment or parsed.scheme or parsed.netloc or relative not in resources:
                    raise ValueError("Resource not allowlisted")
                path = plain_file(root, relative)
                row = resources[relative]
                # Detect mutation after startup without loading scientific data.
                if path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]:
                    raise ValueError("Provider changed during delivery")
                sha, status = row["sha256"], 200
                self.send_response(status)
                self.send_header("Content-Length", str(row["bytes"]))
                self.send_header("Content-Type", "application/json" if relative.endswith(".json") else "application/octet-stream")
                self.send_header("X-Content-SHA256", sha)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if body:
                    with path.open("rb") as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b""):
                            self.wfile.write(block)
                            sent += len(block)
            except (ValueError, OSError, UnicodeError):
                if status != 200:
                    self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers()
                else:
                    status = 499
            finally:
                if relative is not None:
                    event = {"method": self.command, "resource": relative, "status": status,
                             "bytes": sent, "sha256": sha, "seconds": time.monotonic() - started,
                             "timestamp_unix": time.time()}
                    with log_path.open("a") as stream:
                        stream.write(json.dumps(event, allow_nan=False) + "\n")

    server = HTTPServer((host, port), Handler)
    server.timeout = 1
    if ready:
        Path(ready).write_text(json.dumps({"port": server.server_port}) + "\n")
    server.serve_forever()


def summarize(log_dir):
    path = Path(log_dir) / "requests.jsonl"
    if not path.is_file():
        return {"state": "unresolved", "reason": "Provider log unavailable", "log_path": str(path)}
    events = [json.loads(line) for line in path.read_text().splitlines()]
    successful = [e for e in events if e["method"] == "GET" and e["status"] == 200]
    return {"state": "recorded", "mode": "private-snapshot-http", "log_path": str(path),
            "log_sha256": digest(path), "requests": events, "bytes": sum(e["bytes"] for e in events),
            "seconds": sum(e["seconds"] for e in events),
            "retrieved_resources": sorted({e["resource"] for e in successful}),
            "provider_download_bytes": 0, "live_provider": False}


def acquisition_evidence(scratch, destination=None):
    """Retain controller-created probe logs before assessment scratch cleanup.

    Scan only direct probe acquisition directories, never agent stage/output
    trees. This diagnostic is independent of the scientific headline.
    Without a destination the returned events still preserve inline evidence.
    """
    scratch = Path(scratch)
    target = Path(destination) if destination is not None else None
    if target is not None:
        target.mkdir(parents=True, exist_ok=False)
    probes = []
    for path in sorted(scratch.glob("probe-*/acquisition/requests.jsonl")):
        if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink():
            raise ValueError("Controller acquisition evidence must be plain files")
        record = summarize(path.parent)
        record["probe"] = path.parent.parent.name.removeprefix("probe-")
        record["evidence_persisted"] = target is not None
        if target is not None:
            retained = target / (path.parent.parent.name + "-requests.jsonl")
            shutil.copyfile(path, retained)
            if digest(retained) != record["log_sha256"]:
                raise ValueError("Acquisition evidence copy changed")
            record["original_log_path"], record["log_path"] = record["log_path"], str(retained.resolve())
        probes.append(record)
    return {"mode": "private-snapshot-http", "scientific_headline_instrument": False,
            "probes": probes, "probe_count": len(probes),
            "bytes": sum(p["bytes"] for p in probes), "seconds": sum(p["seconds"] for p in probes)}


def split_inputs(inputs):
    root = Path(inputs).resolve()
    for name in ("public", "provider"):
        path = root / name
        if not path.is_dir() or path.is_symlink():
            raise ValueError("Acquisition inputs require plain public/ and provider/ directories")
    provider_manifest(root / "provider")
    return root / "public", root / "provider"


def stage_public(submission, public, stage, base_url=None):
    shutil.copytree(submission, stage, ignore=shutil.ignore_patterns("_controller_inputs"))
    target = Path(stage) / "_controller_inputs"
    # Public descriptors are controller-created; copying cannot follow links.
    for source in public.rglob("*"):
        if source.is_symlink():
            raise ValueError("Public input symlinks are forbidden")
    shutil.copytree(public, target)
    if base_url is not None:
        descriptor = target / "acquisition.json"
        data = json.loads(descriptor.read_text())
        if data.get("base_url") != BASE_URL:
            raise ValueError("Unexpected snapshot endpoint descriptor")
        data["base_url"] = base_url
        descriptor.write_text(json.dumps(data, indent=2) + "\n")
    return Path(stage)


class LocalProvider:
    """Fresh subprocess HTTP server for trusted controls, never native I/O threads."""
    def __init__(self, provider, log_dir):
        self.provider, self.log_dir = Path(provider), Path(log_dir)
        self.process = None

    def __enter__(self):
        self.log_dir.mkdir(parents=True, exist_ok=False)
        ready = self.log_dir / "ready.json"
        self.stderr = (self.log_dir / "server.stderr").open("w")
        self.process = subprocess.Popen([sys.executable, "-I", "-S", str(SCRIPT), "--serve",
                                        "--provider", str(self.provider), "--logs", str(self.log_dir / "requests.jsonl"),
                                        "--host", "127.0.0.1", "--port", "0", "--ready", str(ready)],
                                       stdout=subprocess.DEVNULL, stderr=self.stderr)
        try:
            deadline = time.monotonic() + 10
            while not ready.is_file():
                if self.process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Snapshot server did not start; see " + str(self.log_dir / "server.stderr"))
                time.sleep(0.02)
            self.base_url = "http://127.0.0.1:" + str(json.loads(ready.read_text())["port"])
            return self
        except Exception:
            self.__exit__()
            raise

    def __exit__(self, *_):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=5)
        if hasattr(self, "stderr"):
            self.stderr.close()


class AcquisitionLocal:
    """Trusted controls only; isolation is deliberately not claimed."""
    name = "local-trusted-snapshot"

    def run(self, submission, inputs, argv, scratch, seconds=120):
        from assessment.execute import _collect
        scratch = Path(scratch)
        scratch.mkdir(parents=True, exist_ok=True)
        public, provider = split_inputs(inputs)
        log_dir = scratch / "acquisition"
        output = scratch / "output"
        with LocalProvider(provider, log_dir) as server:
            stage = stage_public(submission, public, scratch / "stage", server.base_url)
            output.mkdir()
            command = [a.replace("{input_dir}", str(stage / "_controller_inputs")).replace("{output_dir}", str(output)) for a in argv]
            if command[0] in ("python", "python3"):
                command[0] = sys.executable
            start = time.monotonic()
            try:
                result = subprocess.run(command, cwd=stage, capture_output=True, text=True, timeout=seconds)
                record = {"exit_code": result.returncode, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]}
            except subprocess.TimeoutExpired:
                record = {"exit_code": 124, "stdout": "", "stderr": "Deadline exceeded"}
            except OSError as error:
                record = {"exit_code": 127, "stdout": "", "stderr": str(error)}
        return _collect({**record, "executor": self.name, "seconds": time.monotonic() - start,
                         "infrastructure_unavailable": False, "acquisition": summarize(log_dir)}, output)


def _docker(*args, **kwargs):
    from assessment.runtime import docker
    return docker(*args, **kwargs)


def hardening(memory, cpus, pids=128):
    return ["--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", str(pids), "--ulimit", "nofile=1024:1024", "--memory", str(memory), "--cpus", str(cpus),
            "--user", f"{os.getuid() or 65534}:{os.getgid() or 65534}",
            "--tmpfs", "/tmp:rw,nosuid,size=512m"]


def inspect_container(name, image, network, expected_mounts):
    from assessment.runtime import InfrastructureUnavailable
    config = json.loads(_docker("inspect", name).stdout)[0]
    host = config["HostConfig"]
    mounts = [(m["Source"], m["Destination"], m["RW"]) for m in config["Mounts"] if m["Type"] == "bind"]
    networks = config["NetworkSettings"]["Networks"]
    passed = (config["Image"] == image and host["NetworkMode"] == network and set(networks) == {network}
              and host["ReadonlyRootfs"] and not host["Privileged"]
              and config["Config"]["User"].split(":")[0] not in ("", "0", "root")
              and sorted(mounts) == sorted(expected_mounts) and len(config["Mounts"]) == len(expected_mounts)
              and "ALL" in [x.upper() for x in host.get("CapDrop", [])] and not host.get("CapAdd")
              and any(x.split(":")[0] == "no-new-privileges" for x in host.get("SecurityOpt", []))
              and not host.get("PortBindings") and not host.get("PublishAllPorts")
              and not host.get("ExtraHosts") and host.get("PidMode", "") == ""
              and host.get("IpcMode", "private") in ("", "private")
              and not host.get("Devices") and not host.get("DeviceRequests")
              and int(host.get("Memory", 0)) > 0 and int(host.get("PidsLimit", 0)) > 0)
    if not passed:
        raise InfrastructureUnavailable("Snapshot container boundary mismatch: " + name)
    return config


class DockerProvider:
    def __init__(self, image, provider, log_dir):
        self.image, self.provider, self.log_dir = image, Path(provider).resolve(), Path(log_dir).resolve()
        suffix = uuid.uuid4().hex[:12]
        self.network, self.name = "weather-snapshot-net-" + suffix, "weather-snapshot-source-" + suffix

    def __enter__(self):
        from assessment.runtime import InfrastructureUnavailable, preflight
        preflight(self.image)
        provider_manifest(self.provider)
        self.log_dir.mkdir(parents=True, exist_ok=False)
        try:
            # Internal alone still permits bridge-host services. Isolated mode
            # (Docker >=28) removes that host bridge address; no weak fallback.
            _docker("network", "create", "--internal", "--opt", "com.docker.network.bridge.gateway_mode_ipv4=isolated", self.network)
            mounts = [(str(self.provider), "/provider", False), (str(SCRIPT), "/server/acquisition.py", False),
                      (str(self.log_dir), "/logs", True)]
            args = ["run", "--detach", "--name", self.name, "--network", self.network, "--network-alias", "weather-source",
                    *hardening("256m", "0.25", 32)]
            for source, target, writable in mounts:
                args += ["--mount", f"type=bind,src={source},dst={target}" + ("" if writable else ",readonly")]
            _docker(*args, "--entrypoint", "python", self.image, "-I", "-S", "/server/acquisition.py", "--serve",
                    "--provider", "/provider", "--logs", "/logs/requests.jsonl", "--host", "0.0.0.0", "--port", "8000")
            inspect_container(self.name, self.image, self.network, mounts)
            self.inspect_network({self.name})
            deadline = time.monotonic() + 15
            while True:
                probe = _docker("exec", self.name, "python", "-I", "-S", "-c",
                                "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/_health',timeout=1).read()", check=False, timeout=3)
                if probe.returncode == 0:
                    break
                if time.monotonic() >= deadline:
                    raise InfrastructureUnavailable("Snapshot provider readiness deadline")
                time.sleep(0.1)
            return self
        except Exception:
            self.__exit__()
            raise

    def inspect_network(self, names):
        from assessment.runtime import InfrastructureUnavailable
        config = json.loads(_docker("network", "inspect", self.network).stdout)[0]
        actual = {row["Name"] for row in config.get("Containers", {}).values()}
        if (not config["Internal"] or config.get("EnableIPv6") or config["Driver"] != "bridge"
            or config.get("Options", {}).get("com.docker.network.bridge.gateway_mode_ipv4") != "isolated"
            or actual != set(names)):
            raise InfrastructureUnavailable("Snapshot isolated network boundary mismatch")

    def __exit__(self, *_):
        _docker("rm", "--force", self.name, check=False)
        _docker("network", "rm", self.network, check=False)


class AcquisitionToolSandbox:
    """ToolSandbox-compatible actor, connected only to its provider snapshot."""
    def __init__(self, image, work, task, substrate, inputs, memory="4g", cpus=2, feedback=None):
        self.image, self.work, self.task, self.substrate = image, Path(work).resolve(), Path(task).resolve(), Path(substrate).resolve()
        self.public, self.provider = split_inputs(inputs)
        self.memory, self.cpus, self.feedback = memory, cpus, feedback
        self.name = "weather-snapshot-actor-" + uuid.uuid4().hex[:12]
        self.log_dir = self.work.parent / "controller" / ("acquisition-" + uuid.uuid4().hex[:12])
        self.gateway = DockerProvider(image, self.provider, self.log_dir)
        self.mounts = [(str(self.work), "/work", True), (str(self.task), "/task", False),
                       (str(self.substrate), "/substrate", False), (str(self.public), "/work/inputs", False)]

    def __enter__(self):
        self.work.mkdir(parents=True, exist_ok=True)
        (self.work / "inputs").mkdir(exist_ok=True)
        self.gateway.__enter__()
        try:
            args = ["run", "--detach", "--name", self.name, "--network", self.gateway.network,
                    *hardening(self.memory, self.cpus)]
            for source, target, writable in self.mounts:
                args += ["--mount", f"type=bind,src={source},dst={target}" + ("" if writable else ",readonly")]
            _docker(*args, "--workdir", "/work", "--entrypoint", "/bin/sh", self.image, "-c", "while :; do sleep 60; done")
            self.boundary = self.inspect()
            return self
        except Exception:
            self.__exit__()
            raise

    def inspect(self):
        inspect_container(self.name, self.image, self.gateway.network, self.mounts)
        inspect_container(self.gateway.name, self.image, self.gateway.network,
                          [(str(self.provider), "/provider", False), (str(SCRIPT), "/server/acquisition.py", False),
                           (str(self.log_dir.resolve()), "/logs", True)])
        self.gateway.inspect_network({self.name, self.gateway.name})
        return {"passed": True, "network": "isolated-internal-snapshot", "runtime_image": self.image,
                "mounts": [{"destination": m[1], "writable": m[2]} for m in self.mounts],
                "private_references_mounted": False, "private_observations_mounted": False,
                "model_credentials_mounted": False, "trusted_controller_adapter": True,
                "acquisition": summarize(self.log_dir)}

    def execute(self, command, timeout):
        # Reuse only ToolSandbox's exec/deadline implementation, not its network.
        from assessment.runtime import ToolSandbox
        return ToolSandbox.execute(self, command, timeout)

    def score_development(self, prediction_file, timeout=60):
        from assessment.runtime import ToolSandbox
        return ToolSandbox.score_development(self, prediction_file, timeout)

    def __exit__(self, *_):
        try:
            _docker("rm", "--force", self.name, check=False)
        finally:
            self.gateway.__exit__()


class AcquisitionDocker:
    name = "docker-snapshot-http"

    def __init__(self, image, memory="4g", cpus=2):
        self.image, self.memory, self.cpus = image, memory, cpus

    def run(self, submission, inputs, argv, scratch, seconds=120):
        from assessment.execute import _collect
        from assessment.runtime import InfrastructureUnavailable
        scratch = Path(scratch)
        scratch.mkdir(parents=True, exist_ok=True)
        public, provider = split_inputs(inputs)
        stage = stage_public(submission, public, scratch / "stage")
        output = scratch / "output"
        output.mkdir()
        name = "weather-snapshot-replay-" + uuid.uuid4().hex[:12]
        log_dir = scratch / "acquisition"
        command = [a.replace("{input_dir}", "/work/_controller_inputs").replace("{output_dir}", "/output") for a in argv]
        mounts = [(str(stage.resolve()), "/work", False), (str(output.resolve()), "/output", True)]
        start = time.monotonic()
        record = {"exit_code": 125, "stdout": "", "stderr": "", "infrastructure_unavailable": True}
        try:
            with DockerProvider(self.image, provider, log_dir) as gateway:
                args = ["create", "--name", name, "--network", gateway.network, *hardening(self.memory, self.cpus)]
                for source, target, writable in mounts:
                    args += ["--mount", f"type=bind,src={source},dst={target}" + ("" if writable else ",readonly")]
                # Start a harmless waiting process, inspect its live network,
                # then release the scientific command. No agent code precedes
                # validation; no private provider mount enters this actor.
                gate = 'while ! test -f /tmp/weather-controller-start; do sleep 0.1; done; exec "$@"'
                try:
                    _docker(*args, "--workdir", "/work", "--entrypoint", "/bin/sh", self.image,
                            "-c", gate, "snapshot-replay", *command)
                    _docker("start", name)
                    inspect_container(name, self.image, gateway.network, mounts)
                    gateway.inspect_network({name, gateway.name})
                    _docker("exec", name, "touch", "/tmp/weather-controller-start")
                    _docker("wait", name, timeout=seconds)
                    final = json.loads(_docker("inspect", name).stdout)[0]
                    logs = _docker("logs", name, check=False)
                    record = {"exit_code": final["State"]["ExitCode"], "stdout": logs.stdout[-4000:],
                              "stderr": logs.stderr[-4000:], "infrastructure_unavailable": False}
                except subprocess.TimeoutExpired:
                    _docker("kill", name, check=False)
                    record = {"exit_code": 124, "stdout": "", "stderr": "Snapshot replay deadline", "infrastructure_unavailable": False}
                finally:
                    _docker("rm", "--force", name, check=False)
        except InfrastructureUnavailable as error:
            record["stderr"] = str(error)[:1500]
        finally:
            _docker("rm", "--force", name, check=False)
        return _collect({**record, "executor": self.name, "seconds": time.monotonic() - start,
                         "acquisition": summarize(log_dir), "network": "isolated-internal-snapshot"}, output)


def sandbox_factory(*args, **kwargs):
    return AcquisitionToolSandbox(*args, **kwargs)


def executor_factory(base_executor):
    from assessment.execute import Docker, Local
    if isinstance(base_executor, AcquisitionDocker) or isinstance(base_executor, AcquisitionLocal):
        return base_executor
    if isinstance(base_executor, Docker):
        return AcquisitionDocker(base_executor.image, base_executor.memory, base_executor.cpus)
    if isinstance(base_executor, Local):
        return AcquisitionLocal()
    raise TypeError("Unsupported acquisition executor: " + type(base_executor).__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--logs", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--ready")
    args = parser.parse_args()
    serve(args.provider, args.logs, args.host, args.port, args.ready)
