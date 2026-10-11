import json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
CONTROLS={
 'correct':{'kind':'known_correct','expect':{}},
 'clip_quantization':{'kind':'accepted_alternative','expect':{},'matched':{'negative_increments':['clip_quantization']}},
 'float32':{'kind':'accepted_alternative','expect':{}},
 'independent':{'kind':'known_correct','expect':{}},
 'reordered':{'kind':'accepted_alternative','expect':{}},
 'sum_rates':{'kind':'pitfall','pitfall':'sum_rates','expect':{'variant':'fail'}},
 'same_lead':{'kind':'pitfall','pitfall':'same_lead','expect':{'variant':'fail'}},
 'false_claim':{'kind':'incorrect','expect':{'claim.direction':'fail'}},
 'bulletin':{'kind':'incorrect','expect':{'probe.bulletin_independence':'fail'}},
 'cached':{'kind':'incorrect','expect':{'probe.changed_data':'fail'}},
}
NOT_APPLICABLE={'held_out_observations':'This computes forecast revisions; no verification observations or skill ranking.'}
def build(name,inputs,params,destination):
 destination=Path(destination);destination.mkdir(parents=True)
 for src in [HERE/'solve.py',HERE.parent/'science.py',HERE.parent/'reference_independent.py']:shutil.copyfile(src,destination/src.name)
 (destination/'variant.json').write_text(json.dumps({'defect':name}))
 subprocess.run([sys.executable,'solve.py','--inputs',str(inputs),'--output',str(destination)],cwd=destination,check=True,capture_output=True,text=True)
 if name=='cached':
  shutil.copytree(destination/'results.zarr',destination/'cached-results.zarr');shutil.copyfile(destination/'answer.json',destination/'cached-answer.json')
  (destination/'cached.py').write_text("import argparse,shutil\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--inputs');p.add_argument('--output');a=p.parse_args();o=Path(a.output);o.mkdir(parents=True,exist_ok=True);shutil.copytree('cached-results.zarr',o/'results.zarr');shutil.copyfile('cached-answer.json',o/'answer.json')\n")
  p=destination/'answer.json';a=json.loads(p.read_text());a['run']['argv'][1]='cached.py';p.write_text(json.dumps(a))
 return destination
