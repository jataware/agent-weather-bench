import json
import sys
from copy import deepcopy

import pytest

from weatherbench.adapters import command_driver
from weatherbench.evaluation import json_agreement
from weatherbench.judge import aggregate,validate_judgment
from weatherbench.storage import read,ROOT,inventory
from weatherbench.systems import validate,snapshot
from weatherbench.verification import scores


def evidence_fixture():
    rubric=read(ROOT / 'tasks/acmad-objective/rubric.yaml')
    static={'leaves':{leaf['id']:{'state':'pass' if leaf['evaluator']=='deterministic' else 'unresolved'} for leaf in rubric['tree']['children']},
            'basic_validity':{'delivery':{'state':'pass'},'execution_schema':{'state':'pass'}}}
    evaluation={'static':static,'replay':{'state':'pass'},'prediction':{'state':'unresolved'},'acquisition':{'state':'unresolved'},
                'integrity':{'state':'pass'},'forecast_outcomes':{}}
    criteria=[leaf for leaf in rubric['tree']['children'] if leaf['evaluator']!='deterministic']
    payload={'criteria':criteria,'evidence':{'file:report.txt':{'truncated':False},'figure:outlook.png':{'verified_png':True},'controller:replay':{'state':'pass'}}}
    value={'ratings':{leaf['id']:{'score':2,'reason':'Supported by specific evidence','evidence':['file:report.txt','figure:outlook.png','controller:replay'],'uncertainty':''} for leaf in criteria},
           'concerns':['An informational limitation, not an extra completion gate.'],'summary':'Reviewed'}
    return rubric,evaluation,payload,value


def test_controller_failures_cannot_be_overridden_by_a_perfect_model_rating():
    rubric,evaluation,payload,value=evidence_fixture()
    assert aggregate(rubric,evaluation,validate_judgment(value,payload))['completion']=='complete'
    evaluation['static']['leaves']['objective_product']['state']='fail'
    assert aggregate(rubric,evaluation,value)['completion']=='partial'
    evaluation['integrity']['state']='fail'
    assert aggregate(rubric,evaluation,value)['completion']=='failed_integrity'


def test_pending_execution_and_imported_integrity_are_not_success():
    rubric,evaluation,payload,value=evidence_fixture()
    assert aggregate(rubric,evaluation)['completion']=='pending'
    evaluation['integrity']['state']='unresolved'
    assert aggregate(rubric,evaluation,value)['completion']=='pending'
    evaluation['replay']['state']='fail'
    assert aggregate(rubric,evaluation,value)['outcomes']['reusable_workflow']['state']=='fail'
    evaluation['replay']['state']='unresolved'
    assert aggregate(rubric,evaluation,value)['outcomes']['reusable_workflow']['state']=='unresolved'
    evaluation['static']['leaves']['objective_product']['state']='unresolved'
    assert aggregate(rubric,evaluation,value)['outcomes']['objective_product']['state']=='unresolved'


@pytest.mark.parametrize('damage',['citation','missing','bool','truncated','figure'])
def test_judge_rejects_fabricated_or_insufficient_full_credit_evidence(damage):
    _,_,payload,value=evidence_fixture()
    name='scientific_report'
    if damage=='citation': value['ratings'][name]['evidence']=['invented-evidence']
    elif damage=='missing': del value['ratings'][name]
    elif damage=='bool': value['ratings'][name]['score']=True
    elif damage=='truncated': payload['evidence']['file:report.txt']['truncated']=True
    else: payload['evidence']['figure:outlook.png']['verified_png']=False
    with pytest.raises(ValueError): validate_judgment(value,payload)


def test_json_science_comparison_does_not_coerce_booleans_or_drop_fields():
    assert json_agreement({'rps':.1},{'rps':.10000001})
    assert not json_agreement(True,1)
    assert not json_agreement({'rps':.1},{'rps':.1,'rmse':2})
    assert not json_agreement(float('nan'),float('nan'))


def test_locked_judge_detects_code_or_identity_drift(tmp_path,monkeypatch):
    import weatherbench.judge as judge
    policy=tmp_path / 'policy.yaml'; policy.write_text('model: {model: pinned-model}')
    lock=tmp_path / 'lock.json'
    monkeypatch.setattr(judge,'CONFIG',policy); monkeypatch.setattr(judge,'LOCK',lock)
    state={'implementation.py':'unchanged'}
    monkeypatch.setattr(judge,'lock_files',lambda:state.copy())
    policy.write_text('id: test\nmodel: {model: pinned-model}')
    original=judge.create_lock()
    assert judge.verify_lock()['fingerprint']==original['fingerprint']
    state['implementation.py']='changed'
    with pytest.raises(ValueError,match='changed after locking'): judge.verify_lock()
    state['implementation.py']='unchanged'
    value=json.loads(lock.read_text()); value['fingerprint']='forged'; lock.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='identity'): judge.verify_lock()


def test_command_adapter_routes_tools_through_boundary_and_records_unknown_usage(tmp_path):
    class Box:
        commands=[]
        def execute(self,command,timeout):
            self.commands.append(command)
            return {'exit_code':0,'stdout':'isolated result','stderr':''}
    script=tmp_path / 'driver.py'
    script.write_text("import json,sys\nr=json.loads(sys.stdin.readline())\nprint(json.dumps({'type':'execute','id':'a','command':'do work'}),flush=True)\nr=json.loads(sys.stdin.readline())\nassert r['stdout']=='isolated result'\nprint(json.dumps({'type':'final'}),flush=True)\n")
    config={'driver':{'argv':[sys.executable,str(script)]},'budget':{'max_seconds':3,'max_tool_calls':1,'command_seconds':1}}
    box=Box()
    result=command_driver(config,tmp_path,{'type':'start'},box,tmp_path / 'events.jsonl',tmp_path / 'stderr')
    assert box.commands==['do work']
    assert result['status']=='submitted'
    assert result['usage'] is None and result['usage_source']=='unknown'
    events=[json.loads(line) for line in (tmp_path / 'events.jsonl').read_text().splitlines()]
    assert any(event['type']=='tool_result' for event in events)


def test_partial_adapter_lines_cannot_bypass_deadline(tmp_path):
    script=tmp_path / 'driver.py'
    script.write_text("import sys,time\nsys.stdin.readline()\nsys.stdout.write('{');sys.stdout.flush();time.sleep(30)\n")
    config={'driver':{'argv':[sys.executable,str(script)]},'budget':{'max_seconds':1,'max_tool_calls':1,'command_seconds':1}}
    result=command_driver(config,tmp_path,{},None,tmp_path / 'events.jsonl',tmp_path / 'stderr')
    assert result['status']=='time_limit' and result['seconds']<4


def test_substrate_symlink_cannot_include_controller_references(tmp_path):
    system=read(ROOT / 'systems/example/system.yaml')
    system['substrate']['paths']=['leak/private.txt']
    outside=tmp_path / 'outside'; outside.mkdir(); (outside / 'private.txt').write_text('reference')
    home=tmp_path / 'system'; home.mkdir(); (home / 'leak').symlink_to(outside,target_is_directory=True)
    path=home / 'system.yaml'; path.write_text(json.dumps(system))
    with pytest.raises(ValueError,match='inside the system'): snapshot(path,tmp_path / 'snapshot')


def test_forecast_outcomes_are_continuous_and_keep_ties_in_middle_category():
    import numpy as np
    training=np.array([0.,10.,20.])[:,None,None]
    p=np.array([0.,1.,0.])[None,:,None,None]
    metrics,target=scores(p,np.array([[[10.]]]),np.array([[[10.]]]),training)
    assert metrics['RPS']['submitted']==0 and metrics['RMSE_mm']['submitted']==0
    assert target[0,1,0,0]==1


def test_native_assessment_freezes_response_caches_calls_and_checks_tampering(tmp_path,monkeypatch):
    import shutil
    from PIL import Image
    import weatherbench.judge as judge
    import weatherbench.model as model
    import weatherbench.runner as runner
    import weatherbench.evaluation as evaluation_module
    from weatherbench.storage import write
    _,evaluation,_,value=evidence_fixture()
    run=tmp_path / 'run'; run.mkdir()
    (run / 'task').mkdir(); (run / 'system').mkdir(); (run / 'frozen').mkdir()
    for name in ('task.yaml','rubric.yaml','input-manifest.json','prompt.md'):
        shutil.copyfile(ROOT / 'tasks/acmad-objective' / name,run / 'task' / name)
    for name in ('provenance-contract.md','replay-contract.md'):
        shutil.copyfile(ROOT / 'tasks' / name,run / 'task' / name)
    (run / 'frozen/report.txt').write_text('Submission evidence for the simulated judge lifecycle.')
    Image.new('RGB',(4,4),'white').save(run / 'frozen/outlook.png')
    write(run / 'run.json',{'task':'acmad-objective','kind':'harness_fixture','task_approvals':{}})
    for directory,manifest in (('frozen','artifacts.json'),('task','task-manifest.json'),('system','substrate-manifest.json')):
        write(run / manifest,inventory(run / directory))
    monkeypatch.setattr(judge,'verify_lock',lambda:{'fingerprint':'abcdef0123456789','model':'simulated'})
    monkeypatch.setattr(runner,'reference_integrity',lambda task:None)
    monkeypatch.setattr(evaluation_module,'evaluate',lambda run,directory:deepcopy(evaluation))
    class Model:
        calls=0
        usage={'calls':1,'usd':.01}
        def __init__(self,config): pass
        def call(self,system,messages):
            Model.calls+=1
            packet=json.loads(messages[0]['content'][0]['text'])
            assert 'system' not in packet and 'model' not in packet
            return {'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps(value)}]}
        def close(self): pass
    monkeypatch.setattr(model,'Model',Model)
    first=judge.assess(str(run))
    assert first['completion']=='complete' and first['benchmark_eligible'] is False
    directory=__import__('pathlib').Path(first['assessment_directory'])
    assert (directory / 'judge-raw.json').is_file() and (directory / 'judge-packet.json').is_file()
    assert judge.assess(str(run))==first and Model.calls==1
    second=judge.assess(str(run),retry=True)
    assert second['assessment_directory']!=first['assessment_directory'] and Model.calls==2
    (run / 'frozen/report.txt').write_text('tampered')
    with pytest.raises(ValueError,match='Frozen submission changed'): judge.assess(str(run))


def test_installed_dependency_versions_are_enforced(monkeypatch):
    import weatherbench.judge as judge
    monkeypatch.setattr(judge,'version',lambda name:'unexpected-version')
    with pytest.raises(ValueError,match='dependency drift'): judge.dependency_versions()


def test_acmad_disagreement_uses_native_percent_precision():
    import numpy as np
    import xarray as xr
    from weatherbench.task_tools.references import acmad_objective
    components=[]
    for below in (np.float32(33.333333),np.float32(33.333340),np.float32(33.333350)):
        components.append(xr.Dataset({k:(('lat','lon'),np.array([[v]],dtype='float32'))
            for k,v in [('below',below),('normal',np.float32(30)),('above',np.float32(70)-below)]},coords={'lat':[0.],'lon':[0.]}))
    result=acmad_objective(components)
    expected=float(components[2].below.item())-float(components[0].below.item())
    assert abs(result.disagreement_pp.sel(tercile='below').item()-expected)<1e-12


@pytest.mark.parametrize('continue_after_failure',[True,False])
def test_suite_records_failures_and_honors_continue_policy(tmp_path,monkeypatch,continue_after_failure):
    import weatherbench.runner as runner
    import weatherbench.judge as judge
    from weatherbench.storage import write
    monkeypatch.setattr(runner,'STATE',tmp_path)
    monkeypatch.setattr(runner,'preflight',lambda image:None)
    monkeypatch.setattr(runner,'reference_integrity',lambda task:None)
    monkeypatch.setattr(judge,'verify_lock',lambda:None)
    calls=[]
    def attempt(task,system,parent,judge):
        calls.append((task,parent))
        raise RuntimeError('Adapter failed during execution')
    monkeypatch.setattr(runner,'run_task',attempt)
    config=tmp_path / 'sequence.yaml'
    write(config,{'system':'example','tasks':['acmad-objective','wvg-definition-audit'],
        'condition':'retained','continue_after_failure':continue_after_failure})
    result=runner.suite(config,judge='none')
    assert len(calls)==(2 if continue_after_failure else 1)
    assert all(step['status']=='harness_error' for step in result['steps'])
    record=read(__import__('pathlib').Path(result['suite']) / 'suite.json')
    assert record['status']==('finished' if continue_after_failure else 'stopped_after_failure')
