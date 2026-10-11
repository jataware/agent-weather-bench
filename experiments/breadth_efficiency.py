"""Bounded matched-pair launcher and immutable-evidence summary for tooling breadth."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assessment.spec import Template
from assessment.storage import inventory

PLAN = ROOT / "experiments/tooling-breadth-plan-2026-10-08.json"
REVIEW = ROOT / "var/review/tooling-breadth-20261008"


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def validate(plan, pair):
    assert plan["status"] == "ready", "Preflight must finish before inference"
    assert len(plan["systems"]) == plan["max_new_agent_attempts"] == 6
    task = Template(pair["template"])
    assert task.fingerprint() == pair["fingerprint"], "Scientific contract drift"
    assert task.brief(task.instance(pair["instance"])).strip()
    certificate = read(task.folder / "certification.json")
    assert certificate["fingerprint"] == task.fingerprint() and certificate["automatic_tests_passed"]
    for proof in pair["preflight_evidence"]:
        assert digest(ROOT / proof["path"]) == proof["sha256"], proof["path"]
    for system in pair["systems"]:
        assigned = plan["systems"][system]
        for name, expected in assigned["files"].items():
            assert digest(ROOT / "systems" / system / name) == expected, (system, name)
    binary = Path(plan["codex_binary"])
    assert digest(binary) == plan["codex_binary_sha256"]
    assert subprocess.check_output([str(binary), "--version"], text=True).strip() == plan["codex_version"]


def launch_cell(plan, pair_id, system):
    pair, assigned = plan["pairs"][pair_id], plan["systems"][system]
    folder = REVIEW / system
    folder.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, "-m", "assessment", "run", pair["template"], pair["instance"], "--system", system]
    if not pair["run_required_judge"]:
        command.append("--no-judge")
    record = {"system": system, "pair": pair_id, "arm": assigned["arm"],
              "plan_sha256": digest(PLAN), "fingerprint": pair["fingerprint"],
              "started_at": datetime.now(timezone.utc).isoformat(), "status": "running",
              "command": command, "agent_retries": 0, "direct_paid_api_usd": 0}
    write(folder / "invocation.json", record)
    started = time.monotonic()
    with (folder / "stdout.json").open("w") as out, (folder / "stderr.log").open("w") as err:
        done = subprocess.run(command, cwd=ROOT, stdout=out, stderr=err,
                              env={**os.environ, "CODEX_BINARY": plan["codex_binary"],
                                   "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                                   "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"})
    record.update(status="finished", exit_code=done.returncode,
                  finished_at=datetime.now(timezone.utc).isoformat(),
                  cli_wall_seconds=time.monotonic() - started)
    if done.returncode == 0:
        record["result"] = read(folder / "stdout.json")
    write(folder / "invocation.json", record)
    return record


def run_pair(pair_id):
    plan = read(PLAN)
    pair = plan["pairs"][pair_id]
    validate(plan, pair)
    assert not any((REVIEW / s).exists() for s in pair["systems"]), "Never retry an assigned cell"
    invocations = list(REVIEW.glob("*/invocation.json")) if REVIEW.exists() else []
    assert not any(read(p)["status"] == "running" for p in invocations), "Only one scientific pair at a time"
    assert len(invocations) + 2 <= plan["max_new_agent_attempts"]
    # Threads only orchestrate fresh controller subprocesses. Native I/O stays serial.
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda s: launch_cell(plan, pair_id, s), pair["systems"]))
    print(json.dumps(rows, indent=2))
    return int(any(row["exit_code"] != 0 for row in rows))


def summarize():
    plan, rows, pending = read(PLAN), [], []
    invocations = {p.parent.name: read(p) for p in REVIEW.glob("*/invocation.json")} if REVIEW.exists() else {}
    for folder in sorted((ROOT / "var/template-runs").glob("*")):
        if not (folder / "run.json").exists():
            continue
        meta = read(folder / "run.json")
        if meta["system"] not in plan["systems"]:
            continue
        assigned = plan["systems"][meta["system"]]
        pair = plan["pairs"][assigned["pair"]]
        if not (folder / "assessment.json").exists():
            pending.append(meta["id"])
            continue
        assessment = read(folder / "assessment.json")
        assert meta["fingerprint"] == assessment["fingerprint"] == pair["fingerprint"]
        assert meta["system_sha256"] == assigned["files"]["system.yaml"]
        for child, manifest in [("frozen", "artifacts.json"), ("inputs", "input-manifest.json"), ("system", "substrate-manifest.json")]:
            assert inventory(folder / child) == read(folder / manifest), (meta["id"], child)
        events_path = folder / "logs/events.jsonl"
        events = [json.loads(line) for line in events_path.read_text().splitlines()] if events_path.exists() else []
        provenance = read(folder / "controller/provenance.json")
        assert digest(events_path) == provenance["trace"]["sha256"]
        command_seconds = sum(e.get("seconds", 0) for e in events if e.get("type") == "tool_result")
        usage = meta.get("usage")
        fresh = usage["input_tokens"] - usage.get("cached_input_tokens", 0) if usage else None
        rows.append({"run": meta["id"], "system": meta["system"], "pair": assigned["pair"], "arm": assigned["arm"],
                     "status": meta["status"], "computed": assessment["computed_outcome"],
                     "completion": assessment["outcome"], "advisory": assessment.get("advisory_outcome"),
                     "checks": {k: v["state"] for k, v in assessment["checks"].items()},
                     "usage": usage, "uncached_input_tokens": fresh,
                     "fresh_input_plus_output_tokens": fresh + usage["output_tokens"] if usage else None,
                     "agent_seconds": meta.get("seconds"), "command_seconds": command_seconds,
                     "cli_seconds": invocations.get(meta["system"], {}).get("cli_wall_seconds"),
                     "tool_calls": meta.get("tool_calls"), "judge": assessment.get("judge"),
                     "assessment_sha256": digest(folder / "assessment.json"),
                     "tool_compliance": "awaiting independent trace/dataflow review" if assigned["arm"] != "python" else "not assigned"})
    assert len({r["system"] for r in rows}) == len(rows), "Duplicate assigned attempts"
    comparisons = {}
    for pair_id in plan["pairs"]:
        pair_rows = [r for r in rows if r["pair"] == pair_id]
        if len(pair_rows) != 2:
            continue
        base = next(r for r in pair_rows if r["arm"] == "python")
        tool = next(r for r in pair_rows if r["arm"] != "python")
        reductions = {}
        for key in ("fresh_input_plus_output_tokens", "uncached_input_tokens", "agent_seconds", "command_seconds", "cli_seconds"):
            a, b = base[key], tool[key]
            reductions[key] = (a - b) / a if a is not None and b is not None and a > 0 else None
        for key in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"):
            a, b = (base["usage"] or {}).get(key), (tool["usage"] or {}).get(key)
            reductions[key] = (a - b) / a if a is not None and b is not None and a > 0 else None
        comparisons[pair_id] = {"python_computed": base["computed"], "tool_computed": tool["computed"],
                                "python_completion": base["completion"], "tool_completion": tool["completion"],
                                "tool_relative_resource_reductions": reductions,
                                "interpretation": "One matched pair; resource differences are descriptive. Check substantive tool use before attributing benefit."}
    known = all(r["usage"] is not None for r in rows)
    result = {"plan_sha256": digest(PLAN), "rows": rows, "paired_comparisons": comparisons, "pending": pending,
              "launched_cells": len(invocations), "assessed_attempts": len(rows),
              "unlaunched_cells": sorted(set(plan["systems"]) - set(invocations)),
              "token_totals_including_failures": {key: sum(r["usage"].get(key, 0) for r in rows) if known else None
                 for key in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens")},
              "direct_paid_api_usd": 0, "subscription_invoice_usd": None,
              "interpretation": "Do not pool weather questions, related datasets, judge costs or changed study phases into one causal efficiency estimate."}
    write(ROOT / "experiments/tooling-breadth-results-2026-10-08.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(summarize() if sys.argv[1] == "summarize" else run_pair(sys.argv[1]))
