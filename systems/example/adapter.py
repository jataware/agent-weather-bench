"""Replace this trusted controller adapter with your model/agent library.

One JSON request arrives on stdin. Emit execute events and read tool results.
Only the harness executes scientific commands, inside the isolated container.
Never let model-generated commands execute on this controller host.
"""
import json
import sys

request = json.loads(sys.stdin.readline())
print(json.dumps({"type":"execute","id":"inspect","command":"ls -la /work/inputs /substrate /task"}),flush=True)
result = json.loads(sys.stdin.readline())
# Feed request + tool result into your system, emit further execute events,
# and finish only when its deliverables are in /work/submission.
print(json.dumps({"type":"final","message":"Template adapter only; no scientific submission generated."}),flush=True)
