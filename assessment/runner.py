"""Launch one system on one instance of a template, then assess its submission.

Reuses the existing harness pieces unchanged: system definitions, the Docker tool
sandbox, the adapter protocol and the substrate-use monitor. The controller, not
the agent, keeps the provenance record.
"""
import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from weatherbench import adapters
from weatherbench.runtime import ToolSandbox, preflight
from weatherbench.storage import copy_bundle, digest, inventory, read, write
from weatherbench.substrate_use import substrate_use
from weatherbench.systems import resolve_system, snapshot, validate

from .assess import assess
from .execute import Docker
from .spec import ROOT

RUNS = ROOT / "var/template-runs"


def resolve_run(value):
    path = Path(value)
    if not path.is_dir():
        path = RUNS / value
    if not (path / "run.json").is_file():
        raise ValueError("Expected a template run ID or directory")
    return path.resolve()


def run(template, params, system, parent=None):
    config_path = resolve_system(system)
    config = validate(config_path)
    preflight(config["runtime"]["image"])
    if parent:
        parent = resolve_run(parent)
        if read(parent / "run.json")["system_sha256"] != digest(config_path):
            raise ValueError("Retained and reset comparisons require the same system definition")
        if inventory(parent / "retained") != read(parent / "retained-manifest.json"):
            raise ValueError("Parent retained artifacts changed")
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{template.name}-{params['id']}-{config['id']}-{uuid.uuid4().hex[:6]}"
    folder = RUNS / name
    folder.mkdir(parents=True)
    metadata = {"schema_version": 1, "id": name, "template": template.name, "spec_version": template.spec["spec_version"],
                "fingerprint": template.fingerprint(), "mode": template.spec["mode"], "instance": params, "system": config["id"],
                "kind": config["kind"], "system_sha256": digest(config_path), "runtime_image": config["runtime"]["image"],
                "parent": parent.name if parent else None, "status": "created", "created_at": datetime.now(timezone.utc).isoformat()}
    write(folder / "run.json", metadata)
    config, bundle = snapshot(config_path, folder / "system")
    write(folder / "system.json", config)
    write(folder / "substrate-manifest.json", bundle)

    task, work, inputs = folder / "task", folder / "work", folder / "inputs"
    for path in (task, work / "submission", work / "state", work / "prior", folder / "logs", folder / "controller"):
        path.mkdir(parents=True)
    brief, envelope = template.brief(params), (ROOT / "assessment/envelope.md").read_text()
    (task / "brief.md").write_text(brief)
    (task / "envelope.md").write_text(envelope)
    (task / "instance.json").write_text(json.dumps(params, indent=2) + "\n")
    template.hooks.stage_inputs(template.private, params, inputs)
    write(folder / "input-manifest.json", inventory(inputs))
    if parent:
        shutil.copytree(parent / "retained/state", work / "state", dirs_exist_ok=True)
        shutil.copytree(parent / "retained/prior", work / "prior", dirs_exist_ok=True)
        copy_bundle(parent / "frozen", work / "prior" / parent.name)
    request = {"schema_version": 1, "type": "start", "task": template.name, "prompt": brief, "contracts": {"envelope": envelope},
               "paths": {"work": "/work", "inputs": "/work/inputs", "submission": "/work/submission", "state": "/work/state",
                         "prior": "/work/prior", "substrate": "/substrate", "task": "/task"},
               "substrate_instructions": config.get("substrate", {}).get("instructions", ""), "budget": config["budget"],
               "retained_files": inventory(work / "prior"), "protocol": "execute / tool_result / usage / final as JSON lines"}
    write(folder / "request.json", request)

    started, boundary = time.monotonic(), {"passed": False, "state": "unresolved"}
    metadata["status"] = "running"
    write(folder / "run.json", metadata)
    try:
        with ToolSandbox(config["runtime"]["image"], work, task, folder / "system", inputs,
                         memory=config["runtime"]["memory"], cpus=config["runtime"]["cpus"]) as box:
            if config["driver"]["kind"] == "command":
                result = adapters.command_driver(config, folder / "system", request, box, folder / "logs/events.jsonl", folder / "logs/driver.stderr")
            else:
                result = adapters.anthropic_driver(config, request, box, folder / "logs/events.jsonl")
            boundary = {**box.inspect(), "state": "pass"}
    except Exception as error:                                    # the run record must survive any harness failure
        result = {"status": "execution_error", "reason": f"{type(error).__name__}: {str(error)[:1500]}", "usage": None,
                  "usage_source": "unknown", "seconds": time.monotonic() - started, "tool_calls": None}
    metadata.update(result)
    artifacts = copy_bundle(work / "submission", folder / "frozen")
    write(folder / "artifacts.json", artifacts)
    (folder / "retained").mkdir()
    copy_bundle(work / "state", folder / "retained/state")
    copy_bundle(work / "prior", folder / "retained/prior")
    write(folder / "retained-manifest.json", inventory(folder / "retained"))
    inputs_unchanged = inventory(inputs) == read(folder / "input-manifest.json")
    system_unchanged = inventory(folder / "system") == bundle
    if not (inputs_unchanged and system_unchanged):
        boundary = {"passed": False, "state": "fail", "reason": "Inputs or the system snapshot changed during the run"}

    # Provenance is the controller's record. The agent writes none of it.
    log = folder / "logs/events.jsonl"
    sources = template.folder / "sources.json"
    write(folder / "controller/provenance.json", {
        "inputs": read(folder / "input-manifest.json"), "inputs_unchanged": inputs_unchanged,
        "sources": {"record": str(sources.relative_to(ROOT)), "sha256": digest(sources)} if sources.is_file() else None,
        "artifacts_at_freeze": artifacts,
        "system": {"id": config["id"], "kind": config["kind"], "definition_sha256": metadata["system_sha256"],
                   "substrate_files": bundle, "runtime_image": config["runtime"]["image"]},
        "spec": {"template": template.name, "spec_version": template.spec["spec_version"], "fingerprint": metadata["fingerprint"]},
        "trace": {"path": "logs/events.jsonl", "sha256": digest(log) if log.is_file() else None},
        "sandbox": boundary, "substrate_use": substrate_use(folder),
        "episode": {"parent": metadata["parent"], "started_from": "retained state of the parent run" if parent else "a fresh workspace"}})
    write(folder / "run.json", metadata)

    executor = Docker(config["runtime"]["image"], config["runtime"]["memory"], config["runtime"]["cpus"])
    assessment = assess(template, params, folder / "frozen", executor, folder / "controller/assessment-work")
    assessment["sandbox"] = boundary["state"]
    write(folder / "assessment.json", assessment)
    shutil.rmtree(folder / "controller/assessment-work", ignore_errors=True)
    return {"run": name, "status": metadata["status"], "computed_outcome": assessment["computed_outcome"], "outcome": assessment["outcome"],
            "directory": str(folder.relative_to(ROOT))}


def list_runs():
    rows = []
    for folder in sorted(RUNS.glob("*")) if RUNS.is_dir() else []:
        if not (folder / "run.json").is_file():
            continue
        meta = read(folder / "run.json")
        assessment = read(folder / "assessment.json") if (folder / "assessment.json").is_file() else {}
        checks = assessment.get("checks", {})
        variant = checks.get("variant", {})
        rows.append({"id": meta["id"], "template": meta["template"], "instance": meta["instance"]["id"], "system": meta["system"], "kind": meta["kind"],
                     "status": meta.get("status"), "computed_outcome": assessment.get("computed_outcome"), "outcome": assessment.get("outcome"),
                     "failed_checks": sorted(name for name, row in checks.items() if row["state"] == "fail"),
                     "unresolved_reasons": assessment.get("unresolved_reasons"),
                     "pitfalls": variant.get("pitfalls_certain") or variant.get("pitfalls_possible") or [],
                     "matched_conventions": assessment.get("matched_conventions"),
                     "usage": meta.get("usage"), "seconds": meta.get("seconds"), "tool_calls": meta.get("tool_calls"),
                     "parent": meta.get("parent"), "substrate_use": substrate_use(folder), "spec_version": meta.get("spec_version")})
    return rows
