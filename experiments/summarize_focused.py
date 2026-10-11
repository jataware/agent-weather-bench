"""Collect completed focused-study evidence; never launches inference."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template
from assessment.storage import digest


def read(path):
    return json.loads(path.read_text())


def summarize():
    rows, pending, seen = [], [], set()
    reviewed = ROOT / "experiments/downscaling-reassessment-2026-10-08.json"
    reassessments = {r["run"]: r for r in read(reviewed)["rows"]} if reviewed.is_file() else {}
    for folder in sorted((ROOT / "var/template-runs").glob("*focused-*")):
        meta = read(folder / "run.json")
        key = (meta["template"], meta["instance"]["id"], meta["system"])
        if key in seen:
            raise ValueError(f"Duplicate attempt: {key}; review repeats explicitly")
        seen.add(key)
        if meta["status"] in ("created", "running") or not (folder / "assessment.json").is_file():
            pending.append(meta["id"])
            continue
        original = assessment = read(folder / "assessment.json")
        reassessment = reassessments.get(meta["id"])
        if meta["fingerprint"] != original["fingerprint"]:
            raise ValueError("Original assessment drift: " + meta["id"])
        if reassessment:
            path = ROOT / reassessment["assessment_file"]
            if digest(path) != reassessment["assessment_sha256"] or reassessment["original_fingerprint"] != meta["fingerprint"]:
                raise ValueError("Reviewed reassessment changed: " + meta["id"])
            if not all(reassessment[k] for k in ("brief_identical", "inputs_byte_identical", "envelope_identical", "frozen_artifacts_unchanged")):
                raise ValueError("Reassessment changes the agent's job: " + meta["id"])
            assessment = read(path)
        from experiments.evidence_contracts import contract_status
        historical_status = contract_status(Template(meta['template']), assessment['fingerprint'])
        if digest(ROOT / "systems" / meta["system"] / "system.yaml") != meta["system_sha256"]:
            raise ValueError("System definition changed after launch: " + meta["id"])
        checks = assessment["checks"]
        provenance = read(folder / "controller/provenance.json")
        judge = assessment.get("judge") or {}
        rows.append({"run": meta["id"], "directory": str(folder.relative_to(ROOT)),
                     "template": meta["template"], "instance": meta["instance"]["id"], "system": meta["system"],
                     "submission_spec_version": meta["spec_version"], "submission_fingerprint": meta["fingerprint"],
                     "assessment_spec_version": assessment["spec_version"], "assessment_fingerprint": assessment["fingerprint"],
                     "contract_status": historical_status,
                     "reassessment": reassessment,
                     "original_completion": original["outcome"], "original_computed": original["computed_outcome"],
                     "system_sha256": meta["system_sha256"], "runtime_image": meta["runtime_image"],
                     "status": meta["status"], "completion": assessment["outcome"],
                     "computed": assessment["computed_outcome"], "supplementary": assessment["advisory_outcome"],
                     "ranking_gate": assessment["ranking_outcome"], "skill": assessment.get("skill"),
                     "skill_valid_for_ranking": assessment.get("skill_valid_for_ranking"),
                     "seconds": meta["seconds"], "tool_calls": meta["tool_calls"], "usage": meta["usage"],
                     "failed_checks": [n for n, r in checks.items() if r["state"] == "fail"],
                     "unresolved_checks": [n for n, r in checks.items() if r["state"] == "unresolved"],
                     "check_counts": {s: sum(r["state"] == s for r in checks.values()) for s in ("pass", "fail", "unresolved")},
                     "substrate_use": provenance["substrate_use"], "sandbox": provenance["sandbox"],
                     "judge": judge})
    return {"schema_version": 1, "plan": "experiments/focused-study.yaml", "completed_attempts": len(rows),
            "pending_attempts": pending, "direct_api_key_calls": 0,
            "billing": "Subscription-authenticated inference; list-price estimates are not invoices.",
            "agent_token_totals": {key: sum((r["usage"] or {}).get(key, 0) for r in rows)
                                   for key in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens")},
            "judge_list_price_usd": sum(u.get("list_price_usd", 0) or 0 for r in rows for u in r["judge"].get("usage", [])),
            "rows": rows}


if __name__ == "__main__":
    result = summarize()
    (ROOT / "experiments/focused-results-2026-10-08.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
