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


def test_unexecuted_tool_calls_are_not_use_and_failed_runs_are_separated(tmp_path):
    truncated = {"type":"tool_result","id":"t","command":"python /substrate/skills/verify/scripts/verify.py",
                 "exit_code":1,"stderr":"Incomplete or invalid tool call; nothing executed."}
    log(tmp_path,[truncated,result("python /substrate/a.py",exit_code=2),result("python /substrate/b.py"),
                  result("python /substrate/c.py",exit_code=124),result("cat /substrate/a.md",exit_code=1)])
    use = substrate_use(tmp_path)
    assert (use["commands"],use["ran"],use["ran_ok"],use["ran_failed"],use["read"],use["first_step"])==(4,3,1,2,1,1)
    assert "/substrate/skills/verify/scripts/verify.py" not in use["paths"]


def test_a_malformed_log_line_is_counted_and_does_not_break_the_run_list(tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs/events.jsonl").write_text(json.dumps(result("ls /substrate"))+"\n[1,2]\n"+'{"type":"tool_res')
    use = substrate_use(tmp_path)
    assert (use["commands"],use["listed"],use["unreadable_log_lines"])==(1,1,2)
