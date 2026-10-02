"""Evaluate completed smoke attempts without exposing comparison labels or costs."""
import os,re,time
from pathlib import Path
from pilot.common import ROOT,read,write
from pilot.judge import judge

def main():
 if not os.environ.get('ANTHROPIC_API_KEY'):
  raise RuntimeError('Set ANTHROPIC_API_KEY in the controller environment')
 config=read(ROOT/'smoke/config.yaml')['judge']
 attempted=set()
 deadline=time.monotonic()+1800
 while time.monotonic()<deadline:
  for p in sorted((ROOT/'runs/smoke-v3').glob('*/checks.json')):
   run=p.parent
   if run.name in attempted or (run/'judge-usage.json').exists():continue
   attempted.add(run.name)
   print('JUDGE START '+run.name,flush=True)
   try:
    value=judge(run,config)
    print('JUDGE FINISH '+run.name+' '+str({k:v['score'] for k,v in value['ratings'].items()}),flush=True)
   except Exception as e:
    write(run/'judge-error.json',{'type':type(e).__name__,'message':str(e)[:1000]})
    print('JUDGE ERROR '+run.name+' '+str(e)[:200],flush=True)
  progress=ROOT/'.private/smoke-progress-v3.log'
  if progress.exists() and 'SMOKE ATTEMPTS COMPLETE' in progress.read_text():break
  time.sleep(5)
 print('JUDGING FINISHED',flush=True)
if __name__=='__main__':main()
