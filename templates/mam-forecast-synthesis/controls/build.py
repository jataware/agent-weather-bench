import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
CONTROLS = {
    'correct': {'kind': 'known_correct', 'expect': {}},
    'climatology': {'kind': 'accepted_alternative', 'expect': {}},
    'raw_models': {'kind': 'accepted_alternative', 'expect': {}},
    'reordered': {'kind': 'accepted_alternative', 'expect': {}},
    'percent': {'kind': 'incorrect', 'expect': {'invariant.probabilities_valid': 'fail'}},
    'wrong_sum': {'kind': 'incorrect', 'expect': {'invariant.probabilities_valid': 'fail'}},
    'future_pooling': {'kind': 'incorrect', 'expect': {'probe.no_future_forecasts': 'fail'}},
}
NOT_APPLICABLE = {'pitfall': 'No unique reference answer or convention-grid pitfalls in a free-method forecasting task.',
                  'skipped_process_step': 'No prescribed process checklist.', 'false_method_pointer': 'No required scientific method pointer.'}


def build(name, inputs, params, destination):
    destination = Path(destination).resolve(); destination.mkdir(parents=True)
    for source in (HERE / 'solve.py', HERE.parent / 'science.py'):
        shutil.copyfile(source, destination / source.name)
    (destination / 'variant.json').write_text(json.dumps({'defect': name})+'\n')
    spec = importlib.util.spec_from_file_location('synthesis_control_acquisition', HERE.parent / 'acquisition.py')
    acquisition = importlib.util.module_from_spec(spec); spec.loader.exec_module(acquisition)
    run = acquisition.AcquisitionLocal().run(destination, Path(inputs).resolve(),
        ['python','solve.py','--inputs','{input_dir}','--output','{output_dir}'], destination.parent / 'initial-acquisition', seconds=180)
    if run['exit_code'] != 0:
        raise RuntimeError(run.get('stderr', 'Control execution failed'))
    for name in ('results.zarr','answer.json','report.md'):
        source, target = Path(run['output']) / name, destination / name
        shutil.copytree(source,target) if source.is_dir() else shutil.copyfile(source,target)
    return destination
