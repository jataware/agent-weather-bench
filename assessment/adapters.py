"""A small JSON-lines interface for any trusted agent controller.

Moved from the first evaluator (archive/evaluator-v1-2026-10/weatherbench/adapters.py) without the
`acquire` tool, which only the archived task packages advertised.
"""
import json
import math
import os
import selectors
import signal
import subprocess
import sys
import time


def events(path, row):
    with path.open("a") as stream:
        stream.write(json.dumps(row, allow_nan=False) + "\n")


def command_driver(config, substrate, request, box, log, stderr_path):
    argv = [arg.replace("{python}",sys.executable).replace("{driver}",str(substrate)) for arg in config["driver"]["argv"]]
    env = {key:os.environ[key] for key in ("PATH","LANG","LC_ALL","SSL_CERT_FILE") if key in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for key in config["driver"].get("env",[]):
        if key not in os.environ:
            raise ValueError(f"Missing controller environment variable: {key}")
        env[key] = os.environ[key]
    usage, count, status, started = None, 0, "incomplete", time.monotonic()
    budget = config["budget"]
    with stderr_path.open("w") as stderr:
        process = subprocess.Popen(argv,cwd=substrate,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,start_new_session=True)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout,selectors.EVENT_READ)
        buffer = b""
        def send(value):
            process.stdin.write((json.dumps(value)+"\n").encode()); process.stdin.flush()
        try:
            send(request)
            for _ in range(budget["max_tool_calls"] * 4 + 10):
                remaining = budget["max_seconds"]-(time.monotonic()-started)
                if remaining <= 0: status="time_limit"; break
                while b"\n" not in buffer:
                    if not selector.select(max(0,remaining)):
                        status="time_limit"; break
                    chunk = os.read(process.stdout.fileno(),65536)
                    if not chunk: break
                    buffer += chunk
                    if len(buffer)>1048576: raise ValueError("Adapter event exceeds 1 MB")
                    remaining = budget["max_seconds"]-(time.monotonic()-started)
                    if remaining<=0: break
                if b"\n" not in buffer: break
                line,buffer = buffer.split(b"\n",1)
                event = json.loads(line)
                if not isinstance(event,dict): raise ValueError("Adapter events must be JSON objects")
                events(log,{"type":"adapter", "event":event})
                if event.get("type")=="final": status="submitted"; break
                if event.get("type")=="usage":
                    usage = event.get("usage")
                    if not isinstance(usage,dict) or not all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in usage.values()):
                        raise ValueError("Usage counters must be finite nonnegative numbers")
                    continue
                action = event.get("type")
                if action == "execute":
                    if not isinstance(event.get("command"),str) or not event["command"].strip():
                        raise ValueError("Expected a nonempty execute command")
                elif action == 'score_development' and any(tool['name'] == 'score_development' for tool in request.get('tools', [])):
                    if not isinstance(event.get('prediction_file'), str) or not event['prediction_file'].strip():
                        raise ValueError('Invalid development feedback request')
                else:
                    raise ValueError("Expected an advertised tool, usage or final event")
                if count>=budget["max_tool_calls"]: status="tool_limit"; break
                requested = event.get("timeout_seconds",budget["command_seconds"])
                if type(requested) not in (int,float) or not math.isfinite(requested) or requested<=0:
                    raise ValueError("Invalid requested tool timeout")
                timeout = min(requested,budget["command_seconds"],max(.1,remaining))
                if action == 'execute':
                    result = box.execute(event['command'], timeout)
                else:
                    result = box.score_development(event['prediction_file'], timeout)
                count += 1
                response = {"type":"tool_result","id":event.get("id"),**result,"remaining_seconds":max(0,budget["max_seconds"]-(time.monotonic()-started))}
                events(log,response); send(response)
                if result["exit_code"]==124: status="tool_timeout"; break
            else: status="event_limit"
        finally:
            selector.close()
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM)
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGKILL); process.wait()
            process.stdin.close(); process.stdout.close()
    return {"status":status,"tool_calls":count,"usage":usage,"usage_source":"adapter_reported" if usage else "unknown","seconds":time.monotonic()-started}


def anthropic_driver(config, request, box, log, stderr_path=None):
    from .model import Model, BudgetExceeded
    cfg = {**config["driver"],"max_seconds":config["budget"]["max_seconds"]}
    model = Model(cfg)
    system = "You are carrying out a weather research task. Use execute for scientific commands in the isolated /work runtime. Read the task and contracts. Write deliverables under /work/submission and retained material under /work/state. No other host tools are available."
    tools = [{"name":"execute","description":"Run a command in the isolated scientific runtime.","input_schema":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}]
    for tool in request.get("tools", []):
        if tool["name"] == 'score_development':
            tools.append({"name":tool['name'],"description":tool["description"],"input_schema":tool["inputSchema"]})
    messages = [{"role":"user","content":json.dumps(request)}]
    status,count,started = "turn_limit",0,time.monotonic()
    try:
        for _ in range(cfg["max_turns"]):
            response = model.call(system,messages,tools)
            events(log,{"type":"model","response":response})
            messages.append({"role":"assistant","content":response["content"]})
            calls = [block for block in response["content"] if block["type"]=="tool_use"]
            if not calls:
                if response["stop_reason"]=="end_turn": status="submitted"; break
                messages.append({"role":"user","content":"Continue using short complete tool calls."}); continue
            answers = []
            for call in calls:
                remaining = cfg["max_seconds"]-(time.monotonic()-started)
                if remaining<=0 or count>=config["budget"]["max_tool_calls"]: raise BudgetExceeded("Tool/time limit")
                args = call.get("input", {})
                command = args.get("command") if isinstance(args,dict) else None
                feedback = call['name'] == 'score_development' and any(tool['name'] == 'score_development' for tool in tools)
                valid_feedback = (feedback and isinstance(args, dict) and set(args) == {'prediction_file'}
                                  and isinstance(args['prediction_file'], str) and bool(args['prediction_file'].strip()))
                if response["stop_reason"]=="max_tokens" or not ((call["name"]=="execute" and isinstance(command,str)) or valid_feedback):
                    result = {"exit_code":1,"stderr":"Incomplete or invalid tool call; nothing executed."}
                else:
                    timeout = min(remaining,config["budget"]["command_seconds"])
                    fields = ('prediction_file',) if feedback else ('command',)
                    events(log, {'type': 'adapter', 'event': {'type': call['name'],
                                **{key: args[key] for key in fields if key in args}}})
                    if feedback:
                        result = box.score_development(args['prediction_file'], timeout)
                    else:
                        result = box.execute(command, timeout)
                    count += 1
                events(log,{"type":"tool_result","id":call["id"],"command":command,**result})
                answers.append({"type":"tool_result","tool_use_id":call["id"],"content":json.dumps(result),"is_error":result["exit_code"]!=0})
            messages.append({"role":"user","content":answers})
    except (BudgetExceeded,RuntimeError) as error:
        status="stopped"; events(log,{"type":"stop","reason":str(error)})
    finally: model.close()
    return {"status":status,"tool_calls":count,"usage":model.usage,"usage_source":"controller_provider_usage_with_pinned_accounting","seconds":time.monotonic()-started}
