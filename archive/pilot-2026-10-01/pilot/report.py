import html
from pathlib import Path
from .common import ROOT, read, task
from .judge import completion


def report(runs, output):
    groups = {}
    for path in sorted(Path(runs).rglob('run.json')):
        run = path.parent
        m = read(path)
        checks = read(run/'checks.json') if (run/'checks.json').exists() else None
        judge = read(run/'judge.json') if (run/'judge.json').exists() else None
        status = completion(checks,judge,m.get('integrity','unreviewed')) if checks else 'not_evaluated'
        if m.get('excluded_from_arm_comparison'):
            status = 'excluded setup diagnostic'
        key = (m.get('study_type','pilot'), m['model'], m['mode'],m['task'],m['arm'])
        # Keep repeat attempts, never silently select the best one.
        groups.setdefault(key,{}).setdefault(m['phase'],[]).append((run,m,checks,judge,status))
    rows=[]
    for (study,model,mode,name,arm),phases in groups.items():
        cells=[html.escape(x) for x in [study,model,mode,task(name)['title'],arm]]
        for phase in ['initial','followup']:
            parts=[]
            for run,m,c,j,s in phases.get(phase,[]):
                usage=m.get('usage',{})
                ratings=', '.join(k+': '+str(v['score']) for k,v in j['ratings'].items()) if j else 'Judge pending'
                metric = ''
                if c and c['metrics'].get('skill_vs'):
                    value=c['metrics']['skill_vs'].get('model_climate')
                    metric=f' · RPS skill vs model-climate {value:.1%}' if value is not None else ''
                parts.append(html.escape(f"{s} · ${usage.get('usd',0):.2f} · {m.get('seconds',0)/60:.1f} min{metric}")+
                             '<details><summary>Evidence</summary><p>'+html.escape(ratings)+'</p><p>'+html.escape(str(run))+'</p></details>')
            cells.append('<br>'.join(parts) or 'Not run')
        rows.append('<tr>'+''.join('<td>'+x+'</td>' for x in cells)+'</tr>')
    if not rows: rows=['<tr><td colspan="7">No benchmark attempts in this directory.</td></tr>']
    page='''<!doctype html><meta charset="utf-8"><title>ACCORD weather pilot</title>
<style>body{font:16px system-ui;margin:48px;max-width:1400px;color:#17313b}table{border-collapse:collapse;width:100%}th,td{padding:16px;text-align:left;border-bottom:1px solid #ccd6d7;vertical-align:top}th{background:#e9f1ef}details{font-size:13px;margin-top:12px}p{max-width:1000px;line-height:1.5}</style>
<h1>Three tasks · three tool environments · one follow-up each</h1>
<p>Compare correctness, scientific quality, cost and retained work. Separate controlled and open-web results. A valid negative scientific result can complete the task. No weighted leaderboard; no causal reuse claim without fresh follow-up controls.</p>
<table><thead><tr><th>Study</th><th>Model</th><th>Access</th><th>Task</th><th>Arm</th><th>Initial</th><th>Follow-up</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table>
<p>Numerical checks and a five-criterion evidence-citing judge underpin each completion assessment. “Pending” means evidence or integrity review is missing, not that a model failed.</p>'''
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(page)
    return str(output)
