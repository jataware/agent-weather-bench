"""Run a submission's declared command on controller-chosen inputs.

Docker is the only executor allowed for agent submissions. Local is for the
controller's own trusted control solutions during certification and tests.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

PLACEHOLDERS = ("{input_dir}", "{output_dir}")


def valid_argv(argv):
    return (isinstance(argv, list) and bool(argv) and all(isinstance(arg, str) and arg.strip() for arg in argv)
            and all(any(token in arg for arg in argv) for token in PLACEHOLDERS))


def _stage(submission, inputs, stage):
    shutil.copytree(submission, stage)
    shutil.copytree(inputs, stage / "_controller_inputs")
    return stage


def _collect(record, output):
    """Note what the command wrote. Complete results count even if the process then exited abnormally:
    some scientific libraries crash while shutting down, after the work is done and written."""
    answer = output / "answer.json"
    record["answer"], record["output"] = None, str(output)
    if answer.is_file():
        try:
            record["answer"] = json.loads(answer.read_text())
        except ValueError:
            record["stderr"] = (record.get("stderr") or "") + "\nanswer.json written by the run command is not valid JSON"
    record["crashed_by_signal"] = record["exit_code"] >= 128 or record["exit_code"] < 0
    return record


class Local:
    """Trusted code only: runs on the controller with no isolation."""
    name = "local-trusted"

    def run(self, submission, inputs, argv, scratch, seconds=120):
        stage, output = _stage(Path(submission), Path(inputs), Path(scratch) / "stage"), Path(scratch) / "output"
        output.mkdir(parents=True)
        command = [arg.replace("{input_dir}", str(stage / "_controller_inputs")).replace("{output_dir}", str(output)) for arg in argv]
        if command[0] in ("python", "python3"):
            command[0] = sys.executable
        try:
            result = subprocess.run(command, cwd=stage, capture_output=True, text=True, timeout=seconds)
            record = {"exit_code": result.returncode, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]}
        except subprocess.TimeoutExpired:
            record = {"exit_code": 124, "stdout": "", "stderr": "Deadline exceeded"}
        except OSError as error:
            record = {"exit_code": 127, "stdout": "", "stderr": str(error)}
        return _collect({**record, "executor": self.name, "infrastructure_unavailable": False}, output)


class Docker:
    """The benchmark's offline runtime: no network, read-only submission, dropped capabilities."""
    name = "docker-offline"

    def __init__(self, image, memory="4g", cpus=2):
        self.image, self.memory, self.cpus = image, memory, cpus

    def run(self, submission, inputs, argv, scratch, seconds=120):
        from .runtime import InfrastructureUnavailable, offline
        stage, output = _stage(Path(submission), Path(inputs), Path(scratch) / "stage"), Path(scratch) / "output"
        command = [arg.replace("{input_dir}", "/work/_controller_inputs").replace("{output_dir}", "/output") for arg in argv]
        try:
            record = offline(self.image, stage, output, command, seconds=seconds, memory=self.memory, cpus=self.cpus)
        except InfrastructureUnavailable as error:
            return {"exit_code": 125, "stdout": "", "stderr": str(error)[:1500], "executor": self.name,
                    "infrastructure_unavailable": True, "answer": None, "output": str(output)}
        record = {"exit_code": record["exit_code"], "stdout": record.get("stdout", "")[-4000:], "stderr": record.get("stderr", "")[-4000:],
                  "executor": self.name, "infrastructure_unavailable": bool(record.get("infrastructure_unavailable"))}
        return _collect(record, output)
