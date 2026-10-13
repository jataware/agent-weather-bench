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


def cached_client(monkeypatch, statuses=(200,), usage=None, max_context_tokens=None):
    import json
    monkeypatch.setenv('TEST_WEATHERBENCH_KEY','dummy-never-sent')
    cfg={'model':'test-model','api_key_env':'TEST_WEATHERBENCH_KEY','input_usd_per_million':2,'output_usd_per_million':10,
         'cache':True,'cache_write_usd_per_million':2.5,'cache_read_usd_per_million':.1,'max_usd':5,'max_seconds':600,
         'max_total_tokens':10_000_000,'max_output_tokens':1000,'max_retries':3}
    if max_context_tokens: cfg['max_context_tokens']=max_context_tokens
    model=Model(cfg)
    remaining=list(statuses)
    seen=[]
    def respond(request):
        body=json.loads(request.content)
        if request.url.path.endswith('count_tokens'):
            return httpx.Response(200,json={'input_tokens':1000})
        seen.append(body)
        status=remaining.pop(0)
        if status!=200: return httpx.Response(status,json={'error':{'type':'overloaded_error'}})
        return httpx.Response(200,json={'usage':usage or {'input_tokens':100,'output_tokens':10,'cache_creation_input_tokens':1000,'cache_read_input_tokens':5000},'content':[]})
    model.client.close()
    model.client=httpx.Client(base_url='https://invalid.test',transport=httpx.MockTransport(respond))
    return model, seen


def test_cached_calls_are_priced_by_the_provider_counters_and_ask_for_automatic_caching(monkeypatch):
    model,seen=cached_client(monkeypatch)
    try:
        model.call('system',[{'role':'user','content':'x'}])
        assert seen[0]['cache_control']=={'type':'ephemeral'}
        assert model.usage['usd']==pytest.approx((100*2+10*10+1000*2.5+5000*.1)/1e6)
        assert (model.usage['input_tokens'],model.usage['cache_write_input_tokens'],model.usage['cached_input_tokens'],model.usage['output_tokens'])==(100,1000,5000,10)
        assert model.usage['total_tokens']==6110 and model.usage['unresolved_reserved_usd']==0
    finally: model.close()


def test_a_refused_request_is_retried_after_a_pause_and_not_billed(monkeypatch):
    import assessment.model as module
    pauses=[]
    monkeypatch.setattr(module.time,'sleep',lambda s: pauses.append(s))
    model,seen=cached_client(monkeypatch,statuses=(529,429,200))
    try:
        model.call('system',[{'role':'user','content':'x'}])
        assert len(seen)==3 and pauses==[5,15]
        assert model.usage['calls']==1 and model.usage['retries']==2 and model.usage['unresolved_reserved_usd']==0
    finally: model.close()


def test_retries_are_bounded_and_the_final_refusal_is_an_error(monkeypatch):
    import assessment.model as module
    monkeypatch.setattr(module.time,'sleep',lambda s: None)
    model,seen=cached_client(monkeypatch,statuses=(529,529,529,529))
    try:
        with pytest.raises(RuntimeError,match='HTTP 529'): model.call('system',[])
        assert len(seen)==4 and model.usage['retries']==3
    finally: model.close()


def test_a_prompt_that_no_longer_fits_the_context_stops_the_run(monkeypatch):
    model,seen=cached_client(monkeypatch,max_context_tokens=1500)
    try:
        with pytest.raises(BudgetExceeded,match='Context window'): model.call('system',[])
        assert seen==[]
    finally: model.close()


def test_compaction_elides_the_oldest_long_tool_results_and_keeps_recent_ones():
    import json
    from assessment.adapters import compact
    def turn(i): return {"role":"user","content":[{"type":"tool_result","tool_use_id":f"t{i}","content":json.dumps({"exit_code":i%2,"stdout":"x"*1000})}]}
    messages=[{"role":"user","content":"request"}]+[m for i in range(12) for m in ({"role":"assistant","content":[]},turn(i))]
    # 12 long results; the newest message and the 8 before it stay whole, so 3 are eligible and half of them (at least one) go.
    assert compact(messages)==1
    elided=[json.loads(m["content"][0]["content"]) for m in messages if m["role"]=="user" and isinstance(m["content"],list)]
    assert elided[0]["elided"] and elided[0]["exit_code"]==0
    assert all("stdout" in row for row in elided[1:])
    assert compact(messages)==1 and compact(messages)==1 and compact(messages)==0   # one at a time until only recent ones remain
    assert json.loads(messages[-1]["content"][0]["content"])["stdout"]


def test_a_transport_error_ends_the_run_but_keeps_the_usage_record(monkeypatch, tmp_path):
    """Arm 3 of the 13 October ablation died on an SSL read error after delivering; the usage must survive that path."""
    import json
    from assessment import adapters

    class FakeModel:
        def __init__(self, cfg):
            self.usage = {'input_tokens': 0, 'output_tokens': 0, 'usd': 0.0, 'calls': 0}
            self.closed = False
        def call(self, system, messages, tools):
            self.usage['calls'] += 1
            if self.usage['calls'] == 1:
                self.usage['output_tokens'] += 50; self.usage['usd'] += .01
                return {'content': [{'type': 'tool_use', 'id': 't1', 'name': 'execute', 'input': {'command': 'echo hi'}}], 'stop_reason': 'tool_use'}
            raise httpx.ReadError('[SSL: SSLV3_ALERT_BAD_RECORD_MAC] ssl/tls alert bad record mac')
        def close(self): self.closed = True

    class FakeBox:
        def execute(self, command, timeout): return {'exit_code': 0, 'stdout': 'hi', 'stderr': ''}

    monkeypatch.setattr('assessment.model.Model', FakeModel)
    config = {'driver': {'kind': 'anthropic', 'max_turns': 5}, 'budget': {'max_seconds': 60, 'max_tool_calls': 10, 'command_seconds': 10}}
    log = tmp_path / 'events.jsonl'
    result = adapters.anthropic_driver(config, {'tools': []}, FakeBox(), log)
    assert result['status'] == 'execution_error'
    assert result['reason'].startswith('ReadError: [SSL: SSLV3_ALERT_BAD_RECORD_MAC]')
    assert result['tool_calls'] == 1
    assert result['usage']['calls'] == 2 and result['usage']['usd'] == pytest.approx(.01)
    rows = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    assert rows[-1]['type'] == 'stop' and 'ReadError' in rows[-1]['reason']


def test_a_broken_connection_is_retried_with_the_interrupted_calls_cost_kept_reserved(monkeypatch):
    """A TLS read error mid-response (13 October 2026, twice) is retried after a pause; the first call's reservation stays."""
    import json
    monkeypatch.setenv('TEST_WEATHERBENCH_KEY','dummy-never-sent')
    cfg={'model':'test-model','api_key_env':'TEST_WEATHERBENCH_KEY','input_usd_per_million':2,'output_usd_per_million':10,
         'max_usd':5,'max_seconds':600,'max_total_tokens':10_000_000,'max_output_tokens':1000,'max_retries':3}
    model=Model(cfg)
    attempts=[]
    def respond(request):
        if request.url.path.endswith('count_tokens'):
            return httpx.Response(200,json={'input_tokens':1000})
        attempts.append(1)
        if len(attempts)==1: raise httpx.ReadError('[SSL: SSLV3_ALERT_BAD_RECORD_MAC] ssl/tls alert bad record mac',request=request)
        return httpx.Response(200,json={'usage':{'input_tokens':1000,'output_tokens':100},'content':[]})
    model.client.close()
    model.client=httpx.Client(base_url='https://invalid.test',transport=httpx.MockTransport(respond))
    pauses=[]
    monkeypatch.setattr('assessment.model.time.sleep', lambda s: pauses.append(s))
    try:
        model.call('system',[])
        assert len(attempts)==2 and pauses==[5]
        assert model.usage['retries']==1 and model.usage['calls']==1
        assert model.usage['usd']==pytest.approx(.003)                      # the completed call
        assert model.usage['unresolved_reserved_usd']>0                     # the interrupted one stays reserved
    finally: model.close()


def test_timeouts_still_end_the_run(monkeypatch):
    model=client(monkeypatch,timeout=True)
    try:
        with pytest.raises(RuntimeError,match='no automatic retry'):
            model.call('system',[])
    finally: model.close()
