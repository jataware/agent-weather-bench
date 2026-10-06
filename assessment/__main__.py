"""Command line for task templates: python -m assessment <command>."""
import argparse
import json
import tempfile
from pathlib import Path

from .spec import ROOT, Template, templates


def _executor(args):
    from .execute import Docker, Local
    if getattr(args, "local_trusted", False):
        return Local()
    from weatherbench.systems import DEFAULT_IMAGE
    return Docker(args.image or DEFAULT_IMAGE)


def main():
    parser = argparse.ArgumentParser(prog="python -m assessment", description="Task templates: prepare, certify, assess, run")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("templates")
    prepare = sub.add_parser("prepare"); prepare.add_argument("template"); prepare.add_argument("--source", help="Directory holding the frozen source archives")
    sub.add_parser("instances").add_argument("template")
    brief = sub.add_parser("brief"); brief.add_argument("template"); brief.add_argument("instance"); brief.add_argument("--level", type=int, choices=[1, 2], default=1)
    certify = sub.add_parser("certify"); certify.add_argument("template"); certify.add_argument("--full", action="store_true", help="Compare the reference implementations on every instance")
    assess = sub.add_parser("assess"); assess.add_argument("template"); assess.add_argument("instance"); assess.add_argument("submission")
    run = sub.add_parser("run"); run.add_argument("template"); run.add_argument("instance"); run.add_argument("--system", required=True); run.add_argument("--parent"); run.add_argument("--level", type=int, choices=[1, 2], default=1)
    sub.add_parser("runs")
    sub.add_parser("reassess").add_argument("run")
    sub.add_parser("attempts").add_argument("template")
    for command in (certify, assess):
        command.add_argument("--local-trusted", action="store_true", help="Run without Docker. Only for the controller's own control solutions.")
        command.add_argument("--image")
    args = parser.parse_args()
    try:
        print(json.dumps(dispatch(args), indent=2, default=str))
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        parser.exit(1, f"{type(error).__name__}: {error}\n")


def dispatch(args):
    if args.command == "templates":
        return [{"template": name, "mode": Template(name).spec["mode"], "spec_version": Template(name).spec["spec_version"]} for name in templates()]
    if args.command == "runs":
        from .runner import list_runs
        return list_runs()
    if args.command == "reassess":
        from .runner import reassess
        return reassess(args.run)
    template = Template(args.template)
    if args.command == "attempts":
        from .certify import record_attempts
        return record_attempts(template)
    if args.command == "prepare":
        return template.hooks.prepare(template.private, args.source)
    if args.command == "instances":
        development = {row["id"] for row in template.development_instances()}
        return [{"id": row["id"], "development": row["id"] in development} for row in template.hooks.candidate_instances()]
    if args.command == "brief":
        text = template.brief(template.instance(args.instance), args.level)
        return {"brief": text, "words": len(text.split())}
    if args.command == "certify":
        from .certify import certify
        report = certify(template, _executor(args), full=args.full)
        return {"automatic_tests_passed": report["automatic_tests_passed"], "certified": report["certified"],
                "tests": {name: test["passed"] for name, test in report["tests"].items()},
                "record": str((template.folder / "certification.json").relative_to(ROOT))}
    if args.command == "assess":
        from .assess import assess
        with tempfile.TemporaryDirectory(prefix="assessment-") as scratch:
            return assess(template, template.instance(args.instance), Path(args.submission), _executor(args), Path(scratch) / "work")
    if args.command == "run":
        from .runner import run
        return run(template, template.instance(args.instance), args.system, parent=args.parent, level=args.level)


if __name__ == "__main__":
    main()
