"""Read-only evaluation summary plus explicit integrity records; no API calls."""
from pathlib import Path
import json,re
from pilot.common import ROOT,read,write,inventory,digest
from pilot.judge import completion,validate,evidence_ids
BASE=ROOT/'runs/revision-v1'
result={'protocol':'revision/PLAN.txt','runs':{},'prior_recorded_usd':read(ROOT/'results/smoke-summary.json')['recorded_total_usd_including_diagnostics']}
for r in sorted(BASE.glob('*')):
 if not (r/'checks.json').exists():continue
 m=read(r/'run.json');c=read(r/'checks.json');files=inventory(r/'frozen')
 if not (r/'judge.json').exists() and (r/'judge-raw.json').exists():
  raw=read(r/'judge-raw.json');packet=read(r/'judge-packet.json')
  try:
   j=validate(json.loads(''.join(b['text'] for b in raw['content'] if b['type']=='text')),evidence_ids(packet))
   j['provenance']={'model':raw['model'],'usage':read(r/'judge-usage.json'),'packet_sha256':digest(r/'judge-packet.json'),'rubric_sha256':digest(ROOT/'rubric.yaml')};write(r/'judge.json',j)
  except (ValueError,KeyError):pass
 j=read(r/'judge.json') if (r/'judge.json').exists() else None
 es=[json.loads(l) for l in (r/'events.jsonl').read_text().splitlines()]
 commands=[x.get('command') or '' for x in es if x['type']=='tool']
 sources='\n'.join(p.read_text(errors='replace') for p in (r/'frozen').rglob('*.py'))
 models=[n for n in files if Path(n).name in ['model.pkl','model.npz','model.nc','model.json']]
 inp=inventory(ROOT/'.private/smoke/inputs')
 imports=sorted(set(re.findall(r'(?:from|import)\s+(africas2s|acmaddl|rosetta)\b',sources)))
 preserved=files==read(r/'artifacts.json')
 same_inputs=all(files.get('inputs/'+n)==v for n,v in inp.items())
 allowed=not (m['arm']!='accord' and imports) and not (m['arm']!='rhiza' and '/catalog/' in sources)
 network=[];log=Path(m.get('gateway_log') or '/nonexistent')
 if log.exists():network=[json.loads(l) for l in log.read_text().splitlines()]
 parent=Path(m['parent']) if m.get('parent') else None
 before=read(parent/'artifacts.json') if parent else {}
 unchanged=[n for n in models if before.get(n)==files[n]]
 audit={'status':'passed' if preserved and same_inputs and allowed else 'requires_review','frozen_hashes_match':preserved,'identical_input_hashes':same_inputs,'allowed_toolkit_imports':allowed,'toolkit_imports_in_code':imports,'catalog_reads':sum('SKILL.md' in cmd and '/catalog/' in cmd for cmd in commands),'catalog_script_calls':sum(bool(re.search(r'(?:python|uv run)\s+/catalog/[^\s;]+\.py',cmd)) for cmd in commands),'saved_models':models,'unchanged_inherited_models':unchanged,'input_cache':'retained supplied data; no download saving measured','network_response_bytes':sum(x.get('bytes',0) for x in network),'network_requests':sum('method' in x for x in network),'truncated_responses':sum(x['type']=='model' and x['response']['stop_reason']=='max_tokens' for x in es),'verification_boundary':'Frozen read-only code receives forecast-only inputs, no network and no verification observations.'}
 audit['unchanged_inherited_cache_files']=[n for n in before if 'cache/' in n and files.get(n)==before[n]]
 audit['cache_log_evidence']=[x['result'].get('stdout','')[:1500] for x in es if x['type']=='tool' and re.search(r'cache.{0,20}hit|reus.{0,20}cache|cached',x['result'].get('stdout',''),re.I)][:5]
 write(r/'audit.json',audit);m['integrity']='passed' if audit['status']=='passed' else 'unreviewed';write(r/'run.json',m)
 u=m['usage'];ju={'usd':sum(read(p).get('usd',0) for p in r.rglob('judge-usage.json'))}
 entry={'arm':m['arm'],'model':m['model'],'phase':m['phase'],'status':m['status'],'reason':m.get('reason'),'input_tokens':u['input_tokens'],'output_tokens':u['output_tokens'],'tokens':u['input_tokens']+u['output_tokens'],'usd':u['usd'],'seconds':m['seconds'],'usage_incomplete':m.get('usage_incomplete',False),'checks':f"{c['passed_checks']}/{c['total_checks']}",'failed_checks':[x['id'] for x in c['checks'] if not x['passed']],'metrics':c['metrics'],'ratings':{k:v['score'] for k,v in j['ratings'].items()} if j else None,'judge_usd':ju.get('usd',0),'completion':completion(c,j,m['integrity']),'audit':audit}
 result['runs'][r.name]=entry
result['new_agent_usd']=sum(x['usd'] for x in result['runs'].values());result['new_judge_usd']=sum(x['judge_usd'] for x in result['runs'].values());result['total_recorded_usd']=result['prior_recorded_usd']+result['new_agent_usd']+result['new_judge_usd']
result['cost_note']='Recorded provider token usage at fixed prices. Prior interrupted/timed-out calls may add unrecorded usage; the protocol reserves a buffer below $100.'
write(ROOT/'results/revision-summary.json',result)
print(json.dumps({'runs':{k:{f:v[f] for f in ['checks','tokens','usd','seconds','completion']} for k,v in result['runs'].items()},'total_recorded_usd':result['total_recorded_usd']},indent=2))
