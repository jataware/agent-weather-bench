"""Bounded development-score requests for Level 2. Final-period scores never pass through here.

Same contract as weatherbench.feedback, for answers in the JSON envelope: every
request is counted before it is read, each queried file is frozen and hashed, and
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
    "description": "Score a development forecast. Give the name of a JSON file in /work/submission with the same results layout "
                   "as answer.json. Every request uses one of the allowed submissions, including malformed ones. "
                   "Final-period scores and observations are unavailable.",
    "inputSchema": {"type": "object", "properties": {"prediction_file": {"type": "string"}},
                    "required": ["prediction_file"], "additionalProperties": False},
}


def read_submission(work, filename, limit):
    """Read one regular file under /work/submission through directory descriptors, never following links."""
    if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.json", filename):
        raise ValueError("Use a JSON file name in /work/submission, without directories")
    descriptors = []
    try:
        parent = os.open(work, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(parent)
        parent = os.open("submission", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        descriptors.append(parent)
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        descriptors.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= limit:
            raise ValueError("The file must be a nonempty regular file within the size limit")
        data = bytearray()
        while len(data) <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) != before.st_size or os.fstat(fd).st_mtime_ns != before.st_mtime_ns:
            raise ValueError("The file changed while being read; finish writing before scoring")
        return bytes(data)
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


class DevelopmentFeedback:
    def __init__(self, work, controller, score, max_submissions=5, max_file_bytes=8388608):
        """`score(parsed_json)` returns aggregate development metrics and may raise ValueError."""
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
            data = read_submission(self.work, prediction_file, self.file_limit)
            snapshot = self.controller / f"prediction-{index:03d}.json"
            snapshot.write_bytes(data)
            row.update(prediction_sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), snapshot=snapshot.name)
            metrics = self.score(json.loads(data))
            encoded = json.dumps(metrics, allow_nan=False)
            row.update(status="scored", metrics=metrics)
            result = {"exit_code": 0, "stdout": encoded, "stderr": "", "prediction_sha256": row["prediction_sha256"]}
        except (OSError, ValueError, TypeError, KeyError) as error:
            # A scorer exception can carry target values or host paths; the agent sees only its type.
            row.update(status="failed", error_type=type(error).__name__, private_error=str(error)[:1500])
            result = {"exit_code": 1, "stdout": "",
                      "stderr": f"The development forecast could not be scored ({type(error).__name__}); check the results layout and the file name"}
        row["seconds"] = time.monotonic() - started
        self.finish()
        result.update(seconds=row["seconds"], feedback_scope="development_only", feedback_query=index, feedback_remaining=self.limit - index)
        return result
