"""Summarize the bounded checkpoint; never launches or retries a model.

Run from the repository: .venv/bin/python experiments/summarize_checkpoint.py
"""
import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template


def read(path):
    return json.loads(path.read_text())


def summarize():
    plan = yaml.safe_load((ROOT / "experiments/grading-checkpoint.yaml").read_text())
    expected = {(t["template"], t["instance"], s) for t in plan["tasks"] for s in plan["systems"]}
    selected, interrupted = {}, []
    for folder in sorted((ROOT / "var/template-runs").glob("*")):
        if not (folder / "run.json").is_file():
            continue
        meta = read(folder / "run.json")
        key = (meta["template"], meta["instance"]["id"], meta["system"])
        if key not in expected:
            continue
        if meta["status"] == "interrupted":
            interrupted.append(meta["id"])
            continue
        if key in selected:
            raise ValueError(f"Multiple non-interrupted attempts for {key}; review explicitly")
        selected[key] = folder
    if set(selected) != expected:
        raise ValueError("Checkpoint incomplete; missing " + str(expected - set(selected)))
    rows = []
    for key in sorted(expected):
        folder = selected[key]
        meta, assessment = read(folder / "run.json"), read(folder / "assessment.json")
        if assessment["fingerprint"] != meta["fingerprint"]:
            raise ValueError(f"Contract changed for {meta['id']}; review before pooling")
        from experiments.evidence_contracts import contract_status
        historical_status = contract_status(Template(key[0]), assessment['fingerprint'])
        use = read(folder / "controller/provenance.json")["substrate_use"]
        trace = [json.loads(line) for line in (folder / "logs/events.jsonl").read_text().splitlines()]
        catalog = [r["event"]["command"] for r in trace if r.get("event", {}).get("type") == "execute" and "/catalog" in r["event"]["command"]]
        checks = assessment["checks"]
        rows.append({"template": key[0], "instance": key[1], "system": key[2], "run": meta["id"],
                     "directory": str(folder.relative_to(ROOT)), "spec_version": meta["spec_version"], "fingerprint": meta["fingerprint"],
                     "contract_status": historical_status,
                     "system_sha256": meta["system_sha256"], "runtime_image": meta["runtime_image"],
                     "status": meta["status"], "completion": assessment["outcome"], "computed": assessment["computed_outcome"],
                     "supplementary": assessment["advisory_outcome"], "ranking_gate": assessment["ranking_outcome"],
                     "skill_valid_for_ranking": assessment.get("skill_valid_for_ranking"), "skill": assessment.get("skill"),
                     "failed_checks": [n for n, r in checks.items() if r["state"] == "fail"],
                     "unresolved_checks": [n for n, r in checks.items() if r["state"] == "unresolved"],
                     "check_counts": {state: sum(r["state"] == state for r in checks.values()) for state in ("pass", "fail", "unresolved")},
                     "agent_seconds": meta["seconds"], "tool_calls": meta["tool_calls"], "usage": meta["usage"],
                     "catalog_commands": catalog, "library_use": use["libraries"], "judge": assessment.get("judge") or {"usage": [], "not_run": True},
                     "sandbox": read(folder / "controller/provenance.json")["sandbox"]})
    return {"schema_version": 1, "plan": "experiments/grading-checkpoint.yaml", "completed_attempts": len(rows),
            "interrupted_attempts_excluded": interrupted, "direct_api_key_calls": 0,
            "billing": "Agents use ChatGPT subscription; judges use Claude Max subscription. Dollar usage fields are provider list-price estimates, not API invoices.",
            "agent_token_totals": {key: sum(r["usage"].get(key, 0) for r in rows) for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")},
            "judge_list_price_usd": sum(u.get("list_price_usd", 0) or 0 for r in rows for u in r["judge"]["usage"]),
            "rows": rows}


if __name__ == "__main__":
    result = summarize()
    destination = ROOT / "experiments/checkpoint-results-2026-10-08.json"
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
