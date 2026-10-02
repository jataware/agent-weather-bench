"""Validate preserved responses; no model call or alteration of ratings."""
import json
from pilot.common import ROOT,read,write,digest
from pilot.judge import validate,evidence_ids
for run in sorted((ROOT/'runs/smoke-v3').glob('*')):
 if not (run/'judge-raw.json').exists() or (run/'judge.json').exists():continue
 payload=read(run/'judge-packet.json');raw=read(run/'judge-raw.json')
 ids=evidence_ids(payload)
 try:
  value=validate(json.loads(''.join(b['text'] for b in raw['content'] if b['type']=='text')),ids)
  value['provenance']={'model':raw['model'],'usage':read(run/'judge-usage.json'),'rubric_sha256':digest(ROOT/'rubric.yaml'),'packet_sha256':digest(run/'judge-packet.json'),'validation_note':'Individual check IDs, check:ID aliases and the metrics block are accepted as citations to evidence already present in the original packet. Ratings and citations unchanged.'}
  write(run/'judge.json',value)
  print(run.name,'validated')
 except ValueError as e:print(run.name,str(e))
