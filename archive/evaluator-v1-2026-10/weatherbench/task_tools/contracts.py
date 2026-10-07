"""Validate evidence records without executing any submitted workflow."""
import json
import re
from datetime import datetime
from pathlib import PurePosixPath

from .prepare import digest


def retained_path(root, name):
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("Retained files need relative paths")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Retained paths must stay inside the submission")
    target = root / name
    if not target.is_file():
        raise ValueError(f"Missing retained file: {name}")
    return target


def provenance(root):
    value = json.loads((root / "provenance.json").read_text())
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Expected provenance schema_version 1")
    for key in ("sources", "files", "transformations"):
        if not isinstance(value.get(key), list) or not value[key]:
            raise ValueError(f"Provenance needs a nonempty {key} list")
    ids = set()
    for source in value["sources"]:
        if not isinstance(source, dict) or not all(isinstance(source.get(k), str) and source[k].strip() for k in ("id", "product_version")):
            raise ValueError("Sources need an identifier and product_version")
        if source["id"] in ids:
            raise ValueError("Duplicate source identifier")
        ids.add(source["id"])
        if source.get("access") not in ("downloaded", "cache_hit", "supplied") or not isinstance(source.get("request"), dict) or not source["request"]:
            raise ValueError("Record actual access and a nonempty source request")
        if "retrieved_at" not in source:
            raise ValueError("Record retrieved_at, or null for supplied inputs")
        if source["retrieved_at"] is not None or source["access"] != "supplied":
            if not isinstance(source["retrieved_at"], str):
                raise ValueError("Downloads/cache hits need a retrieval timestamp")
            stamp = datetime.fromisoformat(source["retrieved_at"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("Retrieval timestamps need a timezone")
    files = set()
    for entry in value["files"]:
        if not isinstance(entry, dict):
            raise ValueError("File records must be objects")
        name, sha = entry.get("path"), entry.get("sha256")
        target = retained_path(root, name)
        if name in files or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha) or digest(target) != sha:
            raise ValueError("Retained-file records need unique paths and matching SHA-256 hashes")
        source_ids = entry.get("source_ids")
        if not isinstance(source_ids, list) or not all(isinstance(s, str) and s in ids for s in source_ids):
            raise ValueError("File source_ids must reference declared sources")
        files.add(name)
    for step in value["transformations"]:
        if not isinstance(step, dict) or not isinstance(step.get("operation"), str) or not step["operation"].strip() or not isinstance(step.get("parameters"), dict):
            raise ValueError("Transformations need operation and parameters")
        for key in ("inputs", "outputs"):
            if not isinstance(step.get(key), list) or not step[key] or not all(isinstance(p, str) and p in files for p in step[key]):
                raise ValueError("Transformation inputs/outputs must name recorded files")
    return value


def execution(root, needs_prediction=False):
    value = json.loads((root / "execution.json").read_text())
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Expected execution schema_version 1")
    commands = {"replay": ["{output_dir}"]}
    if needs_prediction:
        commands["predict"] = ["{forecast_path}", "{output_path}"]
    for name, placeholders in commands.items():
        command = value.get(name)
        argv = command.get("argv") if isinstance(command, dict) else None
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg.strip() for arg in argv):
            raise ValueError(f"{name} needs a nonempty argv list")
        if not all(any(token in arg for arg in argv) for token in placeholders):
            raise ValueError(f"{name} must include {placeholders}")
    retained = value.get("retained_files")
    if not isinstance(retained, list) or not retained:
        raise ValueError("Declare nonempty retained_files")
    for name in retained:
        retained_path(root, name)
    dependencies = value.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies or not all(isinstance(d, str) and d.strip() for d in dependencies):
        raise ValueError("Declare the runtime/tool dependencies")
    return value
