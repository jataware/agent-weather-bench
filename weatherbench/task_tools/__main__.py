import argparse
import json

from .prepare import prepare, write_json, TASKS
from .checks import validate_packages, check
from .render import render


def main():
    p = argparse.ArgumentParser(description="Prepare and inspect review task packages; no model calls or submission execution.")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    sub.add_parser("render", help="Build standalone HTML task review pages without accessing private inputs.")
    v = sub.add_parser("validate")
    v.add_argument("--output")
    c = sub.add_parser("check")
    c.add_argument("task", choices=TASKS)
    c.add_argument("--submission", required=True)
    c.add_argument("--output")
    args = p.parse_args()
    if args.command == "prepare":
        result = prepare()
    elif args.command == "render":
        result = render()
    elif args.command == "validate":
        result = validate_packages()
    else:
        result = check(args.task, args.submission)
    if getattr(args, "output", None):
        write_json(args.output, result)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
