"""Bounded development-score requests for Level 2. Final-period scores never pass through here.

Same contract as the first evaluator's development feedback, for forecasts in a results store: every
request is counted before it is read, each queried store is frozen and hashed, and
only aggregate metrics return to the agent.
"""
import hashlib
import json
import os
import re
import stat
import time
from pathlib import Path

SCORE_TOOL = {
    "type": "function", "name": "score_development",
    "description": "Score a development forecast. Give the name of a Zarr store in /work/submission laid out as results.zarr, "
                   "holding the development forecast with its coordinates. Every request uses one of the allowed submissions, "
                   "including malformed ones. Final-period scores and observations are unavailable.",
    "inputSchema": {"type": "object", "properties": {"prediction_file": {"type": "string"}},
                    "required": ["prediction_file"], "additionalProperties": False},
}


def freeze_store(work, name, destination, limit, max_files=20000):
    """Copy one store under /work/submission into the controller's folder, never following links. Returns (sha256, bytes)."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.zarr", name):
        raise ValueError("Use the name of a Zarr store in /work/submission, without directories")
    source, digest, total, count = Path(work) / "submission" / name, hashlib.sha256(), 0, 0
    if source.is_symlink() or not source.is_dir():
        raise ValueError("The store must be a directory in /work/submission")
    pending = [(source, Path(destination))]
    while pending:
        folder, target = pending.pop()
        target.mkdir(parents=True)
        for entry in sorted(os.scandir(folder), key=lambda item: item.name):
            if entry.is_symlink():
                raise ValueError("The store must not contain links")
            if entry.is_dir(follow_symlinks=False):
                pending.append((Path(entry.path), target / entry.name))
                continue
            count += 1
            fd = os.open(entry.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise ValueError("The store must hold regular files only")
                data = os.read(fd, limit + 1 - total)
            finally:
                os.close(fd)
            total += len(data)
            if total > limit or count > max_files:
                raise ValueError("The store is larger than the size limit")
            (target / entry.name).write_bytes(data)
            digest.update(str(Path(entry.path).relative_to(source)).encode() + b"\0" + hashlib.sha256(data).digest())
    if not count:
        raise ValueError("The store is empty")
    return digest.hexdigest(), total


class DevelopmentFeedback:
    def __init__(self, work, controller, score, max_submissions=5, max_file_bytes=8388608):
        """`score(frozen_store_path)` returns aggregate development metrics and may raise ValueError."""
        if type(max_submissions) is not int or not 1 <= max_submissions <= 100:
            raise ValueError("Invalid feedback submission limit")
        self.work, self.controller = Path(work), Path(controller)
        self.controller.mkdir(parents=True, exist_ok=False)
        self.score, self.limit, self.file_limit = score, max_submissions, max_file_bytes
        self.attempts, self.denials = [], 0
        self.finish()

    def finish(self):
        record = {"schema_version": 1, "scope": "development_only", "max_submissions": self.limit, "attempts": self.attempts,
                  "limit_denials": self.denials, "final_score_exposed": False, "final_observations_exposed": False}
        (self.controller / "ledger.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
        return record

    def public_summary(self):
        fields = ("query", "prediction_file", "status", "prediction_sha256", "bytes", "metrics", "seconds", "error_type")
        return {"scope": "development_only", "max_submissions": self.limit, "limit_denials": self.denials,
                "requests": [{key: row[key] for key in fields if key in row} for row in self.attempts],
                "final_score_exposed": False, "final_observations_exposed": False}

    def query(self, prediction_file, timeout=60):
        started = time.monotonic()
        if len(self.attempts) >= self.limit:
            self.denials += 1
            self.finish()
            return {"exit_code": 1, "stdout": "", "stderr": "Development feedback submission limit reached",
                    "feedback_scope": "development_only", "feedback_remaining": 0}
        index = len(self.attempts) + 1
        row = {"query": index, "prediction_file": prediction_file, "status": "reserved"}
        self.attempts.append(row)
        self.finish()                                              # the request counts even if everything after this fails
        try:
            snapshot = self.controller / f"prediction-{index:03d}.zarr"
            digest, size = freeze_store(self.work, prediction_file, snapshot, self.file_limit)
            row.update(prediction_sha256=digest, bytes=size, snapshot=snapshot.name)
            metrics = self.score(snapshot)
            encoded = json.dumps(metrics, allow_nan=False)
            row.update(status="scored", metrics=metrics)
            result = {"exit_code": 0, "stdout": encoded, "stderr": "", "prediction_sha256": row["prediction_sha256"]}
        except (OSError, ValueError, TypeError, KeyError) as error:
            # A scorer exception can carry target values or host paths; the agent sees only its type.
            row.update(status="failed", error_type=type(error).__name__, private_error=str(error)[:1500])
            result = {"exit_code": 1, "stdout": "",
                      "stderr": f"The development forecast could not be scored ({type(error).__name__}); check the store's layout and its name"}
        row["seconds"] = time.monotonic() - started
        self.finish()
        result.update(seconds=row["seconds"], feedback_scope="development_only", feedback_query=index, feedback_remaining=self.limit - index)
        return result
