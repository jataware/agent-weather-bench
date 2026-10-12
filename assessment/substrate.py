"""Substrate use for template runs: mounted files and installed libraries.

Builds on `assessment.substrate_use` (pull request #1), which reports whether a
run listed, read or ran the files mounted at /substrate. A substrate can also be
a library installed in the runtime image, such as AfricaS2S or acmadDL, and that
monitor cannot see an import. This module adds the import record beside the
original one and changes neither its code nor its numbers.
"""
import json
import re
import sys
from pathlib import Path

from .substrate_use import executed_commands, substrate_use
from .tracer import read_trace, static_calls, traced_argv

CODE_SUFFIXES = (".py", ".ipynb", ".sh", ".R", ".jl")


def _pattern(library):
    name = re.escape(library)
    return re.compile(rf"(?:^|[\s;(\"'`])(?:import\s+{name}\b|from\s+{name}(?:\.[\w.]+)?\s+import\b|python3?\s+-m\s+{name}\b)", re.MULTILINE)


def library_use(run, libraries):
    """Per declared library: commands that import it, and submitted files that import it. A lower bound."""
    run, log = Path(run), Path(run) / "logs/events.jsonl"
    commands = executed_commands(log)[0] if log.is_file() else []
    record = {}
    for library in libraries:
        pattern = _pattern(library)
        steps = [index for index, (command, _) in enumerate(commands, 1) if pattern.search(command)]
        files = []
        for path in sorted((run / "frozen").rglob("*")) if (run / "frozen").is_dir() else []:
            if path.is_file() and path.suffix in CODE_SUFFIXES and path.stat().st_size <= 2_000_000 and pattern.search(path.read_text(errors="replace")):
                files.append(str(path.relative_to(run / "frozen")))
        record[library] = {"commands_importing": len(steps), "first_step": steps[0] if steps else None,
                           "submitted_files_importing": files, "used": bool(steps or files)}
    return record


def image_path_use(run, paths):
    """Per declared path inside the runtime image, such as a skills catalog: the commands that name it. A lower bound."""
    log = Path(run) / "logs/events.jsonl"
    commands = executed_commands(log)[0] if log.is_file() else []
    record = {}
    for path in paths:
        pattern = re.compile(r"(?<![\w.~-])" + re.escape(path.rstrip("/")) + r"(?=$|[/\s'\"`;|&<>(){}])")
        steps = [index for index, (command, _) in enumerate(commands, 1) if pattern.search(command)]
        failed = sum(1 for index in steps if commands[index - 1][1] not in (0, None))
        record[path] = {"commands_naming": len(steps), "of_which_failed": failed, "first_step": steps[0] if steps else None, "used": bool(steps)}
    return record


def library_calls(template, params, submission, executor, scratch, libraries, seconds=120):
    """What the submission calls in `libraries`: the submitted code read statically, and the declared command replayed
    once more under a call tracer (assessment.tracer). The traced replay is a measurement; its outputs decide nothing."""
    from .execute import valid_argv
    submission, scratch = Path(submission), Path(scratch)
    record = {"libraries": list(libraries), "static": static_calls(submission, libraries), "replay": None,
              "calls": {library: {} for library in libraries},
              "method": "static: callees resolved through the submitted files' imports; replay: calls from the submission's own code "
                        "into each library, counted function by function while the declared command ran once more on the controller's inputs. "
                        "Both are lower bounds; a process that exits without Python's atexit (a hard kill, os._exit) leaves no trace."}
    try:
        answer = json.loads((submission / "answer.json").read_text())
    except (OSError, ValueError):
        answer = {}
    argv = (answer.get("run") or {}).get("argv") if isinstance(answer.get("run"), dict) else None
    if not valid_argv(argv):
        record["replay"] = {"state": "not_run", "reason": "the answer declares no usable run command"}
        return record
    if getattr(executor, "name", "").startswith("local") and argv[0] in ("python", "python3"):
        argv = [sys.executable, *argv[1:]]                   # the trusted local executor would do the same for a bare command
    inputs = scratch / "inputs"
    template.hooks.stage_inputs(template.private, params, inputs)
    run = executor.run(submission, inputs, traced_argv(argv, libraries), scratch / "replay", seconds=seconds)
    trace = read_trace(run["output"])
    record["replay"] = {"state": "run", "executor": run.get("executor"), "exit_code": run.get("exit_code"),
                        "infrastructure_unavailable": bool(run.get("infrastructure_unavailable")), "processes": trace["processes"],
                        "stderr": (run.get("stderr") or "")[-600:] if run.get("exit_code") else ""}
    for name, count in trace["calls"].items():
        library = next((library for library in libraries if name == library or name.startswith(library + ".")), None)
        if library:
            record["calls"][library][name] = count
    return record


def substrate_record(run, config):
    """The full record for one run: the original path-based monitor, plus what a system declares it installs in its image."""
    substrate = config.get("substrate") or {}
    libraries, paths = substrate.get("libraries") or [], substrate.get("image_paths") or []
    if not isinstance(libraries, list) or not all(isinstance(name, str) and re.fullmatch(r"[A-Za-z_][\w.]*", name) for name in libraries):
        raise ValueError("substrate.libraries must be a list of importable module names")
    if not isinstance(paths, list) or not all(isinstance(path, str) and re.fullmatch(r"/[\w./-]+", path) for path in paths):
        raise ValueError("substrate.image_paths must be a list of absolute paths")
    log = Path(run) / "logs/events.jsonl"
    record = {"mounted_files": substrate_use(run),
              "libraries": library_use(run, libraries) if libraries else {},
              "image_paths": image_path_use(run, paths) if paths else {},
              "commands": len(executed_commands(log)[0]) if log.is_file() else None,
              "method": "Mounted files: command text naming /substrate paths (assessment.substrate_use). Libraries: import statements in "
                        "executed command text and in submitted code; where the controller traced a replay, the functions the delivered "
                        "command actually calls (assessment.tracer). Image paths: command text naming them. All are lower bounds; use is not quality."}
    calls_file = Path(run) / "controller/library-calls.json"
    if libraries and calls_file.is_file():
        try:
            calls = json.loads(calls_file.read_text())
        except ValueError:
            calls = None
        if isinstance(calls, dict) and calls.get("libraries") == libraries:
            for library in libraries:
                row = record["libraries"][library]
                row["static_calls"] = (calls.get("static") or {}).get(library, {})
                row["replay_calls"] = (calls.get("calls") or {}).get(library, {})
                row["substantive"] = bool(row["replay_calls"])
            record["library_calls"] = {"replay": calls.get("replay"), "method": calls.get("method"),
                                       "substantive": "a library counts as substantively used when the delivered command, replayed by the "
                                                      "controller, called at least one of its functions from the submission's own code"}
    return record
