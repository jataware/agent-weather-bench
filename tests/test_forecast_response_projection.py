"""Changed audit diagnostics cannot rescue cached forecast predictions."""
from types import SimpleNamespace
import numpy as np
import pytest
from assessment.assess import _forecast_probes


def run(projected, changed_forecast=False):
    base={'forecast':np.array([2.]),'audit_metric':np.array(3.)}
    changed={'forecast':np.array([4. if changed_forecast else 2.]),'audit_metric':np.array(9.)}
    hooks=SimpleNamespace(RESPONSE_PERTURBATIONS=('targets',),perturb_inputs=lambda *args:None)
    if projected:hooks.response_results=lambda r,i,p:{'forecast':r['forecast']}
    context=SimpleNamespace(spec={'probes':['responds_to_inputs'],'results':{'forecast':{'tolerance':{'atol':1e-8}},'audit_metric':{'tolerance':{'atol':1e-8}}}},
                            hooks=hooks,params={},seed=1,stage=lambda *args,**kwargs:'changed',rerun=lambda *args:(changed,{},None))
    checks={};_forecast_probes(context,base,'original',checks)
    return checks['probe.responds_to_inputs']


def test_projection_rejects_cached_prediction_even_when_audit_metric_changes():
    assert run(projected=False)['state']=='pass'  # historical default is retained
    assert run(projected=True)['state']=='fail'
    assert run(projected=True,changed_forecast=True)['state']=='pass'


def grouped_response(changes,projected=True):
    base={'hindcast':np.array([1.]),'production':np.array([2.]),'audit':np.array(3.)}
    hooks=SimpleNamespace(RESPONSE_PERTURBATIONS=tuple(changes),RESPONSE_GROUPS={'hindcast':['hindcast'],'production':['production']},perturb_inputs=lambda *args:None)
    if projected:hooks.response_results=lambda r,i,p:{name:r[name] for name in ('hindcast','production')}
    def rerun(label,folder):return changes[folder],{},None
    context=SimpleNamespace(spec={'probes':['responds_to_inputs'],'results':{name:{'tolerance':{'atol':1e-8}} for name in base}},hooks=hooks,params={},seed=1,
                            stage=lambda label,**kwargs:label.removeprefix('changed-'),rerun=rerun)
    checks={};_forecast_probes(context,base,'original',checks)
    return checks['probe.responds_to_inputs']


@pytest.mark.parametrize('cached',['hindcast','production'])
def test_each_deliverable_must_respond_so_partial_cache_cannot_pass(cached):
    changed={'hindcast':np.array([10.]),'production':np.array([20.]),'audit':np.array(30.)}
    changed[cached]=np.array([1. if cached=='hindcast' else 2.])
    row=grouped_response({'targets':changed})
    assert row['state']=='fail'
    assert row['responds_to_groups'][cached]==[]


def test_climatology_can_respond_to_targets_alone_for_both_deliverables():
    targets={'hindcast':np.array([10.]),'production':np.array([20.]),'audit':np.array(30.)}
    features={'hindcast':np.array([1.]),'production':np.array([2.]),'audit':np.array(30.)}
    row=grouped_response({'targets':targets,'features':features})
    assert row['state']=='pass'
    assert row['responds_to_groups']=={'hindcast':['targets'],'production':['targets']}


def test_different_deliverables_can_respond_to_different_relevant_inputs():
    targets={'hindcast':np.array([10.]),'production':np.array([2.]),'audit':np.array(30.)}
    features={'hindcast':np.array([1.]),'production':np.array([20.]),'audit':np.array(30.)}
    assert grouped_response({'targets':targets,'features':features},projected=False)['state']=='pass'
