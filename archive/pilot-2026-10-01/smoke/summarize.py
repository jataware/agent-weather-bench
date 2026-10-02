"""Build slide-ready facts from preserved controller records, never agent claims."""
from pathlib import Path
import json
from pilot.common import ROOT,read,write,digest
from pilot.judge import completion

def summarize():
 prior=read(ROOT/'results/smoke-summary.json') if (ROOT/'results/smoke-summary.json').exists() else {}
 result={'scope':'development-only smoke; supplied monthly inputs; no acquisition cost measured','runs':{},'diagnostics':[]}
 for key in ('capability_finding','tools_finding','reuse_finding'):
  if key in prior: result[key]=prior[key]
 total=0
 for base in ['smoke-v1','smoke-v2']:
  for p in (ROOT/'runs'/base).glob('*/run.json'):
   m=read(p);usd=m.get('usage',{}).get('usd',0)
   if m['model'].startswith('claude-haiku') and m.get('excluded_from_arm_comparison') and not m.get('pricing_corrected'):usd/=10
   result['diagnostics'].append({'run':str(p.parent.relative_to(ROOT)),'status':m['status'],'recorded_usd':usd})
   total+=usd
 for p in sorted((ROOT/'runs/smoke-v3').glob('*/run.json')):
  m=read(p);run=p.parent;checks=read(run/'checks.json') if (run/'checks.json').exists() else None
  j=read(run/'judge.json') if (run/'judge.json').exists() else None
  if not checks:continue
  usage=m.get('usage',{}); metrics=checks['metrics'];files=read(run/'artifacts.json')
  models=[n for n in files if Path(n).name in ['model.pkl','model.npz','model.nc','model.json']]
  events=[json.loads(l) for l in (run/'events.jsonl').read_text().splitlines()]
  commands=[e.get('command') or '' for e in events if e['type']=='tool']
  judge_usd=sum(read(p).get('usd',0) for p in run.rglob('judge-usage.json'))
  sources='\n'.join(f.read_text(errors='replace') for f in (run/'frozen').rglob('*.py'))
  entry={'arm':m['arm'],'phase':m['phase'],'model':m['model'],'run_status':m['status'],
   'tokens':usage.get('input_tokens',0)+usage.get('output_tokens',0),'input_tokens':usage.get('input_tokens',0),
   'output_tokens':usage.get('output_tokens',0),'usd':usage.get('usd',0),'seconds':m.get('seconds'),
   'usage_incomplete':m.get('usage_incomplete',False),
   'check_count':f"{checks['passed_checks']}/{checks['total_checks']}",'all_checks_pass':checks['all_mandatory_pass'],
   'failed_checks':[x['id'] for x in checks['checks'] if not x['passed']],
   'rps':metrics.get('RPS',{}).get('submitted'),'rmse_mm':metrics.get('RMSE_mm',{}).get('submitted'),
   'reliability_gap':metrics.get('reliability',{}).get('submitted',{}).get('gap'),
   'metrics':metrics,
   'model_files':models,'model_hashes':{n:files[n]['sha256'] for n in models},
   'saved_code_lines':sum(len(f.read_text(errors='replace').splitlines()) for f in (run/'frozen').rglob('*.py')),
   'catalog_commands':[c[:300] for c in commands if '/catalog/' in c],
   'truncated_responses':sum(e['type']=='model' and e['response']['stop_reason']=='max_tokens' for e in events),
   'accord_import_present':('import africas2s' in sources or 'from africas2s' in sources),
   'judge_ratings':{k:v['score'] for k,v in j['ratings'].items()} if j else None,
   'completion':completion(checks,j,m.get('integrity','unreviewed')),
   'judge_usd':judge_usd,
   'audit':read(run/'audit.json') if (run/'audit.json').exists() else None,
   'artifact_path':str((run/'frozen').relative_to(ROOT))}
  result['runs'][run.name]=entry;total+=entry['usd']+(entry['judge_usd'] or 0)
 result['recorded_total_usd_including_diagnostics']=total
 result['cost_note']='Provider-reported token usage times verified list prices; includes diagnostic attempts and all judge calls. Interrupted setup requests and the timed-out ACCORD follow-up request may have unrecorded cost; this is recorded spend, not a reconciled invoice.'
 write(ROOT/'results/smoke-summary.json',result)
 return result
if __name__=='__main__':
 r=summarize();print(json.dumps({'runs':{k:{x:v[x] for x in ['check_count','usd','seconds','rps','model_files']} for k,v in r['runs'].items()},'recorded_total_usd':r['recorded_total_usd_including_diagnostics']},indent=2))
