"""Launch one system on one instance of a template, then assess its submission.

Reuses the existing harness pieces unchanged: system definitions, the Docker tool
sandbox, the adapter protocol and the tooling-use record (substrate_use.py). The controller, not
the agent, keeps the provenance record.
"""
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import adapters
from .runtime import ToolSandbox, preflight
from .storage import copy_bundle, digest, inventory, read, write
from .systems import resolve_system, snapshot, validate

from . import judge as judging
from .assess import assess, judge_files
from .compare import EnvelopeError, align, read_results
from .execute import Docker
from .feedback import SCORE_TOOL, DevelopmentFeedback
from .outcomes import headline
from .spec import ROOT
from .substrate import image_path_use, library_calls, substrate_record

RUNS = ROOT / "var/template-runs"


MIN_FREE_GB = float(os.environ.get("AWB_MIN_FREE_GB", "12"))
DATA_VOLUME = Path("/System/Volumes/Data") if Path("/System/Volumes/Data").is_dir() else ROOT
INPUTS_CACHE = ROOT / "var/inputs-cache"
ASSESSMENT_LOCK = ROOT / "var/.assessment.lock"


def free_gb(path=None):
    return shutil.disk_usage(path or DATA_VOLUME).free / 1e9


def require_disk(action):
    """Disk is a hard budget: refuse `action` when the data volume is under the floor (AWB_MIN_FREE_GB, default 12)."""
    free = free_gb()
    if free < MIN_FREE_GB:
        raise RuntimeError(f"Refusing to {action}: {free:.1f} GB free on {DATA_VOLUME}, under the {MIN_FREE_GB:g} GB floor")
    return free


class assessment_lock:
    """Agents may run side by side; the controller's replays, probes and tracer run one assessment at a time.

    Their scratch (staged inputs, perturbed copies, replay outputs) is the spike that fills the disk."""

    def __enter__(self):
        import fcntl
        ASSESSMENT_LOCK.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(ASSESSMENT_LOCK, "w")
        fcntl.flock(self.handle, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        import fcntl
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.handle.close()


def staged_inputs(template, params, destination):
    """Stage the instance's inputs once per (template, instance, private snapshot) and hardlink them into `destination`.

    The sandbox mounts inputs read-only, so the links are safe from the agent; the cache's own manifest is checked
    before every reuse and the tree is re-staged if any file differs. Each run still records the manifest of its own
    inputs directory. Saves the per-run copy (267 MB for the outlook) that filled the disk on 13 October 2026."""
    key = digest_text(json.dumps({"params": params, "private": inventory(template.private)}, sort_keys=True))
    cache = INPUTS_CACHE / template.name / params["id"] / key[:16]
    manifest = cache.parent / f"{key[:16]}.manifest.json"
    fresh = cache.is_dir() and manifest.is_file() and inventory(cache) == read(manifest)
    if not fresh:
        shutil.rmtree(cache, ignore_errors=True)
        staging = cache.parent / f"{key[:16]}.staging"
        shutil.rmtree(staging, ignore_errors=True)
        template.hooks.stage_inputs(template.private, params, staging)
        staging.rename(cache)
        write(manifest, inventory(cache))
    try:
        shutil.copytree(cache, destination, copy_function=os.link)
    except OSError:                                               # another filesystem: fall back to a copy
        shutil.rmtree(destination, ignore_errors=True)
        shutil.copytree(cache, destination)
    return {"cache": str(cache.relative_to(ROOT)) if cache.is_relative_to(ROOT) else str(cache), "reused": fresh}


def digest_text(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def retain_bundle(source, destination):
    """Retain ordinary optional state; record links/special files without following them.

    Submissions still use strict copy_bundle. Optional scratch state is not part
    of the scientific envelope and must not prevent a submission being assessed.
    """
    import os
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    omitted = []
    if source.is_symlink() or not source.is_dir():
        omitted.append({"path": ".", "reason": "symlink" if source.is_symlink() else "not_directory",
                        **({"target": str(source.readlink())} if source.is_symlink() else {})})
        return {"omitted": omitted, "files": {}}
    for current, directories, files in os.walk(source, followlinks=False):
        current = Path(current)
        target = destination / current.relative_to(source)
        target.mkdir(parents=True, exist_ok=True)
        for name in list(directories) + files:
            path = current / name
            relative = str(path.relative_to(source))
            if path.is_symlink():
                omitted.append({"path": relative, "reason": "symlink", "target": str(path.readlink())})
                if name in directories:
                    directories.remove(name)
            elif path.is_file():
                shutil.copyfile(path, target / name)
            elif not path.is_dir():
                omitted.append({"path": relative, "reason": "special_file"})
    return {"omitted": omitted, "files": inventory(destination)}


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


def run(template, params, system, parent=None, level=1, supplied=(), judge=True, directions="full"):
    config_path = resolve_system(system)
    config = validate(config_path)
    if config["driver"]["kind"] == "command":
        for name in config["driver"].get("env", []):
            if name not in os.environ:
                raise ValueError(f"Missing controller environment variable: {name}")
    if level not in (1, 2) or (level == 2 and "level2" not in template.spec):
        raise ValueError("This template has no such level")
    supplied = sorted(set(supplied))
    unknown = [name for name in supplied if name not in template.spec.get("supplements", {})]
    if unknown:
        raise ValueError(f"This template has no supplement named {unknown[0]}")
    try:
        brief = template.brief(params, level, supplied)
    except (IndexError, KeyError, ValueError) as error:
        raise ValueError(f"Task brief could not be rendered: {error}") from error
    from .directions import apply as apply_directions
    published_brief = brief
    brief, _ = apply_directions(template.name, directions, published_brief, None)   # fails early on an unknown rung
    require_disk("start a run")
    preflight(config["runtime"]["image"])
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
                "parent": parent.name if parent else None, "supplied": supplied, "directions": directions, "status": "created",
                "created_at": datetime.now(timezone.utc).isoformat()}
    write(folder / "run.json", metadata)
    config, bundle = snapshot(config_path, folder / "system")
    write(folder / "system.json", config)
    write(folder / "substrate-manifest.json", bundle)

    task, work, inputs = folder / "task", folder / "work", folder / "inputs"
    for path in (task, work / "submission", work / "state", work / "prior", folder / "logs", folder / "controller"):
        path.mkdir(parents=True)
    envelope = (ROOT / "assessment/envelope.md").read_text()
    (task / "brief.md").write_text(brief)
    (task / "envelope.md").write_text(envelope)
    for supplement in supplied:                                   # an experimental condition: recorded, and part of what the agent saw
        shutil.copyfile(template.folder / template.spec["supplements"][supplement], task / template.spec["supplements"][supplement])
    metadata["inputs_staging"] = staged_inputs(template, params, inputs)
    if directions != "full":                                      # a directions rung: the practice sheet the agent sees is cut or withheld
        practice_path = inputs / "public/practice.md"
        practice = practice_path.read_text() if practice_path.is_file() else None
        _, practice = apply_directions(template.name, directions, published_brief, practice)   # the edits start from the published brief
        if practice is None:
            practice_path.unlink(missing_ok=True)
        else:
            practice_path.write_text(practice)
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
        sandbox_factory = getattr(template.hooks, "sandbox_factory", ToolSandbox)
        with sandbox_factory(config["runtime"]["image"], work, task, folder / "system", inputs,
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
    # Save the adapter result before optional retention or assessment can fail.
    write(folder / "controller/adapter-result.json", result)
    write(folder / "controller/sandbox.json", boundary)
    write(folder / "run.json", metadata)
    artifacts = copy_bundle(work / "submission", folder / "frozen")
    write(folder / "artifacts.json", artifacts)
    (folder / "retained").mkdir()
    retention = {area: retain_bundle(work / area, folder / "retained" / area) for area in ("state", "prior")}
    write(folder / "controller/retention.json", retention)
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

    try:
        assessment = _assess_run(template, folder, judge)
    finally:
        shutil.rmtree(work, ignore_errors=True)                   # frozen/ and retained/ hold everything the controller reads
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
    if "rubric" in assessment:
        from .rubric import markdown
        (folder / "review.md").write_text(markdown(assessment["rubric"], assessment))
        write(folder / "controller/rubric.json", assessment["rubric"])


class ReplayBudget:
    """An executor whose reruns get the system's per-command budget, the same limit the agent worked under.

    Until 13 October 2026 every controller rerun used the executors' built-in 120 seconds, a limit the agent was never
    told; a correct submission that took 151 seconds (the full-stack arm at the `no-streams` rung) failed its replay
    probes on that limit alone."""

    def __init__(self, inner, seconds):
        self.inner, self.seconds = inner, seconds

    def run(self, submission, inputs, argv, scratch, seconds=None):
        return self.inner.run(submission, inputs, argv, scratch, seconds=self.seconds if seconds is None else seconds)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def _assess_run(template, folder, judge=True):
    """Assess a run's frozen submission and keep the record under the fingerprint that produced it."""
    meta, config = read(folder / "run.json"), read(folder / "system.json")
    if inventory(folder / "frozen") != read(folder / "artifacts.json"):
        raise ValueError("Frozen submission changed")
    feedback = folder / "controller/feedback-public.json"
    executor = Docker(config["runtime"]["image"], config["runtime"]["memory"], config["runtime"]["cpus"])
    executor = getattr(template.hooks, "executor_factory", lambda value: value)(executor)
    executor = ReplayBudget(executor, (config.get("budget") or {}).get("command_seconds", 120))
    work = folder / "controller/assessment-work"
    with assessment_lock():
        require_disk("assess a run")
        shutil.rmtree(work, ignore_errors=True)
        try:
            assessment = assess(template, meta["instance"], folder / "frozen", executor, work, level=meta.get("level", 1),
                                feedback=read(feedback) if feedback.is_file() else None)
            evidence = getattr(template.hooks, "acquisition_evidence", None)
            if evidence is not None:
                assessment["acquisition"] = evidence(work, folder / "controller/acquisition-evidence" / uuid.uuid4().hex)
        finally:
            shutil.rmtree(work, ignore_errors=True)               # also when the assessment dies, so the next run is not starved
        assessment["sandbox"] = read(folder / "controller/provenance.json")["sandbox"]["state"]
        assessment["replay_budget_seconds"] = executor.seconds
        assessment["assessed_at"] = datetime.now(timezone.utc).isoformat()
        _trace_library_calls(template, folder, meta, config, executor)
    if judge:
        _judge(template, folder, assessment)
    _keep(folder, assessment)
    return assessment


def _trace_library_calls(template, folder, meta, config, executor):
    """Measure, after the assessment, which functions of the system's declared libraries the frozen command calls."""
    libraries = (config.get("substrate") or {}).get("libraries") or []
    if not libraries:
        return
    work = folder / "controller/library-calls-work"
    shutil.rmtree(work, ignore_errors=True)
    try:
        record = library_calls(template, meta["instance"], folder / "frozen", executor, work, libraries,
                               seconds=(config.get("budget") or {}).get("command_seconds", 120))
    except Exception as error:                                    # a measurement must never break the record
        record = {"libraries": libraries, "error": f"{type(error).__name__}: {str(error)[:800]}", "static": {}, "calls": {}, "replay": None}
    finally:
        shutil.rmtree(work, ignore_errors=True)
    write(folder / "controller/library-calls.json", record)
    provenance = read(folder / "controller/provenance.json")
    provenance["substrate_use"] = substrate_record(folder, config)
    write(folder / "controller/provenance.json", provenance)


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
                     "directions": meta.get("directions", "full"),
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
