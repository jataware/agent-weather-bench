"""Small human-readable scorecard generated from audited run records."""
from html import escape as e
from pilot.common import ROOT,read
s=read(ROOT/'results/smoke-summary.json')
rows=[];judge_rows=[];details=[]
order=['fable-scratch-initial','fable-rhiza-initial','fable-accord-initial','haiku-scratch-initial','fable-scratch-followup','fable-rhiza-followup','fable-accord-followup']
for name in order:
 if name not in s['runs']:continue
 r=s['runs'][name];run=ROOT/'runs/smoke-v3'/name
 metrics=r['metrics'];rmse=r.get('rmse_mm');rps=r.get('rps');gap=r.get('reliability_gap')
 rows.append('<tr>'+''.join('<td>'+v+'</td>' for v in [e(name),e(r['completion']),e(r['check_count']),f"{r['tokens']:,}",f"${r['usd']:.3f}",f"{r['seconds']/60:.2f} min",f'{rps:.4f}' if rps is not None else '—',f'{rmse:.1f}' if rmse is not None else '—',f'{gap:.4f}' if gap is not None else '—'])+'</tr>')
 j=read(run/'judge.json') if (run/'judge.json').exists() else None
 if j:
  judge_rows.append('<tr><td>'+e(name)+'</td>'+''.join('<td>'+str(v['score'])+'</td>' for v in j['ratings'].values())+'</tr>')
  rating_text=''.join('<li><b>'+e(k.replace('_',' '))+f" ({v['score']}/2)</b>: "+e(v['reason'])+'</li>' for k,v in j['ratings'].items())
 else:rating_text='<li>Judge response not validated.</li>'
 facts=r.get('audit',{})
 details.append(f'<details><summary>{e(name)}</summary><p><a href="runs/smoke-v3/{name}/frozen/">Saved workspace</a> · <a href="runs/smoke-v3/{name}/run.json">Model, usage and identity</a> · <a href="runs/smoke-v3/{name}/checks.json">Numerical scores</a> · <a href="runs/smoke-v3/{name}/judge.json">Judge evidence</a> · <a href="runs/smoke-v3/{name}/audit.json">Integrity review</a></p><p>Failed checks: '+e(', '.join(r['failed_checks']) or 'none')+'</p><ul>'+rating_text+'</ul></details>')
cost_agents=sum(r['usd'] for r in s['runs'].values());cost_diag=sum(r['recorded_usd'] for r in s['diagnostics']);cost_judges=s['recorded_total_usd_including_diagnostics']-cost_agents-cost_diag
findings=''.join('<p>'+e(s.get(k,'Evaluation in progress.'))+'</p>' for k in ['capability_finding','tools_finding','reuse_finding'])
html='''<!doctype html><meta charset="utf-8"><title>ACCORD weather pilot results</title><style>body{font:16px/1.5 Calibri,Arial,sans-serif;color:#111;max-width:1250px;margin:40px auto;padding:0 24px}h1{font-size:30px}h2{margin-top:32px;font-size:23px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #ccc;padding:9px;text-align:left}th{background:#eee}details{border-top:1px solid #bbb;padding:15px 0}summary{font-weight:bold;cursor:pointer}a{color:#245b8e}.note{color:#555}li{margin:10px 0}</style><h1>ACCORD weather pilot: measured smoke</h1><p><a href="2026-10-01-accord-checkin.pptx">Updated check-in deck</a> · <a href="slides/three-smoke-slides.pptx">Three-slide extract</a> · <a href="slides/three-smoke-slides.html">Slide preview</a> · <a href="results/smoke-summary.json">Machine-readable results</a></p>'''+findings
html+='<h2>Completion, forecast quality and effort</h2><table><tr><th>Attempt</th><th>Completion</th><th>Checks</th><th>Tokens</th><th>Agent $</th><th>Wall time</th><th>RPS ↓</th><th>RMSE mm ↓</th><th>Reliability gap ↓</th></tr>'+''.join(rows)+'</table>'
html+='<p class="note">Tokens = provider-reported input + output, including repeated context and thinking output. RPS and RMSE use frozen predictions on two private-to-agent years per phase. The years were previously inspected by the experiment designer. The reliability gap is a binned, above-normal diagnostic; two years cannot establish calibration. All 12 checks are mandatory but are not equally important scientific dimensions.</p>'
html+='<h2>Five-criterion judge</h2><table><tr><th>Attempt</th><th>Data / provenance</th><th>Processing</th><th>Results / uncertainty</th><th>Communication</th><th>Reproduction / reuse</th></tr>'+''.join(judge_rows)+'</table><p>0 = absent/incorrect, 1 = partial, 2 = satisfactory. No weighted total. Sonnet 5.5 saw submissions, code, the outlook figure, numerical checks and replay evidence, without comparative costs or arm labels. Toolkit names can reveal arms. Numerical failures cannot be overridden.</p>'
html+=f'<h2>Recorded cost</h2><p>Agent attempts: <b>${cost_agents:.4f}</b>. Judge calls: <b>${cost_judges:.4f}</b>. Excluded setup attempts: <b>${cost_diag:.4f}</b>. Total recorded: <b>${s["recorded_total_usd_including_diagnostics"]:.4f}</b>.</p><p class="note">'+e(s['cost_note'])+' Local compute and operator time are not priced. Agent time excludes controller scoring and judge latency.</p>'
html+='<h2>What this experiment can say</h2><p>Same Fable 5.1 model, identical inputs and numerical dependencies, $5 / ten-minute / 35-turn limits per attempt, 8,192 output tokens per response. Haiku 4.5 gets the same caps but different per-token prices. The client reserves the next response cost and can stop before spending $5. Large truncated tool calls were a material failure mode. This is a comparison under this harness, not a universal capability threshold.</p><p>The task aggregates monthly ECMWF system 51 forecasts and native CHIRPS rainfall over 12 Kenyan grid cells, fits on 1993–2004, and predicts 2005–06 then 2007–08 without access to verification observations. No live data acquisition is scored. All arms can retain code, data, models and notes; only their own files enter a fresh follow-up conversation. Recovery from an incomplete first attempt is identified separately. No fresh-workspace controls or repeated seeds were run.</p><p>Setup versions v1/v2 hit native NetCDF/HDF5 defects. They are preserved and charged as setup, not model failures. All three v3 images passed the common NetCDF3 input / h5netcdf output roundtrip and sandbox checks before launch. The full seasonal, IOD and Kenya studies and open-web replication remain unlaunched.</p>'
if (ROOT/'results/direct-reuse-timing.json').exists():
 html+='<h2>Direct reuse without another LLM call</h2>'
 for v in read(ROOT/'results/direct-reuse-timing.json'):
  html+=f'<p>The initial {e(v["arm"])} predictor applied its saved model to the second batch in <b>{v["seconds_including_container_start_cleanup"]:.2f} seconds</b>, including container startup and cleanup, with <b>zero additional agent tokens or API dollars</b>. This is direct code execution, distinct from the conversational follow-up above. Local compute cost is not monetized.</p>'
html+='<h2>Per-attempt evidence</h2>'+''.join(details)
(ROOT/'report.html').write_text(html)
(ROOT/'review.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=report.html"><a href="report.html">Measured smoke results</a>')
print('Results page written')
