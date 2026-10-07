"""No paid requests: preserve cost reservations on ambiguous provider failures."""
import httpx
import pytest

from assessment.model import Model, BudgetExceeded


def client(monkeypatch, timeout=False):
    monkeypatch.setenv('TEST_WEATHERBENCH_KEY','dummy-never-sent')
    cfg={'model':'test-model','api_key_env':'TEST_WEATHERBENCH_KEY',
         'input_usd_per_million':10,'output_usd_per_million':50,'max_usd':.12,
         'max_seconds':60,'max_total_tokens':10000,'max_output_tokens':1000,
         'effort':'high'}
    model=Model(cfg)
    def respond(request):
        if request.url.path.endswith('count_tokens'):
            assert 'output_config' not in __import__('json').loads(request.content)
            return httpx.Response(200,json={'input_tokens':1000})
        assert __import__('json').loads(request.content)['output_config']=={'effort':'high'}
        if timeout: raise httpx.ReadTimeout('Ambiguous transport timeout',request=request)
        return httpx.Response(200,json={'usage':{'input_tokens':1000,'output_tokens':100},'content':[]})
    model.client.close()
    model.client=httpx.Client(base_url='https://invalid.test',transport=httpx.MockTransport(respond))
    return model


def test_actual_usage_releases_reservation_and_includes_reasoning_output(monkeypatch):
    model=client(monkeypatch)
    try:
        model.call('system',[])
        assert model.usage['usd']==pytest.approx(.015)
        assert model.usage['unresolved_reserved_usd']==0
        assert model.usage['calls']==1
    finally: model.close()


def test_timeout_reservation_prevents_another_call_exceeding_cap(monkeypatch):
    model=client(monkeypatch,timeout=True)
    try:
        with pytest.raises(RuntimeError,match='reserved cost remains unresolved'):
            model.call('system',[])
        assert model.usage['usd']==0
        assert model.usage['unresolved_reserved_usd']==pytest.approx(.061)
        with pytest.raises(BudgetExceeded): model.call('system',[])
    finally: model.close()
