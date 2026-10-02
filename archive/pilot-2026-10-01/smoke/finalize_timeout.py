"""Freeze and score the preserved timed-out attempt; never call the agent again."""
from pilot.common import ROOT,read,write,inventory
from pilot.runtime import carry_forward
from pilot.runner import replay,offline
from pilot.checks import evaluate
r=ROOT/'runs/smoke-v3/fable-accord-followup'
if (r/'checks.json').exists():raise SystemExit('Already finalized')
m=read(r/'run.json');m.update(status='stopped',reason='API read timeout at the 600-second wall limit; final request usage unavailable',usage_incomplete=True)
write(r/'run.json',m)
files=inventory(r/'work');carry_forward(r/'work',r/'frozen');write(r/'artifacts.json',files)
before=read(ROOT/'runs/smoke-v3/fable-accord-initial/artifacts.json')
write(r/'reuse.json',{'inherited_files':len(before),'unchanged':sum(files.get(k)==v for k,v in before.items()),'modified':[k for k,v in before.items() if k in files and files[k]!=v],'added':[k for k in files if k not in before],'note':'Preserved partial work after API deadline; no fresh follow-up control.'})
rep=replay(r);ref=ROOT/'.private/smoke/followup'
inference=offline('accord',r/'frozen',r/'evaluation',['python','predict.py','--forecast','/inputs/forecast.nc','--output','/output/predictions.nc'],inputs=ref/'forecast.nc')
write(r/'inference.json',inference)
write(r/'checks.json',evaluate('seasonal',r/'frozen',ref,rep,r/'evaluation/predictions.nc'))
print('Timeout artifacts preserved and graded')
