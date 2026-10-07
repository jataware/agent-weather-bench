"""Whether an attempt used its mounted substrate, read from the recorded tool commands.

A substrate that is mounted but never read or run measures availability, not use. Every
agent action reaches the runtime as an `execute` command, so the event log is a complete
record of what was asked; matching paths in command text is still a lower bound (a `cd`
followed by relative paths, shell variables, or code that opens substrate files itself
are not attributed), and is reported as such.
"""
import json
import re

STOP = r"\s'\"`;|&<>(){}"
# The mount itself, not any path that merely contains "/substrate" (e.g. /work/state/substrate_notes.md).
PATH = re.compile(rf"(?<![\w.~/-])/substrate(?=$|[/{STOP}])(?:/[^{STOP}]*)?")
START = r"(?:^|[;&|(]|\bthen|\bdo)\s*"
ENV = r"(?:\w+=\S*\s+)*(?:env\s+(?:-\S+\s+)*(?:\w+=\S*\s+)*)?"
RUN = re.compile(START+ENV+rf"(?:(?:uv\s+run|python3?|bash|sh|Rscript)\s+(?:-\S+\s+)*)*(/substrate/[^{STOP}]+)")
LIST = re.compile(START+r"(?:ls|find|tree)\b[^;&|]*?/substrate")
CD = re.compile(START+r"(?:cd|pushd)\s+/substrate")
DOCUMENT = (".md",".txt",".rst",".yaml",".yml",".json",".csv",".html")


def executed_commands(log):
    """(command, exit_code) for commands that reached the runtime, in order, for both drivers.

    Only results from the sandbox carry `seconds`; the built-in driver also logs truncated or
    invalid tool calls as results ("nothing executed"), and those are not counted.
    """
    commands, pending, unreadable = [], None, 0
    for line in log.read_text(errors="replace").splitlines():
        if not line.strip(): continue
        # A run killed mid-write can leave a partial line; one bad log must not break the run list.
        try: event = json.loads(line)
        except ValueError: event = None
        if not isinstance(event,dict): unreadable += 1; continue
        if event.get("type")=="adapter" and (event.get("event") or {}).get("type")=="execute":
            pending = event["event"].get("command")
        elif event.get("type")=="tool_result":
            command = event["command"] if "command" in event else pending
            pending = None
            if isinstance(command,str) and "seconds" in event: commands.append((command,event.get("exit_code")))
    return commands, unreadable


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
    commands, unreadable = executed_commands(log)
    kinds = [classify(command) for command,_ in commands]
    touched = [i for i,kind in enumerate(kinds,1) if kind]
    exits = [code for (_,code),kind in zip(commands,kinds) if kind=="ran"]
    files = sorted({m.group(0) for command,_ in commands for m in PATH.finditer(command)} - {"/substrate","/substrate/"})
    return {"commands":len(commands),"substrate_commands":len(touched),
            **{kind:kinds.count(kind) for kind in ("ran","read","listed","entered")},
            # Exit status belongs to the whole command, so a chained or piped command is attributed as one.
            "ran_ok":exits.count(0),"ran_failed":sum(code not in (0,None) for code in exits),
            "first_step":touched[0] if touched else None,"paths":files[:50],"unreadable_log_lines":unreadable,
            "method":"command-text lower bound; use is not quality"}
