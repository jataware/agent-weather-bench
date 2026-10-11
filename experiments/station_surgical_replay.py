"""Original versus one-expression repair, executed only in offline Docker."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.execute import Docker
from assessment.storage import digest, inventory, read, write

IMAGE = 'sha256:08dbb4fce25955523a4c3caa3e2efdfb75b960dae3d2b8f3b92746e7f19f7c49'
RUN = ROOT / 'var/runs/20261005T181603-station-verification-codex-luna-ff16df'
DESTINATION = ROOT / 'var/review/station-surgical-replay-20261008'
OUTPUT = ROOT / 'experiments/station-surgical-replay-2026-10-08.json'


def main():
    import numpy as np
    import xarray as xr
    if DESTINATION.exists() or OUTPUT.exists():
        raise ValueError('Never overwrite earlier execution evidence')
    code_path = RUN / 'frozen/workflow.py'
    before = code_path.read_text()
    old, new = 'if v==2: truth=truth-273.15', 'if v in (2,4): truth=truth-273.15'
    if digest(code_path) != '531e0a2a7fb7149303b14c456a7505aa6e1f8fb91bf945fcc49cb3e2c379d3ca' or before.count(old) != 1:
        raise ValueError('Historical source changed')
    original_inventory, input_inventory = inventory(RUN / 'frozen'), inventory(RUN / 'inputs')
    if original_inventory != read(RUN / 'artifacts.json'):
        raise ValueError('Original frozen submission changed')
    reference_path = ROOT / 'archive/evaluator-v1-2026-10/weatherbench/task_tools/station_verification/reference.py'
    spec = importlib.util.spec_from_file_location('trusted_station_reference', reference_path)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    expected = reference.build(RUN / 'inputs')
    executor = Docker(IMAGE, memory='1536m', cpus=2)
    rows, datasets = {}, {}
    for label, code in [('original', before), ('single_expression_repair', before.replace(old, new))]:
        source = DESTINATION / label / 'submission'
        source.mkdir(parents=True)
        (source / 'workflow.py').write_text(code)
        argv = ['python', 'workflow.py', '--inputs', '{input_dir}', '--outputs', '{output_dir}']
        record = executor.run(source, RUN / 'inputs', argv, DESTINATION / label / 'execution', seconds=120)
        write(DESTINATION / label / 'execution.json', record)
        if record.get('infrastructure_unavailable') or record['exit_code'] != 0:
            rows[label] = {'execution': record, 'numeric_comparison': 'not performed'}
            continue
        with xr.open_dataset(Path(record['output']) / 'scores.nc') as ds:
            actual = ds.load()
        datasets[label] = actual
        fields = {}
        for name in reference.FIELDS:
            aligned = actual[name].transpose(*expected[name].dims).values
            target = expected[name].values
            finite = np.isfinite(aligned) & np.isfinite(target)
            error = aligned[finite].astype(float) - target[finite].astype(float)
            fields[name] = {'nonfinite_mask_agrees': bool(np.array_equal(np.isfinite(aligned), np.isfinite(target))),
                            'max_absolute_error': float(np.max(np.abs(error))) if error.size else None,
                            'agrees_at_1e_7': bool(np.allclose(aligned, target, rtol=0, atol=1e-7, equal_nan=True))}
        rows[label] = {'exit_code': record['exit_code'], 'executor': record['executor'],
                       'source_sha256': digest(source / 'workflow.py'), 'fields': fields,
                       'output_inventory': inventory(Path(record['output']))}
    unaffected = None
    if len(datasets) == 2:
        unaffected = all(np.array_equal(datasets['original'][name].values,
                                       datasets['single_expression_repair'][name].values, equal_nan=True)
                         for name in reference.FIELDS if name != 'diagnostic_rmse')
    originals_preserved = inventory(RUN / 'frozen') == original_inventory and inventory(RUN / 'inputs') == input_inventory
    result = {'schema_version': 1, 'runtime_image': IMAGE, 'new_model_calls': 0,
              'scope': 'Two fresh serial Docker executions on unchanged historical inputs; constructed repair changes one scientific expression only.',
              'source_run': RUN.name, 'change': {'before': old, 'after': new, 'count': 1},
              'trusted_reference': {'path': str(reference_path.relative_to(ROOT)), 'sha256': digest(reference_path)},
              'input_inventory': input_inventory, 'rows': rows,
              'unaffected_fields_bitwise_equal': unaffected, 'originals_preserved': originals_preserved,
              'limitation': 'This repair experiment establishes a localized implementation error, not the result of another agent attempt or a complete packaging assessment.'}
    if not originals_preserved:
        raise ValueError('Immutable original changed')
    write(OUTPUT, result)
    print(json.dumps({'output': str(OUTPUT.relative_to(ROOT)), 'originals_preserved': originals_preserved,
                      'unaffected_fields_bitwise_equal': unaffected,
                      'fields_agree': {label: {name: field['agrees_at_1e_7'] for name, field in row.get('fields', {}).items()}
                                       for label, row in rows.items()}}, indent=2))


if __name__ == '__main__':
    main()
