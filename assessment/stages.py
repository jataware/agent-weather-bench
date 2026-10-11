"""Per-stage verdicts for a long-horizon composition.

A template may declare `stages`: an ordered list of the parts of the job, each
owning a group of results. Every stage receives up to two verdicts.

- The *absolute* verdict asks whether the stage's product is right, judged from
  the controller's own inputs: a reference match on the stage's results, or a
  set of named checks.
- The *local* verdict asks whether the stage was done right given the
  submission's own upstream products: named checks that recompute the stage
  from the arrays the submission handed itself.

Before either runs, the stage's own results must be usable (the schema check).
A stage whose results are unusable fails. A local verdict whose upstream stage
failed its schema is `unresolved: invalid_upstream_contract`: the question
cannot be asked of broken inputs, and that is not this stage's fault.

The rollup is a profile of every stage with both verdicts, and a weighted
fraction of passed stages. Completion and ranking gates select `stage.*` rows
through the ordinary result policy.
"""
from .outcomes import FAIL, PASS, UNRESOLVED, combine, outcome

INVALID_UPSTREAM = "invalid_upstream_contract"
KINDS = ("results", "checks")


def validate(spec):
    """Structural validity of the `stages` declaration; instrument names are checked where instruments are known."""
    stages = spec.get("stages")
    if stages is None:
        return
    if not isinstance(stages, list) or not stages:
        raise ValueError("stages must be a nonempty list")
    seen = []
    for stage in stages:
        if not isinstance(stage, dict) or not isinstance(stage.get("id"), str) or not stage["id"] or not stage.get("requirement") or not stage.get("source"):
            raise ValueError("Each stage needs an id, a requirement and a source")
        if stage["id"] in seen:
            raise ValueError(f"Stage {stage['id']} is declared twice")
        results = stage.get("results", [])
        if not isinstance(results, list) or any(name not in spec["results"] for name in results):
            raise ValueError(f"Stage {stage['id']}: results must name declared results")
        for verdict in ("absolute", "local"):
            declared = stage.get(verdict)
            if declared is None:
                continue
            kinds = [key for key in KINDS if key in declared] if isinstance(declared, dict) else []
            if len(kinds) != 1 or not isinstance(declared[kinds[0]], list) or not declared[kinds[0]]:
                raise ValueError(f"Stage {stage['id']}: the {verdict} verdict needs exactly one of {KINDS}, a nonempty list")
            if kinds[0] == "results" and (verdict == "local" or any(name not in spec["results"] or spec["results"][name].get("free") for name in declared["results"])):
                raise ValueError(f"Stage {stage['id']}: an absolute verdict on results needs declared, reference-matched results; a local verdict rests on checks")
        if "absolute" not in stage and "local" not in stage:
            raise ValueError(f"Stage {stage['id']} declares no verdict")
        if any(up not in seen for up in stage.get("upstream", [])):
            raise ValueError(f"Stage {stage['id']}: upstream must name stages declared before it")
        weight = stage.get("weight", 1)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight <= 0:
            raise ValueError(f"Stage {stage['id']}: weight must be a positive number")
        if not isinstance(stage.get("review", []), list):
            raise ValueError(f"Stage {stage['id']}: review must list judge instruments")
        seen.append(stage["id"])


def named_checks(stage):
    """Every check id a stage's verdicts rest on."""
    names = []
    for verdict in ("absolute", "local"):
        declared = stage.get(verdict) or {}
        names += declared.get("checks", [])
    return names


def rows(spec):
    """Rubric rows for the stages: one instrument per stage, with its evidence declared."""
    out = []
    for stage in spec.get("stages", []):
        evidence = {verdict: stage[verdict] for verdict in ("absolute", "local") if verdict in stage}
        out.append({"id": f"stage.{stage['id']}", "question": stage["requirement"], "implementation": f"spec.yaml:stages[{stage['id']}]",
                    "decided_by": "computation", "source": stage["source"], "results": stage.get("results", []), "evidence": evidence,
                    "upstream": stage.get("upstream", []), "weight": stage.get("weight", 1), "review": stage.get("review", [])})
    return out


def _combined(checks, names, missing_detail):
    """Strict combination of named checks; the first unresolved reason carries through."""
    rows_ = []
    for name in names:
        if name not in checks:
            return outcome(UNRESOLVED, missing_detail.format(name=name), "infrastructure")
        rows_.append(checks[name])
    state = combine(rows_)
    detail = {PASS: "Every check this verdict rests on passed.", FAIL: "A check this verdict rests on failed: " +
              ", ".join(n for n, r in zip(names, rows_) if r["state"] == FAIL) + ".",
              UNRESOLVED: "A check this verdict rests on is unresolved: " + ", ".join(n for n, r in zip(names, rows_) if r["state"] == UNRESOLVED) + "."}[state]
    reason = next((r["reason"] for r in rows_ if r["state"] == UNRESOLVED), None) if state == UNRESOLVED else None
    return outcome(state, detail, reason, checks=names)


def evaluate(spec, checks, usable, agreement, coverage_failed=None):
    """One row per stage, in order, written into `checks` as `stage.<id>`; returns the profile and score.

    `usable` names the results that could be read. `agreement(names)` returns the
    outcome of a reference match on the named results, including the changed-data
    test where the probe ran. `coverage_failed` is the detail of a coverage check that
    left no result usable; a coverage gap that takes down some results shows in
    `usable` alone, so only the stages that own those results fail their schema.
    """
    schema_failures, profile = {}, []
    for stage in spec.get("stages", []):
        identifier, results = stage["id"], stage.get("results", [])
        unusable = [name for name in results if name not in usable] if coverage_failed is None else list(results)
        if unusable:
            first = coverage_failed or f"{unusable[0]} is missing or unusable"
            schema = outcome(FAIL, f"The stage's results cannot be used: {first}", unusable=unusable)
            schema_failures[identifier] = first
        else:
            schema = outcome(PASS, "Every result of the stage is readable, finite and of the declared shape." if results else "The stage declares no results.")
        row = {"schema": schema, "upstream": stage.get("upstream", []), "weight": stage.get("weight", 1), "review": stage.get("review", [])}
        if schema["state"] == FAIL:
            row["absolute"] = row["local"] = None
            verdict = outcome(FAIL, "Fails with its schema: " + schema["detail"], blocked_by="schema")
        else:
            parts = []
            if "absolute" in stage:
                declared = stage["absolute"]
                row["absolute"] = agreement(declared["results"]) if "results" in declared else _combined(checks, declared["checks"], "The check {name} was not made.")
                parts.append(row["absolute"])
            else:
                row["absolute"] = None
            if "local" in stage:
                broken = [up for up in stage.get("upstream", []) if up in schema_failures]
                if broken:
                    row["local"] = outcome(UNRESOLVED, f"The upstream stage {broken[0]} failed its schema ({schema_failures[broken[0]]}), so this stage cannot be judged on its own inputs.",
                                           INVALID_UPSTREAM, upstream_failed=broken)
                else:
                    row["local"] = _combined(checks, stage["local"]["checks"], "The check {name} was not made.")
                parts.append(row["local"])
            else:
                row["local"] = None
            state = combine(parts)
            reason = next((p["reason"] for p in parts if p["state"] == UNRESOLVED), None) if state == UNRESOLVED else None
            words = "; ".join(f"{verdict} {row[verdict]['state']}" + ("" if row[verdict]["state"] == PASS else f" ({row[verdict]['detail']})")
                              for verdict in ("absolute", "local") if row[verdict] is not None)
            verdict = outcome(state, f"Verdicts: {words}.", reason)
        checks[f"stage.{identifier}"] = {**verdict, **row}
        profile.append({"id": identifier, "state": verdict["state"], "schema": schema["state"],
                        "absolute": row["absolute"]["state"] if row["absolute"] else None, "local": row["local"]["state"] if row["local"] else None,
                        "weight": row["weight"]})
    return profile, score(profile)


def score(profile):
    """Weighted fraction of passed stages; unresolved stages count as not passed and are listed apart."""
    total = sum(row["weight"] for row in profile)
    passed = sum(row["weight"] for row in profile if row["state"] == PASS)
    return {"passed": sum(row["state"] == PASS for row in profile), "of": len(profile),
            "weighted_fraction": round(passed / total, 6) if total else None,
            "failed": [row["id"] for row in profile if row["state"] == FAIL],
            "unresolved": [row["id"] for row in profile if row["state"] == UNRESOLVED]}


def check_instruments(spec, instrument_ids):
    """Every check a stage names, and every review it lists, must be an instrument of the contract."""
    ids = set(instrument_ids)
    for stage in spec.get("stages", []):
        for name in named_checks(stage):
            if name not in ids:
                raise ValueError(f"Stage {stage['id']} names the check {name!r}, which is no instrument of this contract")
        for name in stage.get("review", []):
            if name not in ids:
                raise ValueError(f"Stage {stage['id']} lists the review {name!r}, which is no instrument of this contract")

