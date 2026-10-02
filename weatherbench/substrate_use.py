"""Whether an attempt used its mounted substrate, read from the recorded tool commands.

A substrate that is mounted but never read or run measures availability, not use. Every
agent action reaches the runtime as an `execute` command, so the event log is a complete
record of what was asked; matching paths in command text is still a lower bound (a `cd`
followed by relative paths, shell variables, or code that opens substrate files itself
are not attributed), and is reported as such.
"""
import json
import re

PATH = re.compile(r"/substrate(?:/[^\s'\"`;|&<>(){}]*)?")
START = r"(?:^|[;&|(]|\bthen|\bdo)\s*"
RUN = re.compile(START+r"(?:(?:uv\s+run|python3?|bash|sh|Rscript)\s+(?:-\S+\s+)*)*(/substrate/[^\s'\"`;|&<>(){}]+)")
LIST = re.compile(START+r"(?:ls|find|tree)\b[^;&|]*?/substrate")
CD = re.compile(START+r"(?:cd|pushd)\s+/substrate")
DOCUMENT = (".md",".txt",".rst",".yaml",".yml",".json",".csv",".html")


def executed_commands(log):
    """Commands that reached the runtime, in order, for both the built-in and command drivers."""
    commands, pending = [], None
    for line in log.read_text().splitlines():
        if not line.strip(): continue
        event = json.loads(line)
        if event.get("type")=="adapter" and (event.get("event") or {}).get("type")=="execute":
            pending = event["event"].get("command")
        elif event.get("type")=="tool_result":
            command = event["command"] if "command" in event else pending
            pending = None
            if isinstance(command,str): commands.append(command)
    return commands


def classify(command):
    """Strongest use in one command: ran > read > listed > entered, or None."""
    kinds = set()
    for part in re.split(r"&&|\|\||[;|\n]",command):
        if not PATH.search(part): continue
        if any(not m.group(1).lower().endswith(DOCUMENT) for m in RUN.finditer(part)): kinds.add("ran")
        elif LIST.search(part): kinds.add("listed")
        elif CD.search(part): kinds.add("entered")
        else: kinds.add("read")
    return next((kind for kind in ("ran","read","listed","entered") if kind in kinds),None)


def substrate_use(run):
    """Summary for one run directory, or None when it has no execution log."""
    log = run / "logs/events.jsonl"
    if not log.is_file(): return None
    commands = executed_commands(log)
    kinds = [classify(command) for command in commands]
    touched = [i for i,kind in enumerate(kinds,1) if kind]
    files = sorted({m.group(0) for command in commands for m in PATH.finditer(command)} - {"/substrate","/substrate/"})
    return {"commands":len(commands),"substrate_commands":len(touched),
            **{kind:kinds.count(kind) for kind in ("ran","read","listed","entered")},
            "first_step":touched[0] if touched else None,"paths":files[:50],
            "method":"command-text lower bound"}
