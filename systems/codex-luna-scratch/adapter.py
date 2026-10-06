"""Trusted Codex controller adapted to the existing Docker-only harness protocol.

Pinned to CLI 0.160.0, whose no-environment tool registry was checked offline.
No model-generated command ever runs on this controller. No API fallback.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

VERSION = "0.160.0"
MODEL = "gpt-6-luna"
PROFILE = "weatherbench-no-host"
INSTRUCTIONS = (
    "Carry out the weather research task using execute for commands in the isolated "
    "Docker runtime. Paths /task, /substrate, /work/inputs, /work/submission and /work/state "
    "are inside that runtime. Read the task and contracts. Write the requested deliverables "
    "under /work/submission and retained material under /work/state."
)
TOOL = {"type":"function", "name":"execute", "description":"Run a command in the isolated scientific runtime.",
        "inputSchema":{"type":"object", "properties":{"command":{"type":"string"}},
                       "required":["command"], "additionalProperties":False}}


def emit(value):
    print(json.dumps(value, allow_nan=False), flush=True)


def trace(direction, value):
    # stderr is retained by command_driver as logs/driver.stderr. Never log auth RPCs.
    print(json.dumps({"type":"codex_rpc", "direction":direction, "message":value}, allow_nan=False),
          file=sys.stderr, flush=True)


def configuration(home):
    disabled = ["shell_tool", "unified_exec", "view_image", "apps", "plugins", "browser_use",
                "computer_use", "image_generation", "multi_agent", "code_mode", "hooks",
                "skill_search", "memories", "shell_snapshot", "goals", "auth_elicitation",
                "unbounded_connection_retries", "remote_plugin", "recommended_plugins"]
    lines = [f'model = "{MODEL}"', 'model_provider = "openai"', 'forced_login_method = "chatgpt"',
             'approval_policy = "never"', f'default_permissions = "{PROFILE}"',
             'project_doc_max_bytes = 0', 'web_search = "disabled"', 'analytics.enabled = false',
             f'[permissions.{PROFILE}.filesystem]', '":minimal" = "read"',
             f'[permissions.{PROFILE}.network]', 'enabled = false',
             '[features]', *[f'{key} = false' for key in disabled],
             'code_mode_host = true', 'skip_host_skill_discovery = true', '[agents]', 'max_threads = 1']
    # Disabling a directory does not disable its skill: exact SKILL.md paths are required.
    skills = {home / 'skills/.system' / name / 'SKILL.md'
              for name in ('imagegen', 'openai-docs', 'skill-creator', 'skill-installer', 'review-agent')}
    for root in (Path.home() / '.agents/skills', Path('/etc/codex/skills')):
        if root.is_dir(): skills.update(root.rglob('SKILL.md'))
    for path in sorted(skills):
        lines += ['[[skills.config]]', f'path = {json.dumps(str(path))}', 'enabled = false']
    return '\n'.join(lines) + '\n'


def advertised_tools(request=None):
    tools = [TOOL]
    for tool in (request or {}).get('tools', []):
        if (not isinstance(tool, dict) or tool.get('name') not in ('execute', 'acquire', 'score_development')
            or tool.get('type') != 'function' or not isinstance(tool.get('inputSchema'), dict)):
            raise ValueError('Unexpected controller tool declaration')
        if tool['name'] in ('acquire', 'score_development'):
            if any(row['name'] == tool['name'] for row in tools):
                raise ValueError('Duplicate controller tool declaration')
            tools.append(tool)
    return tools


def thread_parameters(public, request=None):
    return {"model":MODEL, "modelProvider":"openai", "allowProviderModelFallback":False,
            "cwd":str(public), "ephemeral":True, "environments":[], "runtimeWorkspaceRoots":[],
            "selectedCapabilityRoots":[], "permissions":PROFILE, "approvalPolicy":"never",
            "serviceTier":"default", "config":{"model_reasoning_effort":"medium"},
            "approvalsReviewer":"user", "baseInstructions":INSTRUCTIONS, "developerInstructions":"",
            "dynamicTools":advertised_tools(request), "experimentalRawEvents":True}


def validate_thread(result, public):
    if (result.get('model') != MODEL or result.get('modelProvider') != 'openai'
        or result.get('approvalPolicy') != 'never' or result.get('approvalsReviewer') != 'user'
        or result.get('activePermissionProfile') != {'id':PROFILE, 'extends':None}
        or result.get('cwd') != str(public) or result.get('runtimeWorkspaceRoots') != []
        or result.get('serviceTier') != 'default' or result.get('reasoningEffort') != 'medium'
        or result.get('instructionSources') != [] or result['thread'].get('environments') != []
        or result['thread'].get('ephemeral') is not True
        or result.get('sandbox', {}).get('type') != 'readOnly'
        or result.get('sandbox', {}).get('networkAccess') is not False):
        raise RuntimeError('Codex effective isolation does not match the tested configuration')


def usage_from_notification(params):
    # total is cumulative; last and reasoningOutputTokens are not additional charges.
    total = params['tokenUsage']['total']
    keys = {'inputTokens':'input_tokens', 'cachedInputTokens':'cached_input_tokens',
            'cacheWriteInputTokens':'cache_write_input_tokens', 'outputTokens':'output_tokens',
            'reasoningOutputTokens':'reasoning_output_tokens', 'totalTokens':'total_tokens'}
    required = set(keys) - {'cacheWriteInputTokens'}
    if not required <= total.keys(): raise ValueError('Missing Codex provider token counters')
    usage = {target:total[source] for source, target in keys.items() if source in total}
    if any(type(v) is not int or v < 0 for v in usage.values()):
        raise ValueError('Invalid Codex provider token counters')
    return usage


def route_tool(params, read_result, allowed_tools=('execute',)):
    args = params.get('arguments')
    tool = params.get('tool')
    if tool not in allowed_tools or tool not in ('execute', 'acquire', 'score_development') or params.get('namespace') is not None:
        raise ValueError('Unexpected Codex dynamic tool request')
    if tool == 'execute':
        valid = (isinstance(args, dict) and set(args) == {'command'}
                 and isinstance(args['command'], str) and bool(args['command'].strip()))
        error = 'Invalid execute arguments: provide exactly one nonempty string command. Nothing executed.'
    elif tool == 'acquire':
        valid = (isinstance(args, dict) and {'url', 'destination'} <= set(args) <= {'url', 'destination', 'request'}
                 and all(isinstance(args[name], str) and args[name].strip() for name in ('url', 'destination'))
                 and ('request' not in args or isinstance(args['request'], dict)))
        error = 'Invalid acquire arguments: provide nonempty url and destination strings, and an optional request object. Nothing acquired.'
    else:
        valid = (isinstance(args, dict) and set(args) == {'prediction_file'}
                 and isinstance(args['prediction_file'], str) and bool(args['prediction_file'].strip()))
        error = 'Invalid score_development arguments: provide exactly one nonempty prediction_file. Nothing scored.'
    if not valid:
        result = {'exit_code':1, 'stdout':'',
                  'stderr':error}
        return {'contentItems':[{'type':'inputText', 'text':json.dumps(result)}], 'success':False}
    emit({'type':tool, 'id':params['callId'], **args})
    result = read_result()
    if result.get('type') != 'tool_result' or result.get('id') != params['callId']:
        raise ValueError('Mismatched harness tool result')
    return {'contentItems':[{'type':'inputText', 'text':json.dumps(result, allow_nan=False)}],
            'success':result.get('exit_code') == 0}


def bridge(read_rpc, send_rpc, request, thread_id, read_result):
    allowed_tools = {tool['name'] for tool in advertised_tools(request)}
    while True:
        message = read_rpc()
        trace('server', message)
        if 'id' in message and 'method' in message:
            if message['method'] != 'item/tool/call':
                raise RuntimeError('Unexpected server request; no approvals or fallback are permitted')
            params = message['params']
            if params.get('threadId') != thread_id:
                raise RuntimeError('Unexpected Codex thread')
            send_rpc({'id':message['id'], 'result':route_tool(params, read_result, allowed_tools)})
        elif message.get('method') == 'thread/tokenUsage/updated':
            if message['params']['threadId'] != thread_id: raise RuntimeError('Unexpected usage thread')
            emit({'type':'usage', 'usage':usage_from_notification(message['params']),
                  'source':'codex_provider_cumulative_tokens', 'billing':'chatgpt_subscription_usd_unknown'})
        elif message.get('method') == 'turn/completed':
            turn = message['params']['turn']
            if message['params']['threadId'] != thread_id or turn['status'] != 'completed':
                raise RuntimeError('Codex turn failed: ' + json.dumps(turn.get('error')))
            emit({'type':'final', 'message':'Codex completed its turn; harness evaluates filesystem deliverables.'})
            return
        elif 'error' in message:
            raise RuntimeError('Codex RPC error: ' + json.dumps(message['error']))


def main():
    request = json.loads(sys.stdin.readline())
    binary = Path(os.environ.get('CODEX_BINARY', str(Path.home() / '.local/bin/codex'))).resolve()
    version = subprocess.run([str(binary), '--version'], capture_output=True, text=True, check=True).stdout.strip()
    if version != 'codex-cli ' + VERSION: raise RuntimeError('Untested Codex CLI version: ' + version)
    auth = Path(os.environ.get('CODEX_AUTH_FILE', str(Path.home() / '.codex/auth.json'))).resolve()
    with tempfile.TemporaryDirectory(prefix='weatherbench-codex-') as directory:
        root = Path(directory).resolve(); home = root / 'controller'; public = root / 'public'
        home.mkdir(mode=0o700); public.mkdir()
        shutil.copyfile(auth, home / 'auth.json'); (home / 'auth.json').chmod(0o600)
        (home / 'config.toml').write_text(configuration(home))
        env = {k:os.environ[k] for k in ('PATH','LANG','LC_ALL','SSL_CERT_FILE') if k in os.environ}
        env['CODEX_HOME'] = str(home)
        process = subprocess.Popen([str(binary),'app-server','--stdio','--strict-config'], cwd=public, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True)
        def read_rpc():
            line = process.stdout.readline()
            if not line: raise RuntimeError('Codex app-server closed unexpectedly')
            return json.loads(line)
        def send_rpc(row, record=True):
            if record: trace('client', row)
            process.stdin.write(json.dumps(row, allow_nan=False)+'\n'); process.stdin.flush()
        def rpc(i, method, params, record=True):
            send_rpc({'id':i,'method':method,'params':params}, record)
            while True:
                row = read_rpc()
                if row.get('id') == i:
                    if 'error' in row: raise RuntimeError('Codex '+method+' failed: '+json.dumps(row['error']))
                    if record: trace('server', row)
                    return row['result']
                if record: trace('server', row)
                if 'id' in row and 'method' in row: raise RuntimeError('Unexpected startup server request')
        try:
            rpc(1,'initialize',{'clientInfo':{'name':'weatherbench_codex','version':'1'},
                               'capabilities':{'experimentalApi':True}})
            send_rpc({'method':'initialized','params':{}})
            account = rpc(2,'account/read',{'refreshToken':False}, record=False)
            if (account.get('account') or {}).get('type') != 'chatgpt':
                raise RuntimeError('Existing ChatGPT login required; no API fallback')
            limits = rpc(3,'account/rateLimits/read',{}, record=False)
            rates = limits.get('rateLimitsByLimitId') or {'codex':limits.get('rateLimits')}
            if not rates: raise RuntimeError('Subscription limits unavailable')
            for rate in rates.values():
                if not isinstance(rate,dict): raise RuntimeError('Subscription limits unavailable')
                if rate.get('credits',{}):
                    if rate['credits'].get('hasCredits') or rate['credits'].get('unlimited'):
                        raise RuntimeError('Account has spendable credits; cannot guarantee subscription-only billing')
                for window in ('primary','secondary'):
                    if rate.get(window) and rate[window].get('usedPercent',100) >= 100:
                        raise RuntimeError('Subscription limit exhausted; no credits fallback')
            skills = rpc(4,'skills/list',{'cwds':[str(public)],'forceReload':True}, record=False)
            enabled = [skill['path'] for entry in skills['data'] for skill in entry['skills'] if skill.get('enabled')]
            if enabled:
                raise RuntimeError('Host skill discovery remains enabled: ' + json.dumps(enabled))
            result = rpc(5,'thread/start',thread_parameters(public, request)); validate_thread(result, public)
            tid = result['thread']['id']
            if sys.argv[1:] == ['--check']:
                print(json.dumps({'ready':True,'model':MODEL,'cli_version':VERSION,
                                  'authentication':'chatgpt','inference_started':False}), flush=True)
                return
            send_rpc({'id':6,'method':'turn/start','params':{'threadId':tid, 'environments':[],
                      'effort':'medium', 'serviceTier':'default',
                      'input':[{'type':'text','text':json.dumps(request,allow_nan=False)}]}})
            bridge(read_rpc, send_rpc, request, tid, lambda:json.loads(sys.stdin.readline()))
        finally:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == '__main__':
    main()
