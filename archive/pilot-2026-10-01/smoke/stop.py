import os,signal,subprocess,json
from pathlib import Path
from pilot.common import ROOT,read,write
from pilot.runtime import docker
lines=subprocess.check_output(['ps','-axo','pid,ppid,args'],text=True).splitlines()[1:]
rows=[line.strip().split(None,2) for line in lines if len(line.strip().split(None,2))==3]
roots={int(pid) for pid,ppid,cmd in rows if cmd.endswith(' -m smoke.run')}
kill=set(roots)
while True:
 more={int(pid) for pid,ppid,cmd in rows if int(ppid) in kill}
 if more<=kill:break
 kill|=more
for pid in sorted(kill):
 try:os.kill(pid,signal.SIGTERM)
 except ProcessLookupError:pass
names=[n for n in docker('ps','--format','{{.Names}}').stdout.splitlines() if n.startswith('accord-pilot-')]
for n in names:docker('rm','-f',n,check=False)
for n in names:
 if not n.endswith('gateway'):docker('network','rm',n+'-net',check=False)
for base in ['smoke-v1','smoke-v2']:
 for p in (ROOT/'runs'/base).glob('*/run.json'):
  m=read(p);ev=p.parent/'events.jsonl';rows=[json.loads(x) for x in ev.read_text().splitlines()] if ev.exists() else []
  uses=[r['response']['usage'] for r in rows if r['type']=='model'];n=sum(u['input_tokens'] for u in uses);o=sum(u['output_tokens'] for u in uses)
  m.update(status='aborted_environment_defect',excluded_from_arm_comparison=True,usage={'input_tokens':n,'output_tokens':o,'usd':(n*10+o*50)/1e6,'calls':len(uses)},reason='HDF5/NetCDF shutdown instability; preserve traces, exclude from arm comparison. Interrupted in-flight request costs may not be captured.')
  write(p,m)
  print(base,p.parent.name,m['usage']['usd'])
