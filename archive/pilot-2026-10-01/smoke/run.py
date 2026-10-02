"""Authorized bounded smoke: preserve every attempt, including failures."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import os,re,json,time,traceback
from pilot.common import ROOT,write,read
from pilot.runner import run_attempt

if not os.environ.get('ANTHROPIC_API_KEY'):
 raise RuntimeError('Set ANTHROPIC_API_KEY in the controller environment')
BASE=ROOT/'runs/smoke-v3'
BASE.mkdir(parents=True,exist_ok=True)

def attempt(arm,phase,weak=False):
 label=('haiku-' if weak else 'fable-')+arm+'-'+phase
 path=BASE/label
 print('START '+label,flush=True)
 try:
  result=run_attempt('seasonal',arm,phase,'controlled',path,ROOT/'.private/smoke'/phase,
   ROOT/'.private/smoke/policy.json',
   parent=BASE/('fable-'+arm+'-initial') if phase=='followup' else None,
   config_path=ROOT/'smoke'/('weak-config.yaml' if weak else 'config.yaml'),
   spec_path=ROOT/'smoke/task.yaml',initial_inputs=ROOT/'.private/smoke/inputs')
  meta=read(result/'run.json');checks=read(result/'checks.json')
  print('FINISH '+label+' '+json.dumps({'status':meta['status'],'usage':meta['usage'],'seconds':meta['seconds'],
   'checks':[checks['passed_checks'],checks['total_checks']]}),flush=True)
  return str(result)
 except Exception as e:
  # Preserve any run artifacts and a non-secret exception type/trace for diagnosis.
  write(BASE/(label+'-controller-error.json'),{'type':type(e).__name__,'message':str(e)[:1500]})
  print('ERROR '+label+' '+type(e).__name__+': '+str(e)[:500],flush=True)
  return None

if __name__=='__main__':
 # The three arms are independent isolated benchmark attempts, not collaborators.
 with ProcessPoolExecutor(max_workers=3) as pool:
  futures={pool.submit(attempt,a,'initial'):a for a in ['scratch','rhiza','accord']}
  initial={futures[f]:f.result() for f in as_completed(futures)}
 print('INITIALS COMPLETE',flush=True)
 with ProcessPoolExecutor(max_workers=3) as pool:
  # Incomplete code is retained too; report such follow-ups as recovery.
  follow=[pool.submit(attempt,a,'followup') for a,p in initial.items() if p and (Path(p)/'frozen').exists()]
  for f in as_completed(follow): f.result()
 attempt('scratch','initial',weak=True)
 print('SMOKE ATTEMPTS COMPLETE',flush=True)
