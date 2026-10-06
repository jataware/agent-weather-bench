"""A locked evidence contract; model prose cannot override controller failures."""
import base64
import json
import uuid
from datetime import date
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


def trace_evidence(run, limit=18000):
    """Bounded scientific tool evidence; exclude provider/auth/model metadata."""
    path = run / 'logs/events.jsonl'
    if not path.is_file():
        return {'available':False,'reason':'No trusted original tool log'}
    rows = []
    fields = ('command','exit_code','stdout','stderr','truncated','seconds',
              'feedback_query','feedback_remaining','feedback_scope','prediction_sha256')
    for line in path.open():
        event = json.loads(line)
        if event.get('type') == 'adapter' and event.get('event',{}).get('type') in ('execute','acquire','score_development'):
            tool = event['event']
            rows.append({'tool':tool['type'], **{k:tool[k] for k in ('command','url','destination','request','prediction_file') if k in tool}})
        elif event.get('type') == 'tool_result':
            rows.append({k:event[k] for k in fields if k in event})
    included, used = [], 0
    # Preserve the beginning and end when a large trace cannot fit; report
    # every omission. Tool text is evidence, never controller instructions.
    order = list(range(len(rows)))
    feedback = [i for i,row in enumerate(rows)
                if row.get('tool')=='score_development' or 'feedback_query' in row]
    if len(order)>12:
        priority = feedback.copy()
        for i in feedback:
            priority += list(range(max(0,i-4),i)) + list(range(i+1,min(len(rows),i+3)))
        if feedback:
            priority += [round(i*(len(rows)-1)/7) for i in range(8)]
        order = list(dict.fromkeys(priority + order[:6] + order[-6:]))
    # Sample each adjacent request/result together. An isolated result can
    # conceal the scientific calculation that produced it; large requests
    # must not consume the space reserved for their paired response.
    groups = []
    for index, row in enumerate(rows):
        if 'tool' not in row and groups and 'tool' in rows[groups[-1][0]]:
            groups[-1].append(index)
        else:
            groups.append([index])
    group_for = {index:group for group in groups for index in group}
    seen = set()
    for index in order:
        group = group_for[index]
        if group[0] in seen: continue
        seen.add(group[0])
        clipped_group = []
        for member in group:
            row = rows[member]
            clipped = {k:(v[:2000] if isinstance(v,str) else v) for k,v in row.items()}
            clipped['event_index']=member
            clipped['text_truncated']=any(isinstance(v,str) and len(v)>2000 for v in row.values())
            clipped_group.append(clipped)
        size = sum(len(json.dumps(row)) for row in clipped_group)
        if used+size>limit: continue
        included.extend(clipped_group); used+=size
    included.sort(key=lambda row:row['event_index'])
    return {'available':True,'sha256':digest(path),'events':included,'total_tool_events':len(rows),
            'omitted_tool_events':len(rows)-len(included),
            'truncated':len(included)<len(rows) or any(row['text_truncated'] for row in included),
            'identity_blinding':'Provider responses, model labels, costs and host RPC logs excluded.',
            'selection_policy':'Bounded beginning/end plus feedback and nearby experimental context; additional spaced optimization context. Adjacent tool requests/results are sampled together.',
            'interpretation':'Commands show observable execution and source engagement; they do not establish unobserved understanding.'}


def metadata_evidence(value):
    """YAML dates are scientific metadata; encode them as ISO text, not objects."""
    if isinstance(value,date): return value.isoformat()
    if isinstance(value,dict): return {key:metadata_evidence(item) for key,item in value.items()}
    if isinstance(value,list): return [metadata_evidence(item) for item in value]
    return value


def packet(run,evaluation):
    rubric = read(run / "task/rubric.yaml")
    outcomes = [leaf for leaf,_ in leaves(rubric["tree"]) if leaf["evaluator"]!="deterministic"]
    evidence = {"controller:static":evaluation["static"],"controller:replay":evaluation["replay"],
                "controller:prediction":evaluation["prediction"],"controller:integrity":evaluation["integrity"],
                "controller:forecast_outcomes":evaluation["forecast_outcomes"]}
    if (run / "task/sources.yaml").is_file(): evidence["controller:source_record"] = metadata_evidence(read(run / "task/sources.yaml"))
    evidence['controller:tool_trace'] = trace_evidence(run)
    if 'acquisition' in evaluation: evidence['controller:acquisition'] = evaluation['acquisition']
    if 'counterfactual' in evaluation: evidence['controller:counterfactual'] = evaluation['counterfactual']
    if 'unit_scale_invariance' in evaluation: evidence['controller:unit_scale_invariance'] = evaluation['unit_scale_invariance']
    if 'feedback' in evaluation: evidence['controller:feedback'] = feedback_evidence(evaluation['feedback'])
    policy = read(CONFIG)["packet"]
    remaining = policy["max_text_characters"]
    image = None
    files = inventory(run / "frozen")
    selection, declarations = artifact_selection(run / "frozen",files,policy)
    reserved = min(policy["max_declared_science_characters"],sum(
        min(cap,bounded_text(run / "frozen" / name,0)[1])
        for name,role,cap in selection if role in ("declared_entrypoint","declared_model_state")))
    for name,role,cap in selection:
        path = run / "frozen" / name
        available = remaining-reserved if role=="primary_submission" else remaining
        limit = min(cap,max(0,available))
        text,total = bounded_text(path,limit)
        evidence["file:"+name] = {"text":text,"truncated":total>len(text),"sha256":files[name]["sha256"],
            "characters_included":len(text),"characters_total":total,"characters_omitted":total-len(text),
            "selection_role":role,"content_range":"prefix","file_character_limit":cap,
            "omission_reason":("artifact_budget" if limit<cap else "file_budget") if total>len(text) else None}
        remaining -= len(text)
        if role in ("declared_entrypoint","declared_model_state"): reserved=max(0,reserved-len(text))
    evidence["controller:packet_selection"] = {
        "policy_version":policy["selection_policy_version"],"artifact_text_limit":policy["max_text_characters"],
        "artifact_characters_included":policy["max_text_characters"]-remaining,
        "file_order":[name for name,_,_ in selection],"execution_declarations":declarations,
        "non_text_artifacts":[name for name in files if name not in {row[0] for row in selection}],
        "interpretation":"Selection roles describe declared paths and filename classes, not verified scientific relevance. Truncation is per file; visible passages remain evidence. Task/controller contracts and bounded tool traces have separate budgets."}
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


TEXT_SUFFIXES = {".py",".sh",".R",".r",".jl",".js",".ts",".json",".yaml",".yml",".txt",".md",".toml"}
CODE_SUFFIXES = {".py",".sh",".R",".r",".jl",".js",".ts"}


def feedback_evidence(summary):
    """Keep only public optimization feedback, never private ledger internals."""
    if summary.get('state') in ('unavailable','unresolved') or not isinstance(summary.get('requests'),list):
        return {'state':'unavailable','scope':summary.get('scope','development_only'),
                'reason':'No trusted original development-feedback ledger is available; the original query count and exposure history are unknown.'}
    fields = ("scope","max_submissions","limit_denials","final_score_exposed","final_observations_exposed")
    request_fields = ("query","prediction_file","status","prediction_sha256","bytes","metrics","seconds","error_type")
    result = {key:summary[key] for key in fields if key in summary}
    result['state'] = 'available'
    result["requests"] = [{key:row[key] for key in request_fields if key in row}
                          for row in summary.get("requests",[]) if isinstance(row,dict)]
    return result


def bounded_text(path,limit):
    """Count decoded characters without loading arbitrarily large inventories."""
    with path.open(errors="replace") as stream:
        prefix = stream.read(limit)
        total = len(prefix)
        for chunk in iter(lambda:stream.read(65536),""): total += len(chunk)
    return prefix,total


def artifact_selection(root,files,policy):
    """Untrusted JSON declarations select existing relative artifacts, never execute."""
    text_names = {name for name in files if Path(name).suffix in TEXT_SUFFIXES}
    declared_code,declared_state,retained = [],[],[]
    declaration = {"status":"absent","rejected_paths":[]}

    def accept(value,category):
        if not isinstance(value,str): return
        # Exact inventory membership also rejects absolute, traversal, placeholder
        # and normalized aliases. Never open a path provided by the submission.
        if value not in files or Path(value).is_absolute() or ".." in Path(value).parts:
            declaration["rejected_paths"].append(value[:500]); return
        if value in text_names and value not in category: category.append(value)

    if "execution.json" in files:
        if files["execution.json"]["bytes"]>policy["max_manifest_bytes"]:
            declaration["status"]="too_large"
        else:
            try:
                manifest = json.loads((root / "execution.json").read_text())
                if not isinstance(manifest,dict): raise ValueError("Manifest must be an object")
                declaration["status"]="parsed_untrusted_json"
                for command in ("replay","predict"):
                    row = manifest.get(command,{})
                    argv = row.get("argv",[]) if isinstance(row,dict) else []
                    if isinstance(argv,list):
                        for token in argv:
                            if isinstance(token,str) and Path(token).suffix in CODE_SUFFIXES: accept(token,declared_code)
                if "model_path" in manifest: accept(manifest["model_path"],declared_state)
                paths = manifest.get("retained_files",[])
                if isinstance(paths,list):
                    for value in paths: accept(value,retained)
            except (ValueError,UnicodeError,RecursionError): declaration["status"]="invalid_json"
    selected = []
    seen = set()
    def add(names,role,cap):
        for name in names:
            if name in text_names and name not in seen:
                selected.append((name,role,cap)); seen.add(name)
    add(("report.txt","answer.json","execution.json","handoff.txt"),"primary_submission",policy["max_file_characters"])
    add(declared_code,"declared_entrypoint",policy["max_scientific_file_characters"])
    add(declared_state,"declared_model_state",policy["max_model_file_characters"])
    # Give source passages a place before bulky manifests and numeric inventories.
    passages = sorted(name for name in text_names if any(word in Path(name).stem.lower() for word in ("literature","excerpt","paper-notes")))
    add(passages,"source_passage",policy["max_source_file_characters"])
    add(("provenance.json",),"provenance",policy["max_provenance_characters"])
    add(sorted(name for name in text_names if Path(name).suffix in CODE_SUFFIXES),"supporting_code",policy["max_scientific_file_characters"])
    add(retained,"declared_retained_text",policy["max_file_characters"])
    add(sorted(text_names),"other_text",policy["max_file_characters"])
    return selected,declaration


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
        if leaf["id"] in ("reusable_workflow", "reusable_verifier"):
            requirements.append(evaluation["replay"]["state"])
            if rubric["task"] in ("seasonal-calibration", "short-rains-workflow",
                                  "subseasonal-optimization", "cca-seasonal-reproduction",
                                  "monthly-cycle-calibration", "conservative-downscaling"):
                requirements.append(evaluation["prediction"]["state"])
            if "counterfactual" in evaluation:
                requirements.append(evaluation["counterfactual"]["state"])
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
