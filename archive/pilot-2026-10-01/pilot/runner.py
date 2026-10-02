"""One attempt; the follow-up inherits files, never another arm or a conversation."""
import json
import os
from pathlib import Path
import shutil
import time

import httpx
import xarray as xr

from .common import ROOT, read, write, task, brief, inventory, digest
from .runtime import Sandbox, carry_forward, docker, image_id
from .model import Model, BudgetExceeded
from .checks import compare, evaluate

TOOLS = [{'name':'execute', 'description':'Execute a shell command inside your isolated /work workspace.',
          'input_schema':{'type':'object','properties':{'command':{'type':'string'}},'required':['command'],'additionalProperties':False}}]
SYSTEM = '''You are performing a scientific weather task. Use execute to inspect your
environment, retrieve permitted data, write code and produce the required artifacts.
Only /work persists to the follow-up. Use installed dependencies; run skill scripts with
python rather than resolving inline uv dependencies. Do not use another arm's excluded
toolkits or benchmark solutions. Do not send messages or publish to external services.
The gateway manages data credentials; no real secret is needed in your code.
Report failures and negative scientific results honestly. Your report does not determine
your score: outputs are independently checked and code is rerun. Keep raw data, reusable
code, fitted state and handoff notes under /work. No symlinks or special files in the final
workspace. Use the required filenames. End your response when the artifacts are ready.
Build a minimal complete working submission first, then improve it if budget remains.
Write code in small executable chunks: at most about 80 lines or 6000 characters
per command. Append to longer files in successive calls. Do not print whole datasets
or long documentation files; inspect targeted sections. Keep final chat concise.
solve.py --output must recreate answer.json as well as numerical outputs and figures.
Cache downloads and intermediate data under /work; reuse them when valid and record
cache hits/misses and avoided downloads. Never claim supplied data was downloaded.
'''


def tool_command(call, stop_reason):
    """Never execute a partially generated tool call; give actionable recovery."""
    if stop_reason == 'max_tokens':
        return None, 'Response hit the output-token limit. This command was NOT executed. Split the write into chunks of at most 80 lines / 6000 characters; append successive chunks. Do not resend the whole file.'
    command = call.get('input', {}).get('command')
    if call.get('name') != 'execute' or not isinstance(command,str):
        return None, 'Only execute(command: string) is available.'
    return command, None


def replay_answer_matches(actual, original, name):
    if name == 'seasonal':
        # Compare the task's declared answer fields, not optional session notes.
        keys = ('method','development_validation','limitations','source_url')
        if not all(k in actual and k in original for k in keys): return False
        return compare({k:actual[k] for k in keys},{k:original[k] for k in keys})
    return compare(actual, original)


def offline(arm, frozen, out, command, inputs=None, runtime=None):
    runtime = runtime or read(ROOT/'experiment.yaml')['runtime']
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    args = ['run','--rm','--network','none','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','128','--memory',runtime['memory'],
            '--cpus',str(runtime['cpus']),'--user',f'{os.getuid()}:{os.getgid()}',
            '--tmpfs','/tmp:rw,nosuid,size=512m','--mount',f'type=bind,src={Path(frozen).resolve()},dst=/work,readonly',
            '--mount',f'type=bind,src={out},dst=/output','--workdir','/work']
    if inputs:
        args += ['--mount',f'type=bind,src={Path(inputs).resolve()},dst=/inputs/forecast.nc,readonly']
    # Name it so a timeout can kill the workload, not merely the docker client.
    import uuid, subprocess
    name = 'accord-replay-'+uuid.uuid4().hex[:12]
    try:
        p = docker(*args, '--name', name, runtime['images'][arm], *command,
                   timeout=runtime['command_timeout_seconds'], check=False)
        return {'exit_code':p.returncode, 'stdout':p.stdout[-16000:], 'stderr':p.stderr[-8000:]}
    except subprocess.TimeoutExpired:
        return {'exit_code':124, 'stdout':'', 'stderr':'Replay deadline exceeded'}
    finally:
        docker('rm','-f',name,check=False)


def replay(run):
    run = Path(run)
    meta = read(run/'run.json')
    result = offline(meta['arm'],run/'frozen',run/'replay', ['python','solve.py','--output','/output'])
    result['passed'] = False
    try:
        inventory(run/'replay')
        result['passed'] = result['exit_code']==0 and replay_answer_matches(read(run/'replay/answer.json'),read(run/'frozen/answer.json'),meta['task'])
        if meta['task']=='seasonal':
            for file in ['training.nc','development.nc']:
                xr.testing.assert_allclose(xr.load_dataset(run/'replay'/file),xr.load_dataset(run/'frozen'/file))
    except (OSError, ValueError, AssertionError):
        result['passed'] = False
    result['detail'] = 'Offline replay compared to original output; judge also inspects code for substantive recomputation.'
    write(run/'replay.json',result)
    return result


def run_attempt(name, arm, phase, mode, directory, reference, policy, parent=None,
                config_path=None, spec_path=None, initial_inputs=None):
    if read(ROOT/'launch-review.yaml')['status'] != 'ready':
        raise ValueError('Benchmark attempts paused at user request; review the plan before changing launch status.')
    config_path = Path(config_path or ROOT/'experiment.yaml')
    spec_path = Path(spec_path or ROOT/'tasks'/f'{name}.yaml')
    config = read(config_path)
    if read(ROOT/'launch-review.yaml').get('allowed_scope') == 'smoke_only' and config.get('study_type') != 'development_smoke':
        raise ValueError('Only the authorized development smoke is enabled')
    spec, ref = read(spec_path), Path(reference).resolve()
    reference_info = read(ref/'reference.json')
    if reference_info.get('reviewed') is not True or reference_info.get('task_sha256') != digest(spec_path):
        raise ValueError('Need a reviewed reference matching the task version')
    if reference_info.get('phase') != phase or reference_info.get('task') != name:
        raise ValueError('Wrong reference phase/task')
    policy = read(policy)
    if policy.get('mode') != mode or policy.get('reviewed') is not True:
        raise ValueError('Need a reviewed network policy matching the mode')
    if not read(ROOT/'results/sandbox-preflight.json').get('passed'):
        raise ValueError('Sandbox preflight has not passed')
    image_ids = read(ROOT/'sandbox/images.lock.json')
    if image_id('accord-pilot-gateway:v1') != image_ids['gateway'] or read(ROOT/'results/sandbox-preflight.json').get('gateway_image_id') != image_ids['gateway']:
        raise ValueError('Gateway changed after preflight')
    for a, image in config['runtime']['images'].items():
        if image_id(image) != image_ids[a]:
            raise ValueError('Runtime image changed after lock')
        if read(ROOT/'results/sandbox-preflight.json')['arms'][a]['image_id'] != image_ids[a]:
            raise ValueError('Runtime image changed after preflight')
    run = Path(directory).resolve()
    run.mkdir(parents=True, exist_ok=False)
    work = run/'work'
    inherited = {}
    if phase=='followup':
        if parent is None: raise ValueError('Follow-up needs same-arm initial attempt')
        parent = Path(parent).resolve()
        pm = read(parent/'run.json')
        if any(pm[k] != v for k,v in [('task',name),('arm',arm),('mode',mode),('phase','initial'),('model',config['agent']['model'])]):
            raise ValueError('Follow-up parent differs in task, arm, mode or model')
        if pm['task_sha256'] != digest(spec_path) or pm['config_sha256'] != digest(config_path) or pm['image_id'] != image_ids[arm]:
            raise ValueError('Protocol/environment changed between initial and follow-up')
        if inventory(parent/'frozen') != read(parent/'artifacts.json'):
            raise ValueError('Initial frozen artifacts changed')
        inherited = carry_forward(parent/'frozen',work)
    else:
        work.mkdir()
        if initial_inputs:
            for p in Path(initial_inputs).iterdir():
                if not p.is_file() or p.is_symlink(): raise ValueError('Inputs must be plain files')
                (work/'inputs').mkdir(exist_ok=True)
                shutil.copy2(p,work/'inputs'/p.name)
    arms = {'scratch':'Generic Python only; Rhiza and ACCORD toolkits are excluded.',
            'rhiza':'Rhiza skills and scripts are under /catalog; generic Python is also allowed.',
            'accord':'africas2s, acmaddl and rosetta are installed; start at /opt/accord-docs. Generic Python is also allowed.'}
    prompt = brief(spec,phase)+'\n\n'+arms[arm]
    prompt += '\n\n'+config.get('arm_guidance',{}).get(arm,'')
    (run/'prompt.txt').write_text(prompt)
    (run/'system.txt').write_text(SYSTEM)
    write(run/'task.json',spec)
    write(run/'config.json',config)
    write(run/'policy.json',policy)
    metadata = dict(task=name,arm=arm,phase=phase,mode=mode,model=config['agent']['model'],
                    parent=str(parent) if parent else None, task_sha256=digest(spec_path),
                    config_sha256=digest(config_path), image_id=image_ids[arm], study_type=config.get('study_type','pilot'),
                    reference_sha256=digest(ref/'reference.json'), status='started', integrity='unreviewed')
    write(run/'run.json',metadata)
    messages = [{'role':'user','content':prompt}]
    model = Model(config['agent'])
    started = time.monotonic()
    try:
        with Sandbox(arm,work,policy=policy,credential=Path.home()/'.cdsapirc',runtime=config['runtime']) as box:
            metadata['gateway_log'] = str(box.state/'network.jsonl')
            for _ in range(config['agent']['max_turns']):
                response = model.call(SYSTEM,messages,TOOLS)
                with (run/'events.jsonl').open('a') as log: log.write(json.dumps({'type':'model','response':response})+'\n')
                messages.append({'role':'assistant','content':response['content']})
                calls = [b for b in response['content'] if b['type']=='tool_use']
                if not calls:
                    if response['stop_reason'] in ('max_tokens','pause_turn'):
                        messages.append({'role':'user','content':'Continue with short tool calls. If the response was truncated, split each file write into at most 80 lines / 6000 characters and append successive chunks.'})
                        continue
                    metadata['status'] = 'submitted' if response['stop_reason']=='end_turn' else 'incomplete_response'
                    break
                outputs = []
                for call in calls:
                    remaining = config['agent']['max_seconds']-(time.monotonic()-started)
                    if remaining <= 0: raise BudgetExceeded('Wall-time budget exhausted')
                    command, error = tool_command(call,response['stop_reason'])
                    if error:
                        result = {'exit_code':1,'stderr':error}
                    else:
                        result = box.execute(command,timeout=min(remaining,config['runtime']['command_timeout_seconds']))
                    result['remaining_seconds'] = max(0,round(config['agent']['max_seconds']-(time.monotonic()-started)))
                    result['remaining_usd'] = round(max(0,config['agent']['max_usd']-model.usage['usd']),3)
                    with (run/'events.jsonl').open('a') as log: log.write(json.dumps({'type':'tool','id':call['id'],'command':call['input'].get('command'),'result':result})+'\n')
                    outputs.append({'type':'tool_result','tool_use_id':call['id'],'content':json.dumps(result),'is_error':result['exit_code']!=0})
                messages.append({'role':'user','content':outputs})
            else: metadata['status']='turn_budget_exhausted'
            metadata['gateway_log'] = str(box.state/'network.jsonl')
    except (BudgetExceeded, RuntimeError, httpx.TimeoutException) as exc:
        metadata.update(status='stopped',reason=str(exc)[:500])
        if isinstance(exc,httpx.TimeoutException): metadata['usage_incomplete']=True
    finally:
        metadata.update(usage=model.usage,seconds=time.monotonic()-started)
        model.close()
        write(run/'run.json',metadata)
    final = inventory(work)
    carry_forward(work,run/'frozen')
    write(run/'artifacts.json',final)
    write(run/'reuse.json',dict(inherited_files=len(inherited),unchanged=sum(final.get(k)==v for k,v in inherited.items()),
                                modified=[k for k,v in inherited.items() if k in final and final[k]!=v],
                                added=[k for k in final if k not in inherited],
                                note='Descriptive reuse evidence; no fresh follow-up control.'))
    reproduction = replay(run)
    predictions = None
    if name=='seasonal':
        inference = offline(arm,run/'frozen',run/'evaluation',
                            ['python','predict.py','--forecast','/inputs/forecast.nc','--output','/output/predictions.nc'],
                            inputs=ref/'forecast.nc')
        write(run/'inference.json',inference)
        inventory(run/'evaluation')
        predictions = run/'evaluation/predictions.nc'
    write(run/'checks.json',evaluate(name,run/'frozen',ref,reproduction,predictions))
    return run
