"""Evidence coverage regressions: never infer correctness from source selection."""
import json

import pytest

from weatherbench.judge import packet, validate_judgment


def make_run(tmp_path):
    run = tmp_path / 'run'
    task = run / 'task'; task.mkdir(parents=True)
    (run / 'frozen').mkdir()
    (task / 'rubric.yaml').write_text('tree:\n  children:\n    - {id: science, weight: 1, evaluator: expert, evidence: []}\n')
    for name in ('prompt.md','provenance-contract.md','replay-contract.md'):
        (task / name).write_text('Declared task contract')
    evaluation = {name:{} for name in ('static','replay','prediction','integrity','forecast_outcomes')}
    return run,evaluation


def test_large_inventories_cannot_hide_declared_workflow_and_fitted_state(tmp_path):
    run,evaluation = make_run(tmp_path); frozen=run/'frozen'
    manifest={'replay':{'argv':['python','z-workflow.py','--inputs','{input_dir}']},
              'predict':{'argv':['python','z-workflow.py','--model','{model_path}']},
              'model_path':'z-state.json','retained_files':['inputs/a-inventory.json','z-workflow.py']}
    (frozen/'execution.json').write_text(json.dumps(manifest))
    (frozen/'report.txt').write_text('Forecast conclusions\n')
    (frozen/'answer.json').write_text('{"metric":0.25}')
    (frozen/'handoff.txt').write_text('Reproduce with the declared entrypoint')
    (frozen/'provenance.json').write_text('P'*60000)
    (frozen/'inputs').mkdir()
    (frozen/'inputs/a-inventory.json').write_text('I'*200000)
    (frozen/'inputs/literature-notes.txt').write_text('Published definition and assumptions')
    source='x'*20000+'\n# final inference does not refit\n'
    state='{"coefficients":['+'0,'*9999+'0]}'
    (frozen/'z-workflow.py').write_text(source)
    (frozen/'z-state.json').write_text(state)
    payload,_=packet(run,evaluation); evidence=payload['evidence']
    assert evidence['file:z-workflow.py']['text']==source
    assert evidence['file:z-state.json']['text']==state
    assert not evidence['file:z-workflow.py']['truncated']
    assert not evidence['file:z-state.json']['truncated']
    assert evidence['file:inputs/literature-notes.txt']['text']=='Published definition and assumptions'
    assert evidence['file:provenance.json']['characters_included']==6000
    assert list(evidence).index('file:z-workflow.py')<list(evidence).index('file:inputs/a-inventory.json')
    assert sum(row['characters_included'] for key,row in evidence.items() if key.startswith('file:'))<=90000
    assert packet(run,evaluation)[0]==payload


def test_large_science_file_reports_exact_prefix_and_never_earns_complete_citation(tmp_path):
    run,evaluation = make_run(tmp_path); frozen=run/'frozen'
    (frozen/'execution.json').write_text('{"replay":{"argv":["python","workflow.py"]}}')
    (frozen/'workflow.py').write_text('µ'*50000)
    payload,_=packet(run,evaluation); row=payload['evidence']['file:workflow.py']
    assert row['characters_included']==48000
    assert row['characters_total']==50000 and row['characters_omitted']==2000
    assert row['truncated'] and row['omission_reason']=='file_budget'
    judgment={'ratings':{'science':{'score':2,'reason':'Visible source','uncertainty':'',
                                  'evidence':['file:workflow.py']}},'summary':'Review','concerns':[]}
    with pytest.raises(ValueError,match='complete cited'): validate_judgment(judgment,payload)
    judgment['ratings']['science']['score']=1
    validate_judgment(judgment,payload)


def test_global_exhaustion_marks_remaining_artifacts_as_omitted(tmp_path):
    run,evaluation = make_run(tmp_path); frozen=run/'frozen'
    for name in ('report.txt','answer.json','execution.json','handoff.txt'):
        (frozen/name).write_text('X'*19000)
    (frozen/'a.py').write_text('A'*50000)
    (frozen/'z.json').write_text('Never visible')
    payload,_=packet(run,evaluation)
    rows={name:row for name,row in payload['evidence'].items() if name.startswith('file:')}
    assert sum(row['characters_included'] for row in rows.values())==90000
    assert rows['file:z.json']['text']=='' and rows['file:z.json']['truncated']
    assert rows['file:z.json']['omission_reason']=='artifact_budget'


def test_oversized_reports_cannot_exhaust_reserved_declared_science(tmp_path):
    run,evaluation=make_run(tmp_path); frozen=run/'frozen'
    for name in ('report.txt','answer.json','handoff.txt','provenance.json'):
        (frozen/name).write_text('Bulky metadata\n'*30000)
    (frozen/'execution.json').write_text('{"replay":{"argv":["python","workflow.py"]},"model_path":"model.json"}')
    (frozen/'workflow.py').write_text('Source\n'*3000)
    (frozen/'model.json').write_text('State\n'*3500)
    payload,_=packet(run,evaluation)
    evidence=payload['evidence']
    assert not evidence['file:workflow.py']['truncated']
    assert not evidence['file:model.json']['truncated']
    assert evidence['file:report.txt']['characters_included']>0
    assert evidence['file:handoff.txt']['characters_included']>0
    assert sum(row['characters_included'] for key,row in evidence.items() if key.startswith('file:'))<=90000


@pytest.mark.parametrize('manifest',[
    {'replay':{'argv':['python','../outside.py']},'model_path':'/tmp/outside.json'},
    {'replay':{'argv':['python','nested/../../outside.py']},'retained_files':['../outside.py']},
    {'replay':{'argv':'python outside.py'},'predict':[],'model_path':{'path':'../outside.py'}},
    ['../outside.py'],
])
def test_manifest_cannot_read_outside_frozen_or_execute_untrusted_paths(tmp_path,manifest):
    run,evaluation=make_run(tmp_path)
    (tmp_path/'outside.py').write_text('OUTSIDE_SECRET')
    (run/'frozen/execution.json').write_text(json.dumps(manifest))
    payload,_=packet(run,evaluation)
    assert 'OUTSIDE_SECRET' not in json.dumps(payload)
    assert 'file:../outside.py' not in payload['evidence']


def test_manifest_parse_has_size_limit_and_invalid_json_still_remains_evidence(tmp_path):
    run,evaluation=make_run(tmp_path); frozen=run/'frozen'
    (frozen/'execution.json').write_text('{'+ ' '*70000)
    payload,_=packet(run,evaluation)
    assert payload['evidence']['controller:packet_selection']['execution_declarations']['status']=='too_large'
    (frozen/'execution.json').write_text('Not JSON')
    payload,_=packet(run,evaluation)
    assert payload['evidence']['controller:packet_selection']['execution_declarations']['status']=='invalid_json'
    assert payload['evidence']['file:execution.json']['text']=='Not JSON'


def test_symlink_artifacts_remain_rejected(tmp_path):
    run,evaluation=make_run(tmp_path)
    (tmp_path/'outside.py').write_text('Secret')
    (run/'frozen/workflow.py').symlink_to(tmp_path/'outside.py')
    with pytest.raises(ValueError,match='Symlink'): packet(run,evaluation)


def test_png_and_trace_validation_are_independent_of_source_priority(tmp_path):
    from PIL import Image
    run,evaluation=make_run(tmp_path)
    Image.new('RGB',(2,2),'red').save(run/'frozen/outlook.png')
    (run/'logs').mkdir()
    rows=[{'type':'adapter','event':{'type':'execute','command':'x'*4000}} for _ in range(30)]
    (run/'logs/events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    payload,image=packet(run,evaluation)
    assert image and payload['evidence']['figure:outlook.png']['verified_png']
    assert payload['evidence']['controller:tool_trace']['omitted_tool_events']>0
    assert payload['evidence']['controller:tool_trace']['truncated']
    (run/'frozen/outlook.png').write_text('fake image')
    payload,image=packet(run,evaluation)
    assert image is None and not payload['evidence']['figure:outlook.png']['verified_png']


def test_feedback_packet_excludes_private_ledger_fields(tmp_path):
    run,evaluation=make_run(tmp_path)
    evaluation['feedback']={'scope':'development_only','max_submissions':3,
        'requests':[{'query':1,'prediction_file':'prediction.nc','status':'scored',
                     'prediction_sha256':'abc','bytes':100,'metrics':{'rmse':.3},'seconds':.2,
                     'private_error':'PRIVATE','snapshot':'/private/internal','provider':'SECRET'}],
        'limit_denials':0,'final_score_exposed':False,'final_observations_exposed':False,
        'snapshot':'/private/controller','private_error':'PRIVATE','cost_usd':77}
    payload,_=packet(run,evaluation); result=payload['evidence']['controller:feedback']
    assert result['requests'][0]['metrics']=={'rmse':.3}
    assert result['max_submissions']==3 and result['final_score_exposed'] is False
    assert 'PRIVATE' not in json.dumps(result) and 'SECRET' not in json.dumps(result)
    assert 'snapshot' not in json.dumps(result) and 'cost_usd' not in json.dumps(result)


def test_unavailable_feedback_does_not_become_zero_requests(tmp_path):
    run,evaluation=make_run(tmp_path)
    evaluation['feedback']={'state':'unavailable','scope':'development_only',
                            'reason':'PRIVATE host details','final_score_exposed':False}
    payload,_=packet(run,evaluation)
    result=payload['evidence']['controller:feedback']
    assert result['state']=='unavailable' and 'requests' not in result
    assert 'unknown' in result['reason'] and 'PRIVATE' not in json.dumps(result)


def test_yaml_source_dates_remain_serializable_scientific_metadata(tmp_path):
    run,evaluation=make_run(tmp_path)
    (run/'task/sources.yaml').write_text('paper: {published: 2024-06-18, title: WeatherBench}\n')
    payload,_=packet(run,evaluation)
    assert payload['evidence']['controller:source_record']['paper']['published']=='2024-06-18'
    json.dumps(payload,allow_nan=False)
