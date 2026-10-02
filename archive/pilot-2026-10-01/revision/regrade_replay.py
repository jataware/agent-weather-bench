"""Apply declared-output comparison to every revised attempt, preserving old records."""
import shutil
import xarray as xr
from pilot.common import ROOT,read,write
from pilot.runner import replay_answer_matches
from pilot.checks import evaluate
changed=[]
for r in sorted((ROOT/'runs/revision-v1').glob('*')):
 if not (r/'checks.json').exists():continue
 meta=read(r/'run.json');old=read(r/'replay.json');new=dict(old)
 try:
  passed=old['exit_code']==0 and replay_answer_matches(read(r/'replay/answer.json'),read(r/'frozen/answer.json'),'seasonal')
  for name in ['training.nc','development.nc']:
   xr.testing.assert_allclose(xr.load_dataset(r/'replay'/name),xr.load_dataset(r/'frozen'/name))
 except (OSError,ValueError,AssertionError):passed=False
 if passed==old['passed']:continue
 archive=r/'evaluation-revisions/before-required-answer-fields';archive.mkdir(parents=True,exist_ok=True)
 for n in ['replay.json','checks.json','judge.json','judge-raw.json','judge-packet.json','judge-usage.json','judge-error.json']:
  if (r/n).exists():shutil.move(r/n,archive/n)
 new.update(passed=passed,detail='Offline replay compared all declared answer fields and numerical arrays. Optional session notes outside the task schema are not scientific replay outputs.')
 write(r/'replay.json',new)
 write(r/'checks.json',evaluate('seasonal',r/'frozen',ROOT/'.private/smoke'/meta['phase'],new,r/'evaluation/predictions.nc'))
 write(r/'checker-revision.json',{'reason':'Compare declared answer fields, excluding optional session notes. Numerical arrays still must match; no submission modified.','old_replay_passed':old['passed'],'new_replay_passed':passed})
 changed.append(str(r))
write(ROOT/'revision/regraded-runs.json',changed)
print('Regraded:',[__import__('pathlib').Path(x).name for x in changed])
