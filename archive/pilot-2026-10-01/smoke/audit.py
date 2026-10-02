"""Record bounded integrity checks, keeping scientific judgments separate."""
import json,re
from pathlib import Path
from pilot.common import ROOT,read,write,inventory,digest
base=ROOT/'runs/smoke-v3'
for run in sorted(base.glob('*')):
 if not (run/'checks.json').exists():continue
 m=read(run/'run.json');files=inventory(run/'frozen')
 frozen_matches=files==read(run/'artifacts.json')
 original=inventory(ROOT/'.private/smoke/inputs')
 inputs_match=all(files.get('inputs/'+n)==v for n,v in original.items())
 es=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
 commands=[x.get('command') or '' for x in es if x['type']=='tool']
 src='\n'.join(p.read_text(errors='replace') for p in (run/'frozen').rglob('*.py'))
 # Explicitly report presence, not proof that an import actually executes.
 toolkit_imports=sorted(set(re.findall(r'(?:from|import)\s+(africas2s|acmaddl|rosetta)\b',src)))
 excluded_import=(m['arm']!='accord' and bool(toolkit_imports)) or (m['arm']!='rhiza' and '/catalog/' in src)
 shell_network_commands=[c[:300] for c in commands if re.search(r'(^|[;&\n ])(?:curl|wget|pip)\s',c)]
 parent=Path(m['parent']) if m.get('parent') else None
 unchanged=[];changed=[];initial_model=[]
 if parent:
  before=read(parent/'artifacts.json')
  initial_model=[n for n in before if Path(n).name in ['model.nc','model.pkl','model.npz','model.json']]
  unchanged=[n for n in initial_model if files.get(n)==before[n]]
  changed=[n for n in initial_model if files.get(n)!=before[n]]
 model_files=[n for n in files if Path(n).name in ['model.nc','model.pkl','model.npz','model.json']]
 value={'frozen_inventory_matches':frozen_matches,'identical_supplied_inputs':inputs_match,
 'excluded_toolkit_import_found':excluded_import,'toolkit_imports_in_saved_code':toolkit_imports,
 'catalog_read_in_trace':any('SKILL.md' in c and '/catalog/' in c for c in commands),
 'catalog_script_execution_in_trace':any(re.search(r'(?:python|uv run)\s+/catalog/[^\s;]+\.py',c) for c in commands),
 'explicit_shell_network_commands':shell_network_commands,
 'saved_model_files':model_files,'inherited_models_unchanged':unchanged,'inherited_models_changed':changed,
 'followup_kind':('saved_model_reuse' if unchanged else 'recovery_from_incomplete_initial') if parent else 'initial_build',
 'truncated_responses':sum(x['type']=='model' and x['response']['stop_reason']=='max_tokens' for x in es),
 'review_scope':'Controller manifests, frozen hashes, input identity, source/tool traces and offline inference boundary; scientific correctness is scored separately.',
 'verification_observations_mounted':False,
 'boundary_evidence':'pilot.runner.offline mounts frozen work, writable output, and forecast-only input; network=none. Common sandbox preflight passed before launch.'}
 passed=frozen_matches and inputs_match and not excluded_import and not shell_network_commands
 value['status']='passed' if passed else 'requires_review'
 write(run/'audit.json',value)
 m['integrity']='passed' if passed else 'unreviewed';write(run/'run.json',m)
 print(run.name,value['status'],value['followup_kind'],model_files)
