"""Apply the required-fields schema fix consistently without touching submissions."""
import shutil
from pilot.common import ROOT,read,write
from pilot.checks import evaluate
for run in sorted((ROOT/'runs/smoke-v3').glob('*')):
 if not (run/'checks.json').exists():continue
 m=read(run/'run.json');before=read(run/'checks.json')
 after=evaluate('seasonal',run/'frozen',ROOT/'.private/smoke'/m['phase'],read(run/'replay.json'),run/'evaluation/predictions.nc')
 if before!=after:
  archive=run/'evaluation-revisions/before-required-fields-fix';archive.mkdir(parents=True,exist_ok=True)
  for n in ['checks.json','judge.json','judge-raw.json','judge-packet.json','judge-usage.json','judge-error.json']:
   p=run/n
   if p.exists():shutil.move(p,archive/n)
  write(run/'checks.json',after)
  write(run/'checker-revision.json',{'reason':'Compare required forecast and observed variables while permitting extra diagnostics/auxiliary metadata. No submission changed.','before_passed':before['passed_checks'],'after_passed':after['passed_checks']})
  print(run.name,before['passed_checks'],'->',after['passed_checks'])
