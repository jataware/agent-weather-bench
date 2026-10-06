"""Deterministic controller fixture for the weeks 3-4 rainfall template, Level 2.

No model calls. It scores three fixed methods with the development-feedback tool,
keeps the best, and states that score as its claim. This exercises the feedback
ledger and the Level 2 checks. Excluded from every capability claim.
"""
import json
import sys

request = json.loads(sys.stdin.readline())
counter = 0


def call(event):
    global counter
    counter += 1
    print(json.dumps({**event, "id": f"fixture-{counter}"}), flush=True)
    return json.loads(sys.stdin.readline())


def execute(command):
    return call({"type": "execute", "command": command})


execute("cp /substrate/solve.py /work/submission/solve.py")
scores = {}
for method in ("bias", "climatology", "raw"):
    execute(f"cd /work/submission && printf '{{\"method\": \"{method}\"}}' > variant.json && python solve.py --inputs /work/inputs --output /work/submission "
            f"&& cp answer.json candidate-{method}.json")
    reply = call({"type": "score_development", "prediction_file": f"candidate-{method}.json"})
    if reply["exit_code"] == 0:
        scores[method] = json.loads(reply["stdout"])["rmse_mm"]
best = min(scores, key=scores.get)
variant = json.dumps({"method": best, "claims": {"development_rmse_mm": scores[best]}})
execute(f"cd /work/submission && printf '%s' '{variant}' > variant.json && python solve.py --inputs /work/inputs --output /work/submission "
        f"&& printf 'Fixture forecast. Development scores: {json.dumps(scores)}. No model was involved.\\n' > report.md")
print(json.dumps({"type": "usage", "usage": {"input_tokens": 0, "output_tokens": 0, "usd": 0, "calls": 0}}), flush=True)
print(json.dumps({"type": "final", "message": f"Fixture kept {best}; development scores {scores}"}), flush=True)
