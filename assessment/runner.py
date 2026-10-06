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
from weatherbench.systems import resolve_system, snapshot, validate

from . import judge as judging
from .assess import assess, judge_files
from .compare import EnvelopeError, align, read_results
from .execute import Docker
from .feedback import SCORE_TOOL, DevelopmentFeedback
from .outcomes import headline
from .spec import ROOT
from .substrate import image_path_use, substrate_record

RUNS = ROOT / "var/template-runs"


def resolve_run(value):
    path = Path(value)
    if not path.is_dir():
        path = RUNS / value
    if not (path / "run.json").is_file():
        raise ValueError("Expected a template run ID or directory")
    return path.resolve()


def development_scorer(template, params, inputs):
    """Callback for the feedback tool: aggregate development metrics only."""
    def score(store):
        spec = {name: row for name, row in template.spec["results"].items() if not name.startswith("final")}
        frame = {name: value for name, value in template.hooks.expected_coordinates(inputs, params).items() if name in spec}
        results, problems = read_results(spec, None, store=store)
        if problems:
            raise EnvelopeError("; ".join(problems.values()))
        metrics = template.hooks.score(align(spec, results, frame), params, template.private, "development")
        return {key: metrics[key] for key in ("split", "rmse_mm", "raw_model_rmse_mm", "climatology_rmse_mm", "skill_vs_raw_model", "skill_vs_climatology")}
    return score


def run(template, params, system, parent=None, level=1, supplied=(), judge=True):
    config_path = resolve_system(system)
    config = validate(config_path)
    preflight(config["runtime"]["image"])
    if level not in (1, 2) or (level == 2 and "level2" not in template.spec):
        raise ValueError("This template has no such level")
    supplied = sorted(set(supplied))
    unknown = [name for name in supplied if name not in template.spec.get("supplements", {})]
    if unknown:
        raise ValueError(f"This template has no supplement named {unknown[0]}")
    if parent:
        parent = resolve_run(parent)
        if read(parent / "run.json")["system_sha256"] != digest(config_path):
            raise ValueError("Retained and reset comparisons require the same system definition")
        if inventory(parent / "retained") != read(parent / "retained-manifest.json"):
            raise ValueError("Parent retained artifacts changed")
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{template.name}-{params['id']}-L{level}-{config['id']}-{uuid.uuid4().hex[:6]}"
    folder = RUNS / name
    folder.mkdir(parents=True)
    metadata = {"schema_version": 1, "id": name, "template": template.name, "spec_version": template.spec["spec_version"],
                "fingerprint": template.fingerprint(), "mode": template.spec["mode"], "level": level, "instance": params, "system": config["id"],
                "kind": config["kind"], "system_sha256": digest(config_path), "runtime_image": config["runtime"]["image"],
                "parent": parent.name if parent else None, "supplied": supplied, "status": "created", "created_at": datetime.now(timezone.utc).isoformat()}
    write(folder / "run.json", metadata)
    config, bundle = snapshot(config_path, folder / "system")
    write(folder / "system.json", config)
    write(folder / "substrate-manifest.json", bundle)

    task, work, inputs = folder / "task", folder / "work", folder / "inputs"
    for path in (task, work / "submission", work / "state", work / "prior", folder / "logs", folder / "controller"):
        path.mkdir(parents=True)
    brief, envelope = template.brief(params, level, supplied), (ROOT / "assessment/envelope.md").read_text()
    (task / "brief.md").write_text(brief)
    (task / "envelope.md").write_text(envelope)
    for supplement in supplied:                                   # an experimental condition: recorded, and part of what the agent saw
        shutil.copyfile(template.folder / template.spec["supplements"][supplement], task / template.spec["supplements"][supplement])
    template.hooks.stage_inputs(template.private, params, inputs)
    # the agent sees one description of the instance, the one the template stages; internal parameters stay with the controller
    shutil.copyfile(inputs / "instance.json", task / "instance.json")
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
    feedback = None
    if level == 2:
        limits = template.spec["level2"]["feedback"]
        feedback = DevelopmentFeedback(work, folder / "controller/development-feedback", development_scorer(template, params, inputs),
                                       max_submissions=limits["max_submissions"])
        request["tools"] = [SCORE_TOOL]
        request["protocol"] = "execute / score_development / tool_result / usage / final as JSON lines"
        request["development_feedback"] = {"scope": "development_only", "max_submissions": feedback.limit}
    if parent:
        request["prior_work"] = (f"Your submission from an earlier, related task is under /work/prior/{parent.name}/, code and results. "
                                 "Use it, adapt it or ignore it, as you judge best.")
    write(folder / "request.json", request)

    started, boundary = time.monotonic(), {"passed": False, "state": "unresolved"}
    metadata["status"] = "running"
    write(folder / "run.json", metadata)
    try:
        with ToolSandbox(config["runtime"]["image"], work, task, folder / "system", inputs,
                         memory=config["runtime"]["memory"], cpus=config["runtime"]["cpus"], feedback=feedback) as box:
            if config["driver"]["kind"] == "command":
                result = adapters.command_driver(config, folder / "system", request, box, folder / "logs/events.jsonl", folder / "logs/driver.stderr")
            else:
                result = adapters.anthropic_driver(config, request, box, folder / "logs/events.jsonl")
            boundary = {**box.inspect(), "state": "pass"}
    except Exception as error:                                    # the run record must survive any harness failure
        result = {"status": "execution_error", "reason": f"{type(error).__name__}: {str(error)[:1500]}", "usage": None,
                  "usage_source": "unknown", "seconds": time.monotonic() - started, "tool_calls": None}
    public_feedback = None
    if feedback is not None:
        feedback.finish()
        public_feedback = feedback.public_summary()
        write(folder / "controller/feedback-public.json", public_feedback)
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
        "sandbox": boundary, "substrate_use": substrate_record(folder, config),
        "supplied": supplied,
        "episode": {"parent": metadata["parent"], "started_from": "retained state of the parent run" if parent else "a fresh workspace",
                    "prior_work_use": image_path_use(folder, ["/work/prior"])["/work/prior"] if parent else None}})
    write(folder / "run.json", metadata)

    assessment = _assess_run(template, folder, judge)
    return {"run": name, "level": level, "status": metadata["status"], "outcome": assessment["outcome"],
            "computed_outcome": assessment["computed_outcome"], "judged_outcome": assessment["judged_outcome"], "skill": next(iter((assessment.get("skill") or {}).values()), None), "directory": str(folder.relative_to(ROOT))}


def _judge(template, folder, assessment):
    """Have the pinned judge decide an assessment's open questions. A judgement of the same questions and files is reused."""
    meta = read(folder / "run.json")
    kept = folder / "controller/judgements" / f"{judging.judge_id()}.json"
    if meta["spec_version"] != template.spec["spec_version"]:      # the agent of an older run read the brief of its own version
        files = judging.views(folder / "frozen", (folder / "task/brief.md").read_text())
    else:
        files = judge_files(template, meta["instance"], folder / "frozen", meta.get("level", 1), meta.get("supplied", ()))
    judgement = judging.apply(assessment, files, judging.claude_cli, template.spec, read(kept) if kept.is_file() else None)
    if judgement and "unavailable" not in judgement:
        write(kept, judgement)
    return assessment


def _keep(folder, assessment):
    """Earlier assessments are kept: one file per fingerprint, and a convenience copy of the latest."""
    write(folder / "controller/assessments" / f"{assessment['fingerprint'][:16]}.json", assessment)
    write(folder / "assessment.json", assessment)


def _assess_run(template, folder, judge=True):
    """Assess a run's frozen submission and keep the record under the fingerprint that produced it."""
    meta, config = read(folder / "run.json"), read(folder / "system.json")
    if inventory(folder / "frozen") != read(folder / "artifacts.json"):
        raise ValueError("Frozen submission changed")
    feedback = folder / "controller/feedback-public.json"
    executor = Docker(config["runtime"]["image"], config["runtime"]["memory"], config["runtime"]["cpus"])
    work = folder / "controller/assessment-work"
    shutil.rmtree(work, ignore_errors=True)
    assessment = assess(template, meta["instance"], folder / "frozen", executor, work, level=meta.get("level", 1),
                        feedback=read(feedback) if feedback.is_file() else None)
    assessment["sandbox"] = read(folder / "controller/provenance.json")["sandbox"]["state"]
    assessment["assessed_at"] = datetime.now(timezone.utc).isoformat()
    shutil.rmtree(work, ignore_errors=True)
    if judge:
        _judge(template, folder, assessment)
    _keep(folder, assessment)
    return assessment


def judge_run(run_id):
    """Judge a run's recorded assessment without recomputing it. The computed checks stand as they were recorded."""
    from .spec import Template
    folder = resolve_run(run_id)
    meta, assessment = read(folder / "run.json"), read(folder / "assessment.json")
    if inventory(folder / "frozen") != read(folder / "artifacts.json"):
        raise ValueError("Frozen submission changed")
    _judge(Template(meta["template"]), folder, assessment)
    assessment["judged_at"] = datetime.now(timezone.utc).isoformat()
    _keep(folder, headline(assessment))
    return {"run": meta["id"], "outcome": assessment["outcome"], "computed_outcome": assessment["computed_outcome"],
            "judged_outcome": assessment["judged_outcome"], "judge": assessment.get("judge"),
            "judged": {name: row["state"] for name, row in assessment["checks"].items() if row.get("decided_by") == "judge"}}


def reassess(run_id, judge=True):
    """Assess an existing run again under the current spec and code. The submission is not rerun by an agent."""
    from .spec import Template
    folder = resolve_run(run_id)
    meta = read(folder / "run.json")
    current = Template(meta["template"]).spec["spec_version"]
    if meta["spec_version"] != current:
        raise ValueError(f"This run was made under spec version {meta['spec_version']} and the template is at {current}. "
                         "Its agent answered a different contract, so it cannot be assessed against the current one. Its recorded assessments stand.")
    previous = read(folder / "assessment.json") if (folder / "assessment.json").is_file() else None
    if previous and not (folder / "controller/assessments" / f"{previous['fingerprint'][:16]}.json").is_file():
        write(folder / "controller/assessments" / f"{previous['fingerprint'][:16]}.json", previous)
    assessment = _assess_run(Template(meta["template"]), folder, judge)
    return {"run": meta["id"], "outcome": assessment["outcome"], "computed_outcome": assessment["computed_outcome"],
            "judged_outcome": assessment["judged_outcome"], "previous_computed_outcome": previous and previous["computed_outcome"],
            "assessments_kept": sorted(p.name for p in (folder / "controller/assessments").iterdir())}


def list_runs():
    rows = []
    for folder in sorted(RUNS.glob("*")) if RUNS.is_dir() else []:
        if not (folder / "run.json").is_file():
            continue
        meta = read(folder / "run.json")
        assessment = read(folder / "assessment.json") if (folder / "assessment.json").is_file() else {}
        checks = assessment.get("checks", {})
        variant = checks.get("variant", {})
        rows.append({"id": meta["id"], "template": meta["template"], "instance": meta["instance"]["id"], "level": meta.get("level", 1),
                     "system": meta["system"], "kind": meta["kind"], "skill": next(iter((assessment.get("skill") or {}).values()), None),
                     "skill_valid_for_ranking": assessment.get("skill_valid_for_ranking"),
                     "status": meta.get("status"), "outcome": assessment.get("outcome"), "computed_outcome": assessment.get("computed_outcome"),
                     "judged_outcome": assessment.get("judged_outcome"), "judge": (assessment.get("judge") or {}).get("id"),
                     "supplied": meta.get("supplied", []),
                     "failed_checks": sorted(name for name, row in checks.items() if row["state"] == "fail"),
                     "unresolved_reasons": assessment.get("unresolved_reasons"),
                     "pitfalls": variant.get("pitfalls_certain") or variant.get("pitfalls_possible") or [],
                     "matched_conventions": assessment.get("matched_conventions"),
                     "usage": meta.get("usage"), "seconds": meta.get("seconds"), "tool_calls": meta.get("tool_calls"),
                     "parent": meta.get("parent"), "substrate_use": substrate_record(folder, read(folder / "system.json")),
                     "spec_version": meta.get("spec_version")})
    return rows
