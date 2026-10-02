"""One run layout for fresh attempts, retained substrates and imported submissions."""
import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import adapters
from .runtime import ToolSandbox, preflight
from .storage import ROOT, STATE, PRIVATE, digest, inventory, copy_bundle, read, write, task_path
from .systems import resolve_system, snapshot, validate


def new_run(task, system):
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + task + "-" + system + "-" + uuid.uuid4().hex[:6]
    path = STATE / "runs" / name
    path.mkdir(parents=True, exist_ok=False)
    return path


def task_snapshot(task, run):
    folder = task_path(task)
    target = run / "task"
    target.mkdir()
    names = ["task.yaml","prompt.md","rubric.yaml","input-manifest.json","sources.yaml"]
    spec = read(folder / "task.yaml")
    if "source_plan" in spec: names.append(spec["source_plan"])
    for name in names: shutil.copyfile(folder / name,target / name)
    for name in spec["artifact_contracts"].values(): shutil.copyfile(folder / name,target / Path(name).name)
    return spec, inventory(target)


def reference_integrity(task):
    manifest = read(task_path(task) / "input-manifest.json")
    for row in manifest["files"]:
        if digest(PRIVATE / task / row["file"]) != row["sha256"]:
            raise ValueError("Controller reference/input snapshot changed; prepare and review a new task version")


def run_task(task, system, parent=None, judge="auto-v1", submission=None):
    from .judge import verify_lock, assess
    folder = task_path(task)
    config_path = resolve_system(system)
    config = validate(config_path)
    spec = read(folder / "task.yaml")
    verify_lock()
    reference_integrity(task)
    if not submission and spec["input_contract"]["mode"] != "supplied_inputs":
        raise ValueError("This task's acquisition runtime is pending preflight. Its source plan can be exported; normalized controller fixtures will not be supplied as an acquisition substitute.")
    if not submission: preflight(config["runtime"]["image"])
    if parent:
        parent = resolve_run(parent)
        meta = read(parent / "run.json")
        if meta["system_sha256"] != digest(config_path):
            raise ValueError("Retained/reset comparisons require the same system definition")
        if inventory(parent / "retained") != read(parent / "retained-manifest.json"):
            raise ValueError("Parent retained artifacts changed")
    run = new_run(task,config["id"])
    metadata = {"schema_version":1,"id":run.name,"task":task,"task_version":spec["version"],"system":config["id"],
                "kind":config["kind"],"system_sha256":digest(config_path),"runtime_image":config["runtime"]["image"],
                "parent":parent.name if parent else None,"status":"created","study_type":"development",
                "created_at":datetime.now(timezone.utc).isoformat(),"task_approvals":spec["review"]}
    write(run / "run.json",metadata)
    config, bundle = snapshot(config_path,run / "system")
    if parent and bundle != read(parent / "substrate-manifest.json"):
        raise ValueError("System substrate changed between parent and child")
    shutil.copyfile(config_path,run / "system.yaml")
    write(run / "system.json",config); write(run / "substrate-manifest.json",bundle)
    spec, task_files = task_snapshot(task,run)
    write(run / "task-manifest.json",task_files)
    work, inputs = run / "work", run / "inputs"
    for path in (work / "submission",work / "state",work / "prior",inputs,run / "controller",run / "logs"): path.mkdir(parents=True,exist_ok=True)
    if parent:
        shutil.copytree(parent / "retained/state",work / "state",dirs_exist_ok=True)
        shutil.copytree(parent / "retained/prior",work / "prior",dirs_exist_ok=True)
        copy_bundle(parent / "frozen",work / "prior" / parent.name)
    if not submission:
        for row in read(folder / "input-manifest.json")["files"]:
            if row["visibility"]=="agent": shutil.copyfile(PRIVATE / task / row["file"],inputs / Path(row["file"]).name)
    write(run / "input-manifest.json",inventory(inputs))
    request = {"schema_version":1,"type":"start","task":task,"prompt":(folder / "prompt.md").read_text(),
               "contracts":{key:(folder / path).read_text() for key,path in spec["artifact_contracts"].items()},
               "paths":{"work":"/work","inputs":"/work/inputs","submission":"/work/submission","state":"/work/state","prior":"/work/prior","substrate":"/substrate"},
               "substrate_instructions":config.get("substrate",{}).get("instructions",""),"budget":config["budget"],
               "retained_files":inventory(work / "prior"),"protocol":"execute / tool_result / usage / final as JSON lines"}
    write(run / "request.json",request)
    # Controller metadata, credentials, reference data and assessments stay outside all tool mounts.
    result = {"status":"imported","usage":None,"usage_source":"unknown","tool_calls":0,"seconds":0}
    integrity = {"passed":False,"state":"unresolved","reason":"Imported artifacts have no trusted original-execution boundary evidence"}
    if submission:
        inventory(submission)
        shutil.copytree(submission,work / "submission",dirs_exist_ok=True)
    else:
        started = time.monotonic()
        try:
            with ToolSandbox(config["runtime"]["image"],work,run / "task",run / "system",inputs,
                             memory=config["runtime"]["memory"],cpus=config["runtime"]["cpus"]) as box:
                driver = adapters.command_driver if config["driver"]["kind"]=="command" else adapters.anthropic_driver
                result = driver(config,run / "system",request,box,run / "logs/events.jsonl",run / "logs/driver.stderr") if config["driver"]["kind"]=="command" else driver(config,request,box,run / "logs/events.jsonl")
                integrity = box.inspect()
                integrity["state"]="pass"
        except Exception as error:
            result = {"status":"execution_error","reason":str(error)[:1500],"usage":None,"usage_source":"unknown","seconds":time.monotonic()-started,"tool_calls":None}
    try:
        if inventory(run / "system") != bundle:
            raise ValueError("Pinned controller adapter/substrate changed during execution")
        artifacts = copy_bundle(work / "submission",run / "frozen")
        write(run / "artifacts.json",artifacts)
        retained = run / "retained"
        retained.mkdir()
        copy_bundle(work / "state",retained / "state")
        copy_bundle(work / "prior",retained / "prior")
        write(run / "retained-manifest.json",inventory(retained))
    except ValueError as error:
        integrity = {"passed":False,"state":"fail","reason":str(error)}
        result["status"]="invalid_artifacts"
    write(run / "controller/integrity.json",integrity)
    metadata.update(result)
    metadata["input_snapshot_unchanged"] = inventory(inputs)==read(run / "input-manifest.json")
    if not metadata["input_snapshot_unchanged"]: integrity.update(passed=False,state="fail",reason="Input snapshot mutated")
    write(run / "controller/integrity.json",integrity)
    write(run / "run.json",metadata)
    if (run / "artifacts.json").exists(): assess(run,judge=judge)
    return {"run":run.name,"directory":str(run),"status":metadata["status"],
            "assessment":str(run / "assessment.json") if (run / "assessment.json").is_file() else None}


def resolve_run(value):
    path = Path(value)
    if not path.is_dir(): path = STATE / "runs" / value
    if not (path / "run.json").is_file(): raise ValueError("Expected a run ID or run directory")
    return path.resolve()


def suite(config_path,judge="auto-v1"):
    from .judge import verify_lock
    config = read(config_path)
    system = config["system"]
    if config["condition"] not in ("reset","retained"): raise ValueError("Condition must be reset or retained")
    if not isinstance(config.get("tasks"),list) or not config["tasks"]: raise ValueError("Suite needs a nonempty task list")
    system_config = validate(resolve_system(system))
    verify_lock()
    preflight(system_config["runtime"]["image"])
    # Validate all tasks before any paid attempts; mixed-ready suites must not partially launch.
    for task in config["tasks"]:
        spec = read(task_path(task) / "task.yaml")
        if spec["input_contract"]["mode"] != "supplied_inputs": raise ValueError(f"Acquisition runtime not ready for {task}")
        reference_integrity(task)
    target = STATE / "suites" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:6])
    target.mkdir(parents=True)
    write(target / "suite.json",{"config":config,"steps":[],"status":"started"})
    steps,parent = [],None
    stopped = False
    for task in config["tasks"]:
        try:
            result = run_task(task,system,parent=parent if config["condition"]=="retained" else None,judge=judge)
            result["task"] = task
            path = resolve_run(result["run"])
            if (path / "retained-manifest.json").is_file(): parent=result["run"]
            failed = result["status"] not in ("submitted","imported")
        except Exception as error:
            result = {"task":task,"status":"harness_error","reason":f"{type(error).__name__}: {str(error)[:1500]}"}
            failed = True
        steps.append(result)
        write(target / "suite.json",{"config":config,"steps":steps,"status":"running"})
        if failed and not config.get("continue_after_failure",False):
            stopped = True
            break
    write(target / "suite.json",{"config":config,"steps":steps,"status":"stopped_after_failure" if stopped else "finished"})
    return {"suite":str(target),"steps":steps}
