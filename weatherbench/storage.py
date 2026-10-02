import hashlib
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
STATE = ROOT / "var"
PRIVATE = STATE / "private/tasks"
ARCHIVE = ROOT / "archive/pilot-2026-10-01"


def identifier(value):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", value):
        raise ValueError("Use a short lowercase identifier with letters, numbers, dashes or underscores")
    return value


def read(path):
    return yaml.safe_load(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Expected a plain directory")
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlink in artifact bundle: {path.relative_to(root)}")
        if path.is_file():
            files[str(path.relative_to(root))] = {"sha256": digest(path), "bytes": path.stat().st_size}
        elif not path.is_dir():
            raise ValueError("Special file in artifact bundle")
    return files


def copy_bundle(source, destination):
    import shutil
    before = inventory(source)
    if Path(destination).exists():
        raise ValueError("Refuse to overwrite an artifact bundle")
    shutil.copytree(source, destination)
    if inventory(destination) != before:
        raise ValueError("Artifact copy mismatch")
    return before


def task_path(name):
    path = TASKS / identifier(name)
    if not (path / "task.yaml").is_file():
        raise ValueError(f"Unknown task: {name}")
    return path
