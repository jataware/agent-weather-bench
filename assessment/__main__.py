"""Command line for task templates: python -m assessment <command>."""
import argparse
import json
import tempfile
from pathlib import Path

from .spec import ROOT, Template, templates


def _executor(args, template=None):
    from .execute import Docker, Local
    if getattr(args, "local_trusted", False):
        executor = Local()
    else:
        from .systems import DEFAULT_IMAGE
        executor = Docker(args.image or DEFAULT_IMAGE)
    factory = getattr(template.hooks, "executor_factory", lambda value: value) if template else lambda value: value
    return factory(executor)


def main():
    parser = argparse.ArgumentParser(prog="python -m assessment", description="Task templates: prepare, certify, assess, run")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("templates")
    prepare = sub.add_parser("prepare"); prepare.add_argument("template"); prepare.add_argument("--source", help="Directory holding the frozen source archives")
    sub.add_parser("instances").add_argument("template")
    brief = sub.add_parser("brief"); brief.add_argument("template"); brief.add_argument("instance"); brief.add_argument("--level", type=int, choices=[1, 2], default=1)
    rubric = sub.add_parser("rubric", help="Show every instrument, its question, implementation and result policy")
    rubric.add_argument("template"); rubric.add_argument("--level", type=int, choices=[1, 2], default=1)
    rubric.add_argument("--format", choices=["json", "markdown"], default="markdown")
    certify = sub.add_parser("certify"); certify.add_argument("template"); certify.add_argument("--full", action="store_true", help="Compare the reference implementations on every instance")
    assess = sub.add_parser("assess"); assess.add_argument("template"); assess.add_argument("instance"); assess.add_argument("submission", nargs="?")
    assess.add_argument("--control", help="Build and assess a named trusted control; start with correct")
    assess.add_argument("--format", choices=["json", "markdown"], default="markdown")
    assess.add_argument("--output", help="Keep assessment.json and review.md in this new directory")
    assess.add_argument("--judge", action="store_true", help="Run the pinned, capped judge on the declared prose questions")
    run = sub.add_parser("run"); run.add_argument("template"); run.add_argument("instance"); run.add_argument("--system", required=True)
    run.add_argument("--parent", help="An earlier run of the same system. Its submission is placed under /work/prior.")
    run.add_argument("--level", type=int, choices=[1, 2], default=1)
    run.add_argument("--supply", action="append", default=[], help="Hand the agent one of the template's supplements, such as `conventions`.")
    run.add_argument("--directions", default="full", help="A rung of the template's directions ladder (assessment.directions): what the agent is told; `full` is the task as published.")
    sub.add_parser("runs")
    reassess = sub.add_parser("reassess"); reassess.add_argument("run")
    sub.add_parser("judge", help="Judge a run's recorded assessment without recomputing it").add_argument("run")
    sub.add_parser("judge-calibration", help="Run the pinned judge on its cases with known answers")
    for command in (run, reassess):
        command.add_argument("--no-judge", action="store_true", help="Leave the judge questions unresolved")
    sub.add_parser("attempts").add_argument("template")
    for command in (certify, assess):
        command.add_argument("--local-trusted", action="store_true", help="Run without Docker. Only for the controller's own control submissions.")
        command.add_argument("--image")
    args = parser.parse_args()
    try:
        result = dispatch(args)
        print(result if isinstance(result, str) else json.dumps(result, indent=2, default=str))
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
        return reassess(args.run, judge=not args.no_judge)
    if args.command == "judge":
        from .runner import judge_run
        return judge_run(args.run)
    if args.command == "judge-calibration":
        from .calibration import calibrate
        return calibrate()
    template = Template(args.template)
    if args.command == "rubric":
        from .rubric import contract, markdown
        value = contract(template, args.level)
        return markdown(value) if args.format == "markdown" else value
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
        report = certify(template, _executor(args, template), full=args.full)
        return {"automatic_tests_passed": report["automatic_tests_passed"], "certified": report["certified"],
                "tests": {name: test["passed"] for name, test in report["tests"].items()},
                "record": str((template.folder / "certification.json").relative_to(ROOT))}
    if args.command == "assess":
        from .assess import assess
        from .rubric import markdown
        if bool(args.submission) == bool(args.control):
            raise ValueError("Name a submission directory or --control NAME")
        if args.local_trusted and not args.control:
            raise ValueError("--local-trusted is restricted to --control submissions")
        params = template.instance(args.instance)
        with tempfile.TemporaryDirectory(prefix="assessment-") as scratch:
            root = Path(scratch)
            submission = Path(args.submission) if args.submission else root / "control"
            if args.control:
                from .certify import _controls
                controls = _controls(template)
                if args.control not in controls.CONTROLS:
                    raise ValueError(f"Unknown control {args.control!r}; choose from {list(controls.CONTROLS)}")
                template.hooks.stage_inputs(template.private, params, root / "inputs")
                controls.build(args.control, root / "inputs", params, submission)
            value = assess(template, params, submission, _executor(args, template), root / "work")
            output = Path(args.output) if args.output else None
            if output is not None:
                output.mkdir(parents=True, exist_ok=False)
            evidence = getattr(template.hooks, "acquisition_evidence", None)
            if evidence is not None:
                value["acquisition"] = evidence(root / "work", output / "acquisition-evidence" if output else None)
            if args.judge:
                from . import judge as judging
                from .assess import judge_files
                judging.apply(value, judge_files(template, params, submission), judging.claude_cli, template.spec)
            review = markdown(value["rubric"], value)
            if output is not None:
                (output / "assessment.json").write_text(json.dumps(value, indent=2, default=str) + "\n")
                (output / "review.md").write_text(review)
            return review if args.format == "markdown" else value
    if args.command == "run":
        from .runner import run
        return run(template, template.instance(args.instance), args.system, parent=args.parent, level=args.level,
                   supplied=args.supply, judge=not args.no_judge, directions=args.directions)


if __name__ == "__main__":
    main()
