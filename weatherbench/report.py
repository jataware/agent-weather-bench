import html
from pathlib import Path

from .storage import STATE, read
from .substrate_use import substrate_use


def list_runs():
    rows = []
    for folder in sorted((STATE / "runs").glob("*")):
        if not (folder / "run.json").is_file(): continue
        meta = read(folder / "run.json")
        assessment = read(folder / "assessment.json") if (folder / "assessment.json").exists() else {}
        rows.append({"id":folder.name,"task":meta["task"],"system":meta["system"],"kind":meta["kind"],"status":meta["status"],
                     "completion":assessment.get("completion","unassessed"),"score_bounds":assessment.get("score_bounds"),
                     "agent_usage":meta.get("usage"),"usage_source":meta.get("usage_source"),"seconds":meta.get("seconds"),
                     "judge_usage":assessment.get("judge_usage"),"judge_fingerprint":assessment.get("judge_fingerprint"),
                     "judge":assessment.get("judge"),"tool_calls":meta.get("tool_calls"),
                     "parent":meta.get("parent"),"benchmark_eligible":assessment.get("benchmark_eligible",False),
                     "substrate_use":substrate_use(folder)})
    return rows


def report():
    def esc(value): return html.escape(str(value))
    rows = []
    for run in list_runs():
        cost = run["agent_usage"].get("usd") if isinstance(run["agent_usage"],dict) else None
        judge_cost = run["judge_usage"].get("usd") if isinstance(run["judge_usage"],dict) else (0 if run["judge"]=="none" else None)
        judge_label = "unknown" if judge_cost is None else f"${judge_cost:.4f}"
        seconds = "unknown" if run["seconds"] is None else f'{run["seconds"]:.1f}s'
        branch = "reset" if run["parent"] is None else "retained"
        policy = run["judge_fingerprint"] or "unassessed"
        score = "–" if run["score_bounds"] is None else "–".join(f"{x:.1f}" for x in run["score_bounds"])
        use = run["substrate_use"]
        used = "unknown" if use is None else "none" if not use["substrate_commands"] else f'ran {use["ran"]} · read {use["read"]} · listed {use["listed"]}<br><small>first at step {use["first_step"]} of {use["commands"]}</small>'
        rows.append(f'<tr><td><a href="runs/{esc(run["id"])}/run.json">{esc(run["id"])}</a><br><small>{esc(run["kind"])} · {esc(run["usage_source"])}</small><br><small title="{esc(policy)}">Judge {esc(policy[:16])}</small></td><td>{esc(run["task"])}</td><td>{esc(run["system"])}<br><small title="{esc(run["parent"])}">{branch} · {seconds}</small></td><td>{esc(run["completion"])}</td><td>{score}</td><td>{used}</td><td>{"unknown" if cost is None else f"${cost:.4f}"}<br><small>Judge {judge_label}</small></td><td><a href="runs/{esc(run["id"])}/assessment.json">Assessment</a> · <a href="runs/{esc(run["id"])}/frozen/">Artifacts</a></td></tr>')
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Weather Bench runs</title><style>body{{max-width:1400px;margin:40px auto;padding:0 25px;font:14px/1.6 system-ui;color:#243c38;background:#f6f5ef}}h1{{font:42px Georgia}}table{{width:100%;border-collapse:collapse;background:#fffefa}}td,th{{text-align:left;padding:15px;border-bottom:1px solid #dce2d8}}small{{color:#63736b}}a{{color:#29695b}}input{{padding:12px;width:360px;max-width:100%;margin-bottom:20px}}.scroll{{overflow:auto}}</style><h1>Agent Weather Bench · runs</h1><p>Current development runs only. Historical pilot results live in the archive. Harness fixtures are excluded from capability claims; unknown usage is not zero cost. Substrate use counts commands naming <code>/substrate</code> paths, a lower bound.</p><input id="filter" aria-label="Filter runs" placeholder="Filter task, system, status…"><div class="scroll"><table><thead><tr><th>Run</th><th>Task</th><th>System</th><th>Completion</th><th>Score bounds</th><th title="Commands that ran, read or listed /substrate files; a lower bound from command text">Substrate use</th><th>Agent USD</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><script>document.getElementById('filter').addEventListener('input',event=>{{const query=event.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(query));}});</script></html>'''
    STATE.mkdir(exist_ok=True)
    target = STATE / "index.html"
    target.write_text(page)
    return {"report":str(target),"runs":len(rows)}
