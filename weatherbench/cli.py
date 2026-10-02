import argparse
import json

from .storage import ROOT, STATE, TASKS, read, write


def main():
    parser = argparse.ArgumentParser(description="Agent Weather Bench: tasks → systems → isolated runs → locked assessments")
    sub = parser.add_subparsers(dest="command",required=True)
    tasks = sub.add_parser("tasks"); t=tasks.add_subparsers(dest="action",required=True)
    for action in ("list","prepare","render"): t.add_parser(action)
    v=t.add_parser("validate"); v.add_argument("--output",default=str(STATE / "validation/task-packages.json"))
    v.add_argument("--metadata-only",action="store_true",help="Validate repository files without the separately distributed internal data bundle")
    check=t.add_parser("check"); check.add_argument("task"); check.add_argument("--submission",required=True); check.add_argument("--output")
    systems=sub.add_parser("systems"); s=systems.add_subparsers(dest="action",required=True)
    s.add_parser("list")
    i=s.add_parser("init"); i.add_argument("name"); i.add_argument("--image")
    c=s.add_parser("validate"); c.add_argument("system")
    for action in ("run","ingest"):
        r=sub.add_parser(action); r.add_argument("task"); r.add_argument("--system",required=True); r.add_argument("--parent")
        r.add_argument("--judge",choices=["auto-v1","none"],default="auto-v1",help="auto-v1 calls the pinned judge for structurally valid submissions; none makes no judge API call")
        if action=="ingest": r.add_argument("--submission",required=True)
    a=sub.add_parser("assess"); a.add_argument("run"); a.add_argument("--judge",choices=["auto-v1","none"],default="auto-v1"); a.add_argument("--retry",action="store_true")
    judge=sub.add_parser("judge"); j=judge.add_subparsers(dest="action",required=True)
    for action in ("lock","status"): j.add_parser(action)
    p=j.add_parser("packet"); p.add_argument("run")
    runs=sub.add_parser("runs"); rs=runs.add_subparsers(dest="action",required=True)
    for action in ("list","report"): rs.add_parser(action)
    show=rs.add_parser("show"); show.add_argument("run")
    suite=sub.add_parser("suite"); suite.add_argument("config"); suite.add_argument("--judge",choices=["auto-v1","none"],default="auto-v1")
    args=parser.parse_args()
    try:
        result=dispatch(args)
        if getattr(args,"output",None): write(args.output,result)
        print(json.dumps(result,indent=2,allow_nan=False))
    except (ValueError,RuntimeError,OSError,KeyError) as error:
        parser.exit(1,f"{type(error).__name__}: {error}\n")


def dispatch(args):
    if args.command=="tasks":
        from .task_tools.prepare import prepare
        from .task_tools.checks import validate_packages,check
        from .task_tools.render import render
        if args.action=="list": return [{"id":read(p)["id"],"title":read(p)["title"],"version":read(p)["version"],"inputs":read(p)["input_contract"]["mode"]} for p in sorted(TASKS.glob("*/task.yaml"))]
        if args.action=="prepare": return prepare()
        if args.action=="render": return render()
        if args.action=="validate": return validate_packages(metadata_only=args.metadata_only)
        return check(args.task,args.submission)
    if args.command=="systems":
        from .systems import init,validate,resolve_system
        if args.action=="list": return [{"system":str(p),"id":read(p)["id"],"kind":read(p)["kind"],"driver":read(p)["driver"]["kind"]} for p in sorted((ROOT / "systems").glob("*/system.yaml"))]
        if args.action=="init": return init(args.name,**({"image":args.image} if args.image else {}))
        return validate(resolve_system(args.system))
    if args.command in ("run","ingest"):
        from .runner import run_task
        return run_task(args.task,args.system,parent=args.parent,judge=args.judge,submission=getattr(args,"submission",None))
    if args.command=="assess":
        from .judge import assess
        return assess(args.run,judge=args.judge,retry=args.retry)
    if args.command=="judge":
        from .judge import create_lock,verify_lock
        if args.action=="lock": return create_lock()
        if args.action=="status": return verify_lock()
        from .runner import resolve_run
        from .judge import assess
        run=resolve_run(args.run)
        result=assess(run,judge="none")
        return {"packet":result["assessment_directory"]+"/judge-packet.json"}
    if args.command=="runs":
        from .report import list_runs,report
        if args.action=="list": return list_runs()
        if args.action=="report": return report()
        from .runner import resolve_run
        return read(resolve_run(args.run) / "run.json")
    if args.command=="suite":
        from .runner import suite
        return suite(args.config,judge=args.judge)
