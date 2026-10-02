"""Fixed revised comparison; all attempts retained, no automatic paid retries."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import os,re,json,time,random
from pilot.common import ROOT,read,write
from pilot.runner import run_attempt
from pilot.judge import judge

def credentials():
 if not os.environ.get('ANTHROPIC_API_KEY'):
  raise RuntimeError('Set ANTHROPIC_API_KEY in the controller environment')

BASE=ROOT/'runs/revision-v1'
def attempt(model,arm,phase):
 credentials();label=f'{model}-{arm}-{phase}';run=BASE/label
 print('START '+label,flush=True)
 try:
  run_attempt('seasonal',arm,phase,'controlled',run,ROOT/'.private/smoke'/phase,ROOT/'.private/smoke/policy.json',parent=BASE/f'{model}-{arm}-initial' if phase=='followup' else None,config_path=ROOT/f'revision/{model}.json',spec_path=ROOT/'smoke/task.yaml',initial_inputs=ROOT/'.private/smoke/inputs')
  m=read(run/'run.json');c=read(run/'checks.json')
  print('FINISH '+label+' '+json.dumps({'status':m['status'],'usage':m['usage'],'seconds':m['seconds'],'checks':f"{c['passed_checks']}/{c['total_checks']}"}),flush=True)
  try:
   j=judge(run,read(ROOT/f'revision/{model}.json')['judge'])
   print('JUDGE '+label+' '+str({k:v['score'] for k,v in j['ratings'].items()}),flush=True)
  except Exception as e:
   write(run/'judge-error.json',{'type':type(e).__name__,'message':str(e)[:500]});print('JUDGE ERROR '+label+' '+str(e)[:300],flush=True)
  return label
 except Exception as e:
  write(BASE/(label+'-controller-error.json'),{'type':type(e).__name__,'message':str(e)[:500]})
  print('ERROR '+label+' '+type(e).__name__+' '+str(e)[:300],flush=True)
  return None

if __name__=='__main__':
 BASE.mkdir(parents=True,exist_ok=True)
 jobs=[(m,a) for m in ['haiku','sonnet','fable'] for a in ['scratch','rhiza']]+[('fable','accord')]
 random.Random(20261001).shuffle(jobs)
 write(ROOT/'revision/order.json',{'initial':jobs,'followup':[['fable',a] for a in ['scratch','rhiza','accord']]})
 with ProcessPoolExecutor(max_workers=3) as pool:
  futures=[pool.submit(attempt,m,a,'initial') for m,a in jobs]
  for f in as_completed(futures):f.result()
 with ProcessPoolExecutor(max_workers=3) as pool:
  futures=[pool.submit(attempt,'fable',a,'followup') for a in ['scratch','rhiza','accord'] if (BASE/f'fable-{a}-initial/frozen').exists()]
  for f in as_completed(futures):f.result()
 print('REVISION COMPLETE',flush=True)
