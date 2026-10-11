"""Run one authorized study cell once, after its control gates pass."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template


def main(system, recover=False):
    if system not in {"mam-luna-python", "mam-luna-required-accord", "mam-astra-python",
                      "mam-luna-python-context-budget", "mam-luna-required-accord-context-budget"}:
        raise ValueError("System is outside the bounded study")
    template = Template("mam-multimodel-outlook")
    certificate = json.loads((template.folder / "certification.json").read_text())
    proof = json.loads((ROOT / "var/review/mam-suite-20261008/final16-docker-correct-summary.json").read_text())
    if not (certificate["fingerprint"] == proof["fingerprint"] == template.fingerprint()
            and certificate["automatic_tests_passed"] and proof["outcome"] == "pass"
            and certificate["tests"]["1_reference_implementations_agree"]["combinations"] == 16):
        raise ValueError("Current scientific and Docker control gates have not passed")
    binary = (Path.home() / ".codex/packages/standalone/releases/0.160.0-aarch64-apple-darwin/bin/codex").resolve()
    version = subprocess.run([str(binary), "--version"], capture_output=True, text=True, check=True).stdout.strip()
    if version != "codex-cli 0.160.0":
        raise ValueError("CLI does not match the snapshotted adapter's pinned version")
    folder = ROOT / "var/review/mam-attempts-20261008" / system
    recovered_from = None
    if recover:
        previous = json.loads((folder / "invocation.json").read_text())
        run = ROOT / previous["result"]["directory"]
        meta = json.loads((run / "run.json").read_text())
        if not (meta["status"] == "execution_error" and meta.get("usage") is None
                and meta.get("tool_calls") is None
                and meta.get("reason") == "ValueError: Missing controller environment variable: CODEX_BINARY"
                and not (run / "logs/events.jsonl").exists()):
            raise ValueError("Recovery is restricted to the verified pre-adapter environment failure")
        recovered_from = meta["id"]
        folder = folder.with_name(system + "-environment-recovery-1")
    folder.mkdir(parents=True, exist_ok=False)  # Never silently retry a cell.
    command = [sys.executable, "-m", "assessment", "run", template.name,
               "kenya-interior--mam-2016", "--system", system, "--no-judge"]
    config = ROOT / "systems" / system / "system.yaml"
    record = {"system": system, "fingerprint": template.fingerprint(),
              "system_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
              "started_at": datetime.now(timezone.utc).isoformat(), "command": command,
              "status": "running", "agent_retries": 0, "recovered_from": recovered_from,
              "codex_binary": str(binary), "codex_version": version,
              "codex_binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
    path = folder / "invocation.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    started = time.monotonic()
    with (folder / "stdout.json").open("w") as stdout, (folder / "stderr.log").open("w") as stderr:
        result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                env={**os.environ, "CODEX_BINARY": str(binary)})
    record.update(status="finished", exit_code=result.returncode,
                  finished_at=datetime.now(timezone.utc).isoformat(), cli_wall_seconds=time.monotonic() - started)
    if result.returncode == 0:
        record["result"] = json.loads((folder / "stdout.json").read_text())
    path.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], recover="--recover-environment" in sys.argv[2:]))
