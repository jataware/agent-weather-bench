"""Deterministic controller fixture for the seasonal rainfall calibration template.

No model calls. It runs the controller's own control solution inside the sandbox
to exercise the runner and the process checks. Excluded from every capability claim.
"""
import json
import sys

request = json.loads(sys.stdin.readline())
steps = ["cp /substrate/solve.py /work/submission/solve.py && cd /work/submission && python solve.py --inputs /work/inputs --output /work/submission",
         "printf 'Fixture forecast produced by the controller. No model was involved.\\n' > /work/submission/report.md"]
codes = []
for number, command in enumerate(steps):
    print(json.dumps({"type": "execute", "id": f"fixture-{number}", "command": command}), flush=True)
    codes.append(json.loads(sys.stdin.readline())["exit_code"])
print(json.dumps({"type": "usage", "usage": {"input_tokens": 0, "output_tokens": 0, "usd": 0, "calls": 0}}), flush=True)
print(json.dumps({"type": "final", "message": "Fixture finished; exit codes " + str(codes)}), flush=True)
