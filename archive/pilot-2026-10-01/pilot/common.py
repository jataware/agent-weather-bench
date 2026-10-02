import hashlib
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def rhiza_catalog():
    value = os.environ.get("RHIZA_WEATHER_SKILLS_DIR")
    if not value:
        raise ValueError("Set RHIZA_WEATHER_SKILLS_DIR to the approved Rhiza weather skills checkout")
    path = Path(value).resolve()
    if not (path / "skills").is_dir():
        raise ValueError("Rhiza weather skills checkout needs a skills directory")
    return path
CRITERIA = ("data_provenance", "scientific_processing", "results_uncertainty",
            "communication", "reproducibility_reuse")
ARMS = ("scratch", "rhiza", "accord")


def read(path):
    return yaml.safe_load(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(root):
    root = Path(root)
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError(f"Symlink in submission: {p.relative_to(root)}")
        if p.is_file():
            files[str(p.relative_to(root))] = {"sha256": digest(p), "bytes": p.stat().st_size}
        elif not p.is_dir():
            raise ValueError("Special file in submission")
    return files


def task(name):
    if name not in {"seasonal", "iod", "kenya"}:
        raise ValueError("Unknown task")
    return read(ROOT / "tasks" / f"{name}.yaml")


def brief(spec, phase):
    return spec["brief"] + "\n\n" + spec["phases"][phase]["brief"] + "\n\n" + spec["submission"]
