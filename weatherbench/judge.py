"""A locked evidence contract; model prose cannot override controller failures."""
import base64
import json
import uuid
from importlib.metadata import version
from pathlib import Path

from .storage import ROOT, STATE, TASKS, digest, inventory, read, write
from .task_tools.checks import leaves

CONFIG = ROOT / "judges/auto-v1.yaml"
LOCK = ROOT / "judges/auto-v1.lock.json"
PROMPT = ROOT / "judges/system-v1.md"


def lock_files():
    paths = [CONFIG,PROMPT,ROOT / "requirements-controller.lock",ROOT / "pyproject.toml"]
    paths += sorted((ROOT / "weatherbench").rglob("*.py"))
    for folder in sorted(TASKS.iterdir()):
        if folder.is_dir(): paths += sorted(p for p in folder.iterdir() if p.suffix in (".yaml",".json",".md"))
        if (folder / "source-material").is_dir(): paths += sorted(p for p in (folder / "source-material").rglob("*") if p.is_file())
    paths += [TASKS / "provenance-contract.md",TASKS / "replay-contract.md"]
    return {str(path.relative_to(ROOT)):digest(path) for path in paths}


def dependency_versions():
    result = {}
    for line in (ROOT / "requirements-controller.lock").read_text().splitlines():
        if "==" not in line or line.startswith("#"): continue
        name,pinned = line.strip().split("==",1)
        installed = version(name)
        if installed != pinned:
            raise ValueError(f"Controller dependency drift: {name} requires {pinned}, installed {installed}")
        result[name] = installed
    return result


def lock_identity(files,dependencies):
    from hashlib import sha256
    return sha256(json.dumps({"files":files,"dependencies":dependencies},sort_keys=True).encode()).hexdigest()


def create_lock():
    config = read(CONFIG)
    files = lock_files()
    dependencies = dependency_versions()
    identity = lock_identity(files,dependencies)
    value = {"schema_version":1,"judge":config["id"],"model":config["model"]["model"],"files":files,"dependencies":dependencies,"fingerprint":identity}
    write(LOCK,value)
    return value


def verify_lock():
    if not LOCK.is_file(): raise ValueError("Create the judge lock with 'weather-bench judge lock' before running")
    lock = read(LOCK)
    fingerprint = lock_identity(lock["files"],lock.get("dependencies",{}))
    if lock["fingerprint"]!=fingerprint or lock["model"]!=read(CONFIG)["model"]["model"]:
        raise ValueError("Judge lock identity is invalid")
    if lock["files"]!=lock_files():
        raise ValueError("Judge/task/evaluator files changed after locking. Version and review the changes, then explicitly regenerate the lock; existing assessments retain their fingerprint.")
    if lock["dependencies"] != dependency_versions(): raise ValueError("Controller dependency environment changed")
    return lock


def packet(run,evaluation):
    rubric = read(run / "task/rubric.yaml")
    outcomes = [leaf for leaf,_ in leaves(rubric["tree"]) if leaf["evaluator"]!="deterministic"]
    evidence = {"controller:static":evaluation["static"],"controller:replay":evaluation["replay"],
                "controller:prediction":evaluation["prediction"],"controller:integrity":evaluation["integrity"],
                "controller:forecast_outcomes":evaluation["forecast_outcomes"]}
    if (run / "task/sources.yaml").is_file(): evidence["controller:source_record"] = read(run / "task/sources.yaml")
    remaining = read(CONFIG)["packet"]["max_text_characters"]
    image = None
    files = inventory(run / "frozen")
    priority = ("report.txt","answer.json","provenance.json","execution.json","handoff.txt")
    names = list(priority) + [name for name in files if name not in priority and Path(name).suffix in (".py",".sh",".R",".r",".jl",".js",".ts",".json",".yaml",".yml",".txt",".md",".toml")]
    for name in names:
        path = run / "frozen" / name
        if not path.is_file(): continue
        text = path.read_text(errors="replace")
        limit = min(read(CONFIG)["packet"]["max_file_characters"],max(0,remaining))
        evidence["file:"+name] = {"text":text[:limit],"truncated":len(text)>limit,"sha256":files[name]["sha256"],"characters_included":min(len(text),limit)}
        remaining -= min(len(text),limit)
    figure = run / "frozen/outlook.png"
    if figure.is_file() and figure.stat().st_size<=4_000_000:
        try:
            from PIL import Image
            with Image.open(figure) as img:
                if img.format!="PNG" or img.width*img.height>16_000_000: raise ValueError("Invalid figure size/type")
                img.verify()
            image = base64.b64encode(figure.read_bytes()).decode()
            evidence["figure:outlook.png"] = {"verified_png":True,"sha256":digest(figure)}
        except Exception:
            evidence["figure:outlook.png"] = {"verified_png":False,"reason":"Figure could not be inspected as a valid bounded PNG"}
    return {"schema_version":1,"task_prompt":(run / "task/prompt.md").read_text(),"criteria":outcomes,
            "provenance_contract":(run / "task/provenance-contract.md").read_text(),"execution_contract":(run / "task/replay-contract.md").read_text(),
            "evidence":evidence,"identity_blinding":"System/model/cost/parent labels omitted; source text may mention libraries."},image


def validate_judgment(value,payload):
    expected = {leaf["id"]:leaf for leaf in payload["criteria"]}
    if not isinstance(value,dict) or set(value.get("ratings",{}))!=set(expected): raise ValueError("Judge must rate exactly the packet's criteria")
    ids = set(payload["evidence"])
    for name,row in value["ratings"].items():
        if not isinstance(row,dict): raise ValueError("Rating must be an object")
        score = row.get("score")
        if score is not None and (type(score) is not int or score not in (0,1,2)): raise ValueError("Score must be 0, 1, 2 or null")
        if not isinstance(row.get("reason"),str) or not row["reason"].strip() or not isinstance(row.get("uncertainty"),str): raise ValueError("Rating needs reason and uncertainty")
        refs = row.get("evidence")
        if not isinstance(refs,list) or not refs or not all(isinstance(ref,str) and ref in ids for ref in refs): raise ValueError("Unknown or missing evidence citation")
        if score==2:
            if not any(ref.startswith("file:") and not payload["evidence"][ref]["truncated"] for ref in refs):
                raise ValueError("Full scientific credit requires a complete cited submission artifact")
            if "outlook.png" in expected[name]["evidence"] and ("figure:outlook.png" not in refs or not payload["evidence"].get("figure:outlook.png",{}).get("verified_png")):
                raise ValueError("Full figure/interpretation credit requires a verified cited figure")
    if not isinstance(value.get("summary"),str) or not isinstance(value.get("concerns"),list) or not all(isinstance(x,str) for x in value["concerns"]): raise ValueError("Invalid judgment summary/concerns")
    return value


def aggregate(rubric,evaluation,judgment=None):
    ratings = judgment["ratings"] if judgment else {}
    outcomes,lower,upper = {},0.,0.
    for leaf,weight in leaves(rubric["tree"]):
        known = evaluation["static"]["leaves"][leaf["id"]]["state"]
        requirements = []
        if leaf["id"]=="reusable_workflow":
            requirements.append(evaluation["replay"]["state"])
            if rubric["task"]=="seasonal-calibration": requirements.append(evaluation["prediction"]["state"])
        if leaf["id"]=="data_acquisition": requirements.append(evaluation["acquisition"]["state"])
        model_score = ratings.get(leaf["id"],{}).get("score")
        if known=="fail" or "fail" in requirements: state,score="fail",0.
        elif leaf["evaluator"]=="deterministic":
            state,score=("pass",1.) if known=="pass" else ("unresolved",None)
        elif "unresolved" in requirements or model_score is None: state,score="unresolved",None
        else: score=model_score/2; state="pass" if score==1 else "fail"
        outcomes[leaf["id"]] = {"state":state,"fractional_score":score,"weight":weight,"judge_rating":ratings.get(leaf["id"])}
        if score is not None: lower += score*weight; upper += score*weight
        else: upper += weight
    basic = evaluation["static"]["basic_validity"]
    integrity = evaluation["integrity"].get("state","unresolved")
    failure = any(row["state"]=="fail" for row in basic.values()) or any(row["state"]=="fail" for row in outcomes.values())
    pending = integrity!="pass" or any(row["state"]!="pass" for row in basic.values()) or any(row["state"]=="unresolved" for row in outcomes.values())
    if integrity=="fail": completion="failed_integrity"
    elif failure: completion="partial" if lower>0 else "failed"
    elif pending: completion="pending"
    else: completion="complete"
    return {"completion":completion,"score_bounds":[round(100*lower,8),round(100*upper,8)],"outcomes":outcomes,"basic_validity":basic,
            "integrity":evaluation["integrity"],"forecast_outcomes":evaluation["forecast_outcomes"],"scientific_skill_gate":False}


def assess(run,judge="auto-v1",retry=False):
    from .evaluation import evaluate
    from .runner import resolve_run, reference_integrity
    run = resolve_run(run)
    lock = verify_lock()
    meta = read(run / "run.json")
    if inventory(run / "frozen")!=read(run / "artifacts.json"): raise ValueError("Frozen submission changed")
    if inventory(run / "system")!=read(run / "substrate-manifest.json"): raise ValueError("Pinned system substrate changed")
    reference_integrity(meta["task"])
    if inventory(run / "task")!=read(run / "task-manifest.json"): raise ValueError("Frozen task snapshot changed")
    for name in ("task.yaml","prompt.md","rubric.yaml","input-manifest.json"):
        if digest(run / "task" / name)!=digest(TASKS / meta["task"] / name): raise ValueError("Run task differs from locked current task")
    if judge not in ("auto-v1","none"): raise ValueError("The locked judge is auto-v1; none is an explicit numeric-only assessment")
    key = lock["fingerprint"][:16]+"-"+judge
    directory = run / "controller/assessments" / key
    if directory.exists() and not retry:
        cached = read(directory / "assessment.json")
        write(run / "assessment.json",cached)
        return cached
    if retry: directory=directory.with_name(key+"-retry-"+uuid.uuid4().hex[:6])
    directory.mkdir(parents=True,exist_ok=False)
    evaluation = evaluate(run,directory)
    write(directory / "evaluation.json",evaluation)
    payload,image = packet(run,evaluation)
    write(directory / "judge-packet.json",payload)
    judgment,error,usage = None,None,None
    # Structural failure already prevents completion; do not pay to judge an invalid packet.
    valid = all(row["state"]=="pass" for row in evaluation["static"]["basic_validity"].values())
    if judge=="auto-v1" and valid:
        from .model import Model
        model = None
        try:
            model = Model(read(CONFIG)["model"])
            content = [{"type":"text","text":json.dumps(payload)}]
            if image: content.append({"type":"image","source":{"type":"base64","media_type":"image/png","data":image}})
            raw = model.call(PROMPT.read_text(),[{"role":"user","content":content}])
            write(directory / "judge-raw.json",raw)
            if raw["stop_reason"]!="end_turn": raise ValueError("Incomplete judge response")
            text = "".join(block["text"] for block in raw["content"] if block["type"]=="text")
            judgment = validate_judgment(json.loads(text),payload)
            write(directory / "judgment.json",judgment)
        except Exception as exc: error=f"{type(exc).__name__}: {str(exc)[:1000]}"
        finally:
            if model: usage=model.usage; model.close()
    result = aggregate(read(run / "task/rubric.yaml"),evaluation,judgment)
    result.update(schema_version=1,run=run.name,judge=judge,judge_fingerprint=lock["fingerprint"],judge_model=lock["model"] if judge!="none" else None,
                  judge_error=error,judge_usage=usage,judge_packet_sha256=digest(directory / "judge-packet.json"),
                  assessment_directory=str(directory),benchmark_eligible=meta["kind"]=="agent" and all(meta["task_approvals"].get(k) is True for k in ("scientific_approval","scoring_approval","redistribution_approval")))
    write(directory / "assessment.json",result)
    write(directory / "judge-lock.json",lock)
    # This convenience pointer is replaceable; every assessment and raw response remains immutable.
    write(run / "assessment.json",result)
    return result
