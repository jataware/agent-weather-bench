import importlib.util
import json
from pathlib import Path
import shutil
HERE=Path(__file__).resolve().parent
CONTROLS={
 'correct':{'kind':'known_correct','expect':{}},
 'independent':{'kind':'known_correct','expect':{}},
 'reordered':{'kind':'accepted_alternative','expect':{}},
 'climatology_fill':{'kind':'pitfall','pitfall':'climatology_fill','expect':{'variant':'fail','invariant.simplex_and_support':'fail'}},
 'nominal':{'kind':'pitfall','pitfall':'nominal','expect':{'variant':'fail'}},
 'percent':{'kind':'incorrect','expect':{'variant':'unresolved','invariant.simplex_and_support':'fail','probe.changed_data':'unresolved'}},
 'categorywise':{'kind':'incorrect','expect':{'probe.changed_data':'fail'}},
 'cached':{'kind':'incorrect','expect':{'probe.changed_data':'fail'}},
}
NOT_APPLICABLE={'skipped_process_step':'No process checklist.','false_method_pointer':'No scientific library is required.'}


def build(name,inputs,params,destination):
 destination=Path(destination).resolve();destination.mkdir(parents=True)
 for source in [HERE/'solve.py',HERE.parent/'science.py',HERE.parent/'reference_independent.py']:shutil.copyfile(source,destination/source.name)
 (destination/'variant.json').write_text(json.dumps({'defect':name})+'\n')
 spec=importlib.util.spec_from_file_location('objective_control_acquisition',HERE.parent/'acquisition.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
 run=a.AcquisitionLocal().run(destination,Path(inputs).resolve(),['python','solve.py','--inputs','{input_dir}','--output','{output_dir}'],destination.parent/'initial-acquisition',seconds=180)
 if run['exit_code']!=0:raise RuntimeError(run.get('stderr','Control failed'))
 for item in ['results.zarr','answer.json','report.md']:
  source=Path(run['output'])/item;shutil.copytree(source,destination/item) if source.is_dir() else shutil.copyfile(source,destination/item)
 if name=='cached':
  for item in ['results.zarr','answer.json','report.md']:
   source=destination/item;shutil.copytree(source,destination/('cached-'+item)) if source.is_dir() else shutil.copyfile(source,destination/('cached-'+item))
 return destination
