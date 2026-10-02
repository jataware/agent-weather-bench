import json

import pytest

from weatherbench.substrate_use import classify, substrate_use


def log(run, rows):
    (run / "logs").mkdir(parents=True)
    (run / "logs/events.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))


def result(command=None, **extra):
    return {"type":"tool_result","id":"x","exit_code":0,"stdout":"","stderr":"",**({"command":command} if command else {}),**extra}


@pytest.mark.parametrize("command,kind",[
    ("python workflow.py",None),
    ("ls /substrate",'listed'),
    ("find /substrate -name '*.md'",'listed'),
    ("cat /substrate/skills/START.md","read"),
    ("sed -n 1,80p /substrate/skills/verify/SKILL.md","read"),
    ("cat /substrate/skills/verify/scripts/verify.py","read"),
    ("python /substrate/skills/verify/scripts/verify.py --metric crps",'ran'),
    ("cd /work && uv run python -u /substrate/skills/verify/scripts/verify.py","ran"),
    ("bash /substrate/workflows/prepare.sh inputs","ran"),
    ("/substrate/bin/fetch --region kenya","ran"),
    ("python /substrate/notes.md",'read'),
    ("ls /substrate/skills; cat /substrate/skills/START.md","read"),
    ("cat /substrate/a.md | python /substrate/tool.py","ran"),
    ("cd /substrate/skills && python verify.py","entered"),
])
def test_commands_are_classified_by_their_strongest_substrate_use(command,kind):
    assert classify(command)==kind


def test_builtin_driver_log_counts_use_and_first_step(tmp_path):
    log(tmp_path,[{"type":"model","response":{}},result("python -c 'print(1)'"),result("ls /substrate/skills"),
                  result("cat /substrate/skills/START.md"),result("python /substrate/skills/verify/scripts/verify.py")])
    use = substrate_use(tmp_path)
    assert (use["commands"],use["substrate_commands"],use["ran"],use["read"],use["listed"],use["first_step"])==(4,3,1,1,1,2)
    assert use["paths"]==["/substrate/skills","/substrate/skills/START.md","/substrate/skills/verify/scripts/verify.py"]
    assert use["method"]=="command-text lower bound"


def test_command_driver_counts_only_commands_that_reached_the_runtime(tmp_path):
    execute = lambda command:{"type":"adapter","event":{"type":"execute","id":"x","command":command}}
    log(tmp_path,[execute("ls /substrate"),result(remaining_seconds=1),execute("python solve.py"),result(remaining_seconds=1),
                  execute("python /substrate/run.py")])  # tool limit reached: never executed
    use = substrate_use(tmp_path)
    assert (use["commands"],use["substrate_commands"],use["ran"],use["listed"])==(2,1,0,1)


def test_mounted_but_unused_substrate_is_zero_and_missing_log_is_unknown(tmp_path):
    assert substrate_use(tmp_path) is None
    log(tmp_path,[result("python solve.py"),result("ls /work/inputs")])
    use = substrate_use(tmp_path)
    assert use["substrate_commands"]==0 and use["first_step"] is None and use["paths"]==[]


def test_run_report_shows_substrate_use(tmp_path,monkeypatch):
    import weatherbench.report as report
    monkeypatch.setattr(report,"STATE",tmp_path)
    for name,commands in (("used",["python /substrate/run.py"]),("unused",["python solve.py"])):
        run = tmp_path / "runs" / name; run.mkdir(parents=True)
        (run / "run.json").write_text(json.dumps({"task":"acmad-objective","system":"s","kind":"agent","status":"submitted","usage":None}))
        log(run,[result(command) for command in commands])
    rows = {row["id"]:row for row in report.list_runs()}
    assert rows["used"]["substrate_use"]["ran"]==1 and rows["unused"]["substrate_use"]["substrate_commands"]==0
    page = (tmp_path / "index.html").read_text() if report.report() else ""
    assert "Substrate use" in page and "ran 1" in page and ">none<" in page
