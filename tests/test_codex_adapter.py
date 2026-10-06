"""Offline controller tests: no credentials, provider inference, or benchmark attempts."""
import importlib.util
import json
from pathlib import Path
import sys
import tomllib

import pytest

from weatherbench.adapters import command_driver
from weatherbench.storage import ROOT
from weatherbench.substrate_use import substrate_use
from weatherbench.systems import validate

ADAPTER = ROOT / 'systems/codex-luna/adapter.py'
spec = importlib.util.spec_from_file_location('weatherbench_codex_test_adapter', ADAPTER)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def test_codex_system_uses_existing_command_driver():
    system = validate(ROOT / 'systems/codex-luna/system.yaml')
    assert system['driver']['kind'] == 'command'
    assert system['driver']['env'] == []


def test_fresh_controller_config_excludes_host_tools_and_api_auth(tmp_path):
    config = tomllib.loads(adapter.configuration(tmp_path))
    assert config['forced_login_method'] == 'chatgpt'
    assert 'sandbox_mode' not in config
    assert config['permissions'][adapter.PROFILE] == {'filesystem':{':minimal':'read'},'network':{'enabled':False}}
    assert all(config['features'][name] is False for name in ('shell_tool','unified_exec','view_image','apps','plugins','browser_use','computer_use','hooks'))
    assert config['features']['skip_host_skill_discovery'] is True
    assert config['agents']['max_threads'] == 1
    assert all(entry['path'].endswith('/SKILL.md') and entry['enabled'] is False for entry in config['skills']['config'])
    params = adapter.thread_parameters(tmp_path)
    assert params['ephemeral'] is True and params['environments'] == [] and params['runtimeWorkspaceRoots'] == []
    assert params['selectedCapabilityRoots'] == [] and params['allowProviderModelFallback'] is False


@pytest.mark.parametrize('damage', ['environment','instructions','profile','approval','model'])
def test_effective_thread_drift_fails_closed(tmp_path, damage):
    result = {'model':adapter.MODEL,'modelProvider':'openai','approvalPolicy':'never','approvalsReviewer':'user',
              'activePermissionProfile':{'id':adapter.PROFILE,'extends':None},'cwd':str(tmp_path),
              'runtimeWorkspaceRoots':[],'instructionSources':[], 'thread':{'environments':[],'ephemeral':True},
              'sandbox':{'type':'readOnly','networkAccess':False},'serviceTier':'default','reasoningEffort':'medium'}
    adapter.validate_thread(result,tmp_path)
    if damage == 'environment': result['thread']['environments'] = [{'environmentId':'local'}]
    elif damage == 'instructions': result['instructionSources'] = ['/private/evaluator.md']
    elif damage == 'profile': result['activePermissionProfile']['id'] = ':workspace'
    elif damage == 'approval': result['approvalPolicy'] = 'on-request'
    else: result['model'] = 'other-model'
    with pytest.raises(RuntimeError,match='isolation'): adapter.validate_thread(result,tmp_path)


@pytest.mark.parametrize('arguments', [{'command':''},{'command':'  \n'},{'command':True},{'command':'cat x','cwd':'/private'},'cat x',{}])
def test_invalid_dynamic_calls_never_reach_harness(arguments,capsys):
    response = adapter.route_tool({'tool':'execute','arguments':arguments,'callId':'x'},lambda:pytest.fail('read result'))
    assert response['success'] is False
    result = json.loads(response['contentItems'][0]['text'])
    assert result['exit_code'] == 1 and result['stdout'] == ''
    assert 'nonempty string command' in result['stderr'] and 'seconds' not in result
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('tool,namespace', [('exec_command',None),('execute','host')])
def test_unexpected_dynamic_tools_remain_fatal(tool,namespace,capsys):
    with pytest.raises(ValueError,match='Unexpected'):
        adapter.route_tool({'tool':tool,'namespace':namespace,'arguments':{'command':'cat x'},'callId':'x'},
                           lambda:pytest.fail('read result'))
    assert capsys.readouterr().out == ''


def test_acquire_is_advertised_only_for_controller_declared_acquisition(tmp_path, capsys):
    acquire = {'type':'function', 'name':'acquire', 'description':'Frozen source retrieval',
               'inputSchema':{'type':'object'}}
    assert [row['name'] for row in adapter.thread_parameters(tmp_path)['dynamicTools']] == ['execute']
    assert [row['name'] for row in adapter.thread_parameters(tmp_path, {'tools':[acquire]})['dynamicTools']] == ['execute','acquire']
    params = {'tool':'acquire', 'callId':'a', 'arguments':{'url':'https://source.test/training', 'destination':'/work/raw.tif'}}
    with pytest.raises(ValueError, match='Unexpected'):
        adapter.route_tool(params, lambda:pytest.fail('undeclared retrieval'))
    response = adapter.route_tool(params, lambda:{'type':'tool_result','id':'a','exit_code':0}, {'execute','acquire'})
    assert response['success'] is True
    assert json.loads(capsys.readouterr().out) == {'type':'acquire','id':'a', **params['arguments']}


@pytest.mark.parametrize('arguments', [{}, {'url':'u','destination':False}, {'url':'u','destination':'/work/a','request':[]},
                                      {'url':'u','destination':'/work/a','host':'private'}])
def test_invalid_acquire_arguments_are_recoverable_without_retrieval(arguments, capsys):
    result = adapter.route_tool({'tool':'acquire','callId':'a','arguments':arguments},
                                lambda:pytest.fail('invalid retrieval'), {'execute','acquire'})
    assert result['success'] is False
    assert 'Nothing acquired' in json.loads(result['contentItems'][0]['text'])['stderr']
    assert capsys.readouterr().out == ''


def test_cumulative_usage_does_not_sum_updates_or_reasoning():
    params = {'tokenUsage':{'total':{'inputTokens':100,'cachedInputTokens':20,'outputTokens':50,
                                   'reasoningOutputTokens':30,'totalTokens':150},'last':{'inputTokens':2}}}
    usage = adapter.usage_from_notification(params)
    assert usage['total_tokens'] == 150 and usage['output_tokens'] == 50 and usage['reasoning_output_tokens'] == 30
    assert 'cache_write_input_tokens' not in usage
    missing = json.loads(json.dumps(params)); del missing['tokenUsage']['total']['inputTokens']
    with pytest.raises(ValueError,match='Missing'): adapter.usage_from_notification(missing)
    params['tokenUsage']['total']['inputTokens'] = True
    with pytest.raises(ValueError): adapter.usage_from_notification(params)


def test_feedback_requires_explicit_declaration_and_uses_controller_only(tmp_path, capsys):
    from weatherbench.feedback import SCORE_TOOL
    tools = adapter.thread_parameters(tmp_path, {'tools': [SCORE_TOOL]})['dynamicTools']
    assert [row['name'] for row in tools] == ['execute', 'score_development']
    params = {'tool': 'score_development', 'callId': 'score', 'arguments': {'prediction_file': 'development.nc'}}
    with pytest.raises(ValueError, match='Unexpected'):
        adapter.route_tool(params, lambda: pytest.fail('undeclared score'))
    result = adapter.route_tool(params, lambda: {'type': 'tool_result', 'id': 'score', 'exit_code': 0},
                                {'execute', 'score_development'})
    assert result['success']
    assert json.loads(capsys.readouterr().out) == {'type': 'score_development', 'id': 'score', 'prediction_file': 'development.nc'}
    with pytest.raises(ValueError, match='Duplicate'):
        adapter.advertised_tools({'tools': [SCORE_TOOL, SCORE_TOOL]})


@pytest.mark.parametrize('args', [{}, {'prediction_file': ''}, {'prediction_file': True},
                                  {'prediction_file': 'a.nc', 'target_file': 'private.nc'}])
def test_invalid_feedback_arguments_do_not_request_scores(args, capsys):
    response = adapter.route_tool({'tool': 'score_development', 'callId': 'x', 'arguments': args},
                                  lambda: pytest.fail('invalid score'), {'score_development'})
    assert not response['success'] and capsys.readouterr().out == ''
    assert 'Nothing scored' in json.loads(response['contentItems'][0]['text'])['stderr']


def test_codex_bridge_keeps_harness_and_substrate_reporting_contract(tmp_path):
    (tmp_path / 'logs').mkdir()
    # Run the actual bridge through command_driver, replacing only the remote server with
    # deterministic protocol messages. Commands can only reach this Box via the harness.
    script = tmp_path / 'offline_controller.py'
    script.write_text('''import importlib.util,json,sys
spec=importlib.util.spec_from_file_location('adapter',sys.argv[1]); a=importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
request=json.loads(sys.stdin.readline())
rows=[{'id':'invalid','method':'item/tool/call','params':{'threadId':'fresh','turnId':'one','callId':'invalid','tool':'execute','namespace':None,'arguments':{'command':''}}}]
for i,command in enumerate(['cat /substrate/notes.md','python /substrate/tool.py']):
 rows.append({'id':i,'method':'item/tool/call','params':{'threadId':'fresh','turnId':'one','callId':str(i),'tool':'execute','namespace':None,'arguments':{'command':command}}})
for total in [10,30]:
 rows.append({'method':'thread/tokenUsage/updated','params':{'threadId':'fresh','tokenUsage':{'last':{},'total':{'inputTokens':total-2,'cachedInputTokens':0,'outputTokens':2,'reasoningOutputTokens':1,'totalTokens':total}}}})
rows.append({'method':'turn/completed','params':{'threadId':'fresh','turn':{'status':'completed'}}})
responses=[]
a.bridge(iter(rows).__next__,responses.append,request,'fresh',lambda:json.loads(sys.stdin.readline()))
assert len(responses)==3 and responses[0]['result']['success'] is False
assert json.loads(responses[0]['result']['contentItems'][0]['text'])['exit_code']==1
assert all(x['result']['success'] for x in responses[1:])
''')
    class Box:
        def __init__(self): self.commands=[]
        def execute(self,command,timeout):
            self.commands.append(command)
            return {'exit_code':0,'stdout':'isolated','stderr':'','seconds':.01}
    box = Box()
    result = command_driver({'driver':{'argv':[sys.executable,str(script),str(ADAPTER)]},
                             'budget':{'max_seconds':3,'max_tool_calls':2,'command_seconds':1}},
                            tmp_path,{'type':'start'},box,tmp_path / 'logs/events.jsonl',tmp_path / 'logs/driver.stderr')
    assert result['status'] == 'submitted' and result['tool_calls'] == 2
    assert box.commands == ['cat /substrate/notes.md','python /substrate/tool.py']
    assert result['usage']['total_tokens'] == 30  # latest cumulative report, not 10+30
    assert result['usage_source'] == 'adapter_reported'
    use = substrate_use(tmp_path)
    assert (use['commands'],use['read'],use['ran'],use['ran_ok']) == (2,1,1,1)
    trace = (tmp_path / 'logs/driver.stderr').read_text()
    assert 'item/tool/call' in trace and 'thread/tokenUsage/updated' in trace and 'turn/completed' in trace


def test_command_driver_feedback_is_logged_and_never_becomes_a_shell_command(tmp_path):
    from weatherbench.feedback import SCORE_TOOL
    script = tmp_path / 'feedback_adapter.py'
    script.write_text('''import json,sys
request=json.loads(sys.stdin.readline())
assert request['tools'][0]['name']=='score_development'
print(json.dumps({'type':'score_development','id':'q','prediction_file':'development.nc'}),flush=True)
reply=json.loads(sys.stdin.readline())
assert reply['feedback_query']==1 and reply['feedback_scope']=='development_only'
print(json.dumps({'type':'final'}),flush=True)
''')
    class Box:
        def execute(self, command, timeout):
            pytest.fail('Feedback must not execute a host or scientific shell command')
        def score_development(self, prediction_file, timeout):
            assert prediction_file == 'development.nc'
            return {'exit_code':0, 'stdout':'{"rmse_mm":12.3}', 'stderr':'',
                    'feedback_scope':'development_only', 'feedback_query':1, 'feedback_remaining':4}
    result = command_driver({'driver':{'argv':[sys.executable,str(script)]},
                             'budget':{'max_seconds':3,'max_tool_calls':1,'command_seconds':1}},
                            tmp_path,{'type':'start','tools':[SCORE_TOOL]},Box(),tmp_path/'events.jsonl',tmp_path/'stderr')
    assert result['status'] == 'submitted' and result['tool_calls'] == 1
    rows = [json.loads(line) for line in (tmp_path/'events.jsonl').read_text().splitlines()]
    assert rows[0]['event']['type'] == 'score_development'
    assert rows[1]['feedback_scope'] == 'development_only'
