"""One inspectable contract, assembled from declarations and scientific hooks.

The implementation may span files. Every instrument has one row here, including
its actual question, implementation and effect on completion and ranking.
"""
from fnmatch import fnmatchcase

from .judge import interpretation_question, report_question
from . import stages


def instruments(template, level=1):
    spec, hooks = template.spec, template.hooks
    rows = []

    def add(name, question, implementation, decided_by="computation", **extra):
        rows.append({"id": name, "question": question, "implementation": implementation,
                     "decided_by": decided_by, **extra})

    add("envelope", "Are the required results readable and is the regeneration command usable?", "assessment/assess.py:read_envelope")
    if callable(getattr(hooks, "expected_coordinates", None)):
        add("coverage", "Does the submission cover exactly the required labelled cases?", "reference.py:expected_coordinates")
    if template.uses_reference:
        add("variant", "Which accepted readings or named pitfalls fit the results within the error bounds?", "reference.py:reference",
            readings=len(template.combinations()), accepted_readings=sum(not template.pitfalls_in(c) for c in template.combinations()))
    for name in spec.get("invariants", []):
        function = hooks.INVARIANTS[name]
        add(f"invariant.{name}", (function.__doc__ or name.replace("_", " ")).strip(), f"reference.py:INVARIANTS[{name}]")
    for name in spec.get("probes", []):
        probe = getattr(hooks, "INVARIANCE_PROBES", {}).get(name)
        question = probe["passes"] if probe else {
            "replay": "Does the submitted command regenerate its results?",
            "changed_data": "Does the command follow changed data under the same accepted reading?",
            "responds_to_inputs": "Does the forecast respond to at least one relevant input change?",
        }.get(name, name.replace("_", " "))
        add(f"probe.{name}", question, f"reference.py:INVARIANCE_PROBES[{name}]" if probe else "reference.py:perturb_inputs; assessment/assess.py", "rerun")
        for part in (probe or {}).get("parts", {}):                # one rerun, one verdict per named part of the results
            add(f"probe.{name}.{part}", probe.get("part_passes", {}).get(part, f"{question} ({part})"), f"reference.py:INVARIANCE_PROBES[{name}].parts[{part}]", "rerun")
    claims = {**spec.get("claims", {}), **(spec.get("level2", {}).get("claims", {}) if level == 2 else {})}
    for name, requirement in claims.items():
        add(f"claim.{name}", requirement, "reference.py:expected_claims" if not isinstance(requirement, dict) else "reference.py:score")
    if level == 2:
        add("feedback.limit", "Were development-score requests within the declared budget?", "assessment/assess.py:_feedback_limit")
    for step in spec.get("process", []):
        judged = "method_statement" in step or "judge" in step
        question = report_question(step)["requirement"] if "judge" in step else step["requirement"]
        add(f"process.{step['id']}", question, f"spec.yaml:process[{step['id']}]", "judge" if judged else "computation",
            source=step["source"], evidence={key: step[key] for key in ("checks", "results", "method_statement", "judge") if key in step})
    rows += stages.rows(spec)
    for name in spec.get("interpretation", []):
        # A template may own the wording, or explicitly reuse a shared question.
        question = interpretation(spec, name)
        add(f"interpretation.{name}", question["requirement"],
            f"spec.yaml:judge_questions[{name}]" if name in spec.get("judge_questions", {}) else f"assessment/judge.py:OBLIGATIONS[{name}]", "judge")
    policy = spec.get("assessment_policy")
    for row in rows:
        # Older contracts retain their original all-checks completion policy.
        row["required_for"] = (["completion", "ranking"] if policy is None and row["decided_by"] != "judge" else
                               ["completion"] if policy is None else
                               [gate for gate in ("completion", "ranking") if any(fnmatchcase(row["id"], pattern) for pattern in policy[gate])])
    if spec.get("skill"):
        rows.append({"id": "skill", "question": spec["skill"]["ranking"], "implementation": "reference.py:score",
                     "decided_by": "score", "required_for": [], "splits": spec["skill"].get("splits", ["final"]),
                     "caveat": spec["skill"].get("caveat"), "ranking_enabled": spec["skill"].get("ranking_enabled", True)})
    return rows


def interpretation(spec, name):
    if name in spec.get("judge_questions", {}):
        return {"kind": "interpretation", **spec["judge_questions"][name]}
    return interpretation_question(name)


def contract(template, level=1):
    rows = instruments(template, level)
    stages.check_instruments(template.spec, [row["id"] for row in rows])
    policy = template.spec.get("assessment_policy")
    if policy is not None:
        for gate, patterns in policy.items():
            for pattern in patterns:
                if not any(fnmatchcase(row["id"], pattern) for row in rows):
                    # A policy can mention instruments only present at Level 2.
                    if level == 1 and pattern in ("feedback.limit", "claim.*"):
                        continue
                    raise ValueError(f"{gate} policy pattern {pattern!r} matches no instrument")
    return {"template": template.name, "spec_version": template.spec["spec_version"], "fingerprint": template.fingerprint(),
            "question": template.spec.get("question", template.spec["mode"]), "level": level,
            "results": template.spec["results"], "instruments": rows,
            "policy": policy or {"completion": ["*"], "ranking": "computed checks (legacy contract)"}}


def annotate(result, template, level):
    rubric = contract(template, level)
    declared = {row["id"]: row for row in rubric["instruments"]}
    for name, check in result["checks"].items():
        row = declared[name]
        check.update(required_for=row["required_for"], implementation=row["implementation"])
        check.setdefault("requirement", row["question"])
    result["rubric"] = rubric
    result["assessment_policy"] = rubric["policy"]
    result["ranking_enabled"] = template.spec.get("skill", {}).get("ranking_enabled", True)


def markdown(rubric, result=None):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [f"# {rubric['template']} — spec {rubric['spec_version']}", "", f"Question: {rubric['question']}", ""]
    if result:
        lines += [f"Completion: **{result['outcome']}** · ranking gate: **{result['ranking_outcome']}** · supplementary: **{result['advisory_outcome']}**", ""]
    lines += ["| Instrument | Question | Required for | Implementation | Result |", "| --- | --- | --- | --- | --- |"]
    for row in rubric["instruments"]:
        check = (result or {}).get("checks", {}).get(row["id"], {})
        state = check.get("state", "number" if row["id"] == "skill" else "not assessed")
        lines.append("| " + " | ".join(cell(v) for v in (row["id"], row["question"], ", ".join(row["required_for"]) or "supplementary", row["implementation"], state)) + " |")
    if result and result.get("stages"):
        score = result.get("stage_score", {})
        lines += ["", f"Stages passed: **{score.get('passed')} of {score.get('of')}** (weighted fraction {score.get('weighted_fraction')})", "",
                  "| Stage | Schema | Absolute | Local | Verdict |", "| --- | --- | --- | --- | --- |"]
        for row in result["stages"]:
            lines.append("| " + " | ".join(cell(v if v is not None else "none") for v in (row["id"], row["schema"], row["absolute"], row["local"], row["state"])) + " |")
    if result:
        lines += ["", "Check evidence:", ""]
        for name, check in result["checks"].items():
            lines.append(f"- **{name}** ({check['state']}): {check.get('detail', '')}")
    if result and result.get("skill"):
        import json
        lines += ["", "Skill:", "", "```json", json.dumps(result["skill"], indent=2), "```"]
    return "\n".join(lines) + "\n"
