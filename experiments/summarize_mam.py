"""Validate and summarize this bounded study; never launch inference."""
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template
from assessment.storage import digest, inventory
from experiments.evidence_contracts import contract_status

SYSTEMS = {"mam-luna-python", "mam-luna-required-accord", "mam-astra-python",
           "mam-luna-python-context-budget", "mam-luna-required-accord-context-budget"}


def read(path):
    return json.loads(path.read_text())


def summarize():
    template = Template("mam-multimodel-outlook")
    reviews_path = ROOT / "experiments/mam-tool-use-review-2026-10-08.json"
    reviews = read(reviews_path).get("runs", {}) if reviews_path.is_file() else {}
    recovery_path = ROOT / "experiments/mam-launch-recovery-2026-10-08.json"
    before_model = {row["run"] for row in read(recovery_path)["failed_launches"]} if recovery_path.is_file() else set()
    invocations = {}
    for path in (ROOT / "var/review/mam-attempts-20261008").glob("*/invocation.json"):
        invocation = read(path)
        if invocation.get("result"):
            invocations[invocation["result"]["run"]] = invocation
    rows, pending, seen = [], [], set()
    for folder in sorted((ROOT / "var/template-runs").glob("*mam-multimodel-outlook*")):
        meta = read(folder / "run.json")
        if meta["system"] not in SYSTEMS:
            continue
        key = (meta["system"], meta["instance"]["id"])
        if meta["id"] not in before_model and key in seen:
            raise ValueError("Additional attempt needs explicit study review: " + str(key))
        if meta["id"] not in before_model:
            seen.add(key)
        if meta["status"] in ("created", "running") or not (folder / "assessment.json").is_file():
            pending.append(meta["id"])
            continue
        assessment = read(folder / "assessment.json")
        if meta["fingerprint"] != assessment["fingerprint"]:
            raise ValueError("Scientific contract drift: " + meta["id"])
        version_status = contract_status(template, meta["fingerprint"])
        if digest(ROOT / "systems" / meta["system"] / "system.yaml") != meta["system_sha256"]:
            raise ValueError("System configuration drift: " + meta["id"])
        for directory, manifest in (("frozen", "artifacts.json"), ("inputs", "input-manifest.json"),
                                    ("system", "substrate-manifest.json")):
            if inventory(folder / directory) != read(folder / manifest):
                raise ValueError(directory + " changed: " + meta["id"])
        acquisition = assessment.get("acquisition", {})
        for probe in acquisition.get("probes", []):
            if not probe.get("evidence_persisted") or digest(Path(probe["log_path"])) != probe["log_sha256"]:
                raise ValueError("Replay acquisition evidence missing or changed: " + meta["id"])
        provenance = read(folder / "controller/provenance.json")
        trace = folder / "logs/events.jsonl"
        if trace.exists() and digest(trace) != provenance["trace"]["sha256"]:
            raise ValueError("Execution trace changed: " + meta["id"])
        events = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
        command_seconds = sum(event.get("seconds", 0) for event in events if event.get("type") == "tool_result")
        initial = provenance["sandbox"].get("acquisition") or {}
        if initial.get("state") == "recorded" and digest(Path(initial["log_path"])) != initial["log_sha256"]:
            raise ValueError("Initial acquisition log changed: " + meta["id"])
        imports = set()
        for source in (folder / "frozen").rglob("*.py"):
            try:
                tree = ast.parse(source.read_text())
            except (SyntaxError, UnicodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(item.name.split(".")[0] for item in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
        rows.append({
            "run": meta["id"], "system": meta["system"], "directory": str(folder.relative_to(ROOT)),
            "status": meta["status"], "fingerprint": assessment["fingerprint"],
            "contract_status": version_status,
            "model_attempt_evaluable": meta["id"] not in before_model,
            "scientific_performance_evaluable": all(assessment["checks"].get(name, {}).get("state") == "pass"
                                                     for name in ("envelope", "coverage")),
            "model_inference_started": False if meta["id"] in before_model else "attempted; see adapter trace and usage",
            "infrastructure_reason": meta.get("reason") if meta["id"] in before_model else None,
            "instance": meta["instance"]["id"], "system_sha256": meta["system_sha256"],
            "runtime_image": meta["runtime_image"], "completion": assessment["outcome"],
            "computed": assessment["computed_outcome"], "supplementary": assessment["advisory_outcome"],
            "skill": assessment.get("skill"), "seconds": meta.get("seconds"),
            "command_seconds": command_seconds,
            "model_and_adapter_overhead_seconds": max(0, (meta.get("seconds") or 0) - command_seconds),
            "invocation": invocations.get(meta["id"]),
            "tool_calls": meta.get("tool_calls"), "usage": meta.get("usage"),
            "usage_source": meta.get("usage_source"),
            "uncached_input_tokens": (max(0, meta["usage"].get("input_tokens", 0)
                                         - meta["usage"].get("cached_input_tokens", 0)) if meta.get("usage") else None),
            "failed_checks": [name for name, check in assessment["checks"].items() if check["state"] == "fail"],
            "unresolved_checks": [name for name, check in assessment["checks"].items() if check["state"] == "unresolved"],
            "initial_acquisition": initial,
            "replay_acquisition": acquisition, "sandbox": provenance["sandbox"],
            "static_imports": sorted(imports), "tool_use_review": reviews.get(meta["id"], {"status": "pending"}),
            "judge": assessment.get("judge") or {},
        })
    by_arm = {}
    for name, required in (("python", False), ("required_accord", True)):
        assigned = [row for row in rows if row["model_attempt_evaluable"] and ("required-accord" in row["system"]) == required]
        valid = sum(row["completion"] == "pass" for row in assigned)
        fresh = sum((row["uncached_input_tokens"] or 0) + (row["usage"] or {}).get("output_tokens", 0) for row in assigned)
        by_arm[name] = {"assigned_attempts": len(assigned), "valid_completions": valid,
                        "uncached_input_plus_output_tokens_including_failures": fresh,
                        "tokens_per_valid_completion_including_failures": fresh / valid if valid else None,
                        "invoice_cost_per_valid_completion": "unknown; subscription inference"}
    return {
        "schema_version": 1, "plan": "experiments/mam-acquisition-study.yaml",
        "completed_attempts": sum(row["model_attempt_evaluable"] for row in rows),
        "scientific_submissions": sum(row["scientific_performance_evaluable"] for row in rows),
        "infrastructure_launch_failures": sum(not row["model_attempt_evaluable"] for row in rows),
        "recorded_launches": len(rows), "pending_attempts": pending,
        "direct_api_key_calls": 0, "direct_paid_api_spend_usd": 0,
        "billing": "Subscription inference. Invoice cost unknown; no list-price estimate is treated as paid spend.",
        "token_totals": {key: sum((row["usage"] or {}).get(key, 0) for row in rows)
                         for key in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens")},
        "uncached_input_tokens": sum(row["uncached_input_tokens"] or 0 for row in rows),
        "unknown_usage_runs": [row["run"] for row in rows if row["model_attempt_evaluable"] and row["usage"] is None],
        "by_arm_including_both_budget_stages": by_arm,
        "interpretation": "One attempt per assigned condition; no stable ranking, causal tool benefit or frontier boundary established.",
        "rows": rows,
    }


if __name__ == "__main__":
    result = summarize()
    (ROOT / "experiments/mam-results-2026-10-08.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
