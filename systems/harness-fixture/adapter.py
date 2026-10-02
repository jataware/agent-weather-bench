"""Deterministic controller fixture; no LLM calls, excluded from benchmark comparisons."""
import json
import sys

request = json.loads(sys.stdin.readline())
print(json.dumps({"type":"execute","id":"fixture","command":"python /substrate/workflow.py --inputs /work/inputs --output /work/submission"}),flush=True)
result = json.loads(sys.stdin.readline())
print(json.dumps({"type":"usage","usage":{"input_tokens":0,"output_tokens":0,"usd":0,"calls":0}}),flush=True)
print(json.dumps({"type":"final","message":"Harness fixture finished; exit code " + str(result['exit_code'])}),flush=True)
