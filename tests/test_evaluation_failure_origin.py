import pytest

import weatherbench.evaluation as evaluation
from weatherbench.runtime import InfrastructureUnavailable
from weatherbench.storage import write


@pytest.mark.parametrize('origin',['controller','command','scientific-output'])
def test_runtime_unavailability_is_unresolved_but_submission_failures_are_not(tmp_path,monkeypatch,origin):
    run=tmp_path/'run';(run/'frozen').mkdir(parents=True);(run/'controller').mkdir()
    write(run/'run.json',{'task':'acmad-objective'})
    write(run/'system.json',{'runtime':{'image':'pinned','memory':'4g','cpus':2},'budget':{'command_seconds':120}})
    write(run/'artifacts.json',{})
    write(run/'controller/integrity.json',{'state':'pass'})
    monkeypatch.setattr(evaluation,'check',lambda task,frozen:{})
    monkeypatch.setattr(evaluation,'execution',lambda frozen,needs_prediction:{'replay':{'argv':['python','workflow.py','{output_dir}']}})
    def offline(*args,**kwargs):
        if origin=='controller': raise InfrastructureUnavailable('Docker unavailable')
        return {'exit_code':1 if origin=='command' else 0}
    def agreement(*args): raise ValueError('Malformed scientific array')
    monkeypatch.setattr(evaluation,'offline',offline)
    monkeypatch.setattr(evaluation,'replay_agreement',agreement)
    result=evaluation.evaluate(run,tmp_path/'output')
    assert result['replay']['state']==('unresolved' if origin=='controller' else 'fail')
