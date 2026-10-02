"""Freeze the revised execution protocol without changing task data or science."""
from pathlib import Path
from copy import deepcopy
import json,yaml
from pilot.common import ROOT,read,write,rhiza_catalog,digest
base=ROOT/'revision';base.mkdir(exist_ok=True)
# Register the skills as an agent would see them: names, descriptions and paths.
lines=['Available Rhiza skills (read the relevant SKILL.md before use; run scripts with python). Use applicable installed skills rather than reimplementing their supported operations; use generic Python for missing capabilities.']
catalog = rhiza_catalog()
for p in sorted((catalog/'skills').rglob('SKILL.md')):
 txt=p.read_text();meta=yaml.safe_load(txt.split('---',2)[1]);rel=p.relative_to(catalog)
 lines.append(f"- {meta['name']}: {str(meta.get('description',''))[:230]} Path: /catalog/{rel}")
rhiza='\n'.join(lines)
accord='''Installed ACCORD capabilities: africas2s (DeepScale), acmaddl and rosetta. Use applicable installed implementations rather than reimplementing their supported operations; use generic Python for missing capabilities.
For persistent per-grid-cell ensemble regression, the installed engine is:
from africas2s.methods.ensemble_regression import EnsembleRegressionMethod
It supports .fit(hindcast, obs), .save(path), .load(path), .predict(forecast), and .predict_tercile(single_year_forecast, obs_climatology, threshold_source="obs"). Inspect signatures/docstrings. clip_negative=True is available for rainfall. ModelBase.save stores fitted state; .load restores it without fitting. The climatology argument should use retained training observations, never future observations. predict_tercile handles one year at a time and labels terciles [0,1,2].
Important API distinction: africas2s.train() uses the downscaling registry, so train("ereg",...) is NOT supported. The class above is the fitted-state interface for eReg; africas2s.calibrate(...,method="ereg") is the fit-and-predict convenience interface.
Other methods and verification are available via africas2s.calibrate, africas2s.skill, africas2s.cv and africas2s.methods. Rosetta/acmaddl provide acquisition and caching when retrieval is needed. General package documentation is in /opt/accord-docs; read targeted sections, not all files at once.
This is an API navigation aid, not a required scientific method. Explain any unsupported operation or decision not to use a toolkit.'''
for model,price in [('haiku',(1,5)),('sonnet',(2,10)),('fable',(10,50))]:
 cfg=deepcopy(read(ROOT/'smoke/config.yaml'))
 cfg['name']='seasonal-revision-1';cfg['study_type']='development_smoke'
 cfg['agent'].update(model={'haiku':'claude-haiku-4-5-20251001','sonnet':'claude-sonnet-5-5','fable':'claude-fable-5-1'}[model],input_usd_per_million=price[0],output_usd_per_million=price[1],max_usd=5.5,max_total_tokens=800000,max_output_tokens=16384,max_turns=60,max_seconds=900)
 cfg['judge']['max_usd']=.35
 cfg['arm_guidance']={'rhiza':rhiza,'accord':accord}
 write(base/f'{model}.json',cfg)
(base/'PLAN.txt').write_text('''Revised seasonal comparison, authorized 1 October 2026.
Same scientific task, supplied monthly inputs, hidden prediction batches and pinned images as smoke-v3. No Kenya switch and no new scientific thresholds.
Seven initial attempts: Haiku/Sonnet/Fable each scratch and Rhiza; Fable with ACCORD. Then three Fable follow-ups with each arm's own retained workspace.
Fixes applied equally: 16,384 output tokens, small file-write instructions, explicit truncated-call recovery, budget feedback and complete-replay reminder. Same $5.50, 900 seconds, 60 turns and 800k-token caps for every agent attempt.
Rhiza receives the installed catalog's name/description/path index. ACCORD receives a verified generic pointer to its fitted eReg class, because train(ereg) is not supported. Neither arm receives a solved task or private answers. These are revised tool configurations; report separately from smoke-v3.
Cost ceiling: prior recorded $35.09 + at most 10 x $5.50 agent calls + 10 x $0.35 judges = $93.59, leaving over $6 for unrecorded interrupted-request usage. No further paid calls without an updated budget calculation. Inputs are supplied, not live downloads; per-arm retained input/cache hashes and network bytes will be reported honestly.
All attempts preserved. No selecting only favorable outcomes. Primary comparisons are within this revised protocol: model capability on scratch, each model with/without Rhiza, Sonnet+Rhiza vs Fable scratch, and Fable ACCORD vs the other two arms. Accuracy, completion, time and cost remain separate.
''')
review=read(ROOT/'launch-review.yaml');review.update(status='ready',reason='User authorized response-limit fixes, ACCORD API investigation, and Haiku/Sonnet/Fable plus skills comparison within $100 total.',allowed_scope='smoke_only');write(ROOT/'launch-review.yaml',review)
write(base/'manifest.json',{'task_sha256':digest(ROOT/'smoke/task.yaml'),'prior_recorded_usd':read(ROOT/'results/smoke-summary.json')['recorded_total_usd_including_diagnostics'],'max_new_agent_usd':55,'max_new_judge_usd':3.5,'overall_user_ceiling_usd':100,'config_sha256':{m:digest(base/f'{m}.json') for m in ['haiku','sonnet','fable']},'inputs_sha256':{p.name:digest(p) for p in (ROOT/'.private/smoke/inputs').iterdir()},'api_check':'results/accord-api-check.json'})
print('Revision frozen; same task/data, seven initial attempts plus three follow-ups; maximum recorded cumulative spend $93.59.')
