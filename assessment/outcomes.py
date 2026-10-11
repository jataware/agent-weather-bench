"""Every check returns pass, fail or unresolved.

Fail means the submission is at fault: a wrong result, a missing piece the brief
asked for, or a check that cannot be made because the submission's own earlier
result is broken. Unresolved means something outside the submission left the
question open.
"""

PASS, FAIL, UNRESOLVED = "pass", "fail", "unresolved"
JUDGE = "judge"                                                    # value of `decided_by` for checks no computation can settle

# Why a question stayed open. Each names a cause outside the submission. Never merged with a failure.
REASONS = ("ambiguous_clause", "ambiguous_variant", "unknown_answer", "infrastructure",
           "judge_not_run", "invalid_citation", "missing_evidence",
           "invalid_upstream_contract")                            # a stage's own inputs, made by the submission upstream, are unusable


def outcome(state, detail="", reason=None, **evidence):
    if state not in (PASS, FAIL, UNRESOLVED):
        raise ValueError("Unknown outcome state")
    if (state == UNRESOLVED) != (reason is not None) and state != PASS:
        raise ValueError("Unresolved outcomes need a reason code; failures must not carry one")
    if reason is not None and reason not in REASONS:
        raise ValueError("Unknown reason code: " + str(reason))
    row = {"state": state, "detail": detail}
    if reason is not None:
        row["reason"] = reason
    row.update(evidence)
    return row


def blocked(cause, detail):
    """A check that cannot be made because an earlier part of the same submission is broken. It fails, and names the cause."""
    return outcome(FAIL, detail, blocked_by=cause)


def combine(rows):
    """Pass only when everything passes; any failure fails; otherwise unresolved."""
    states = [row["state"] for row in rows]
    if FAIL in states:
        return FAIL
    return UNRESOLVED if UNRESOLVED in states else PASS


def headline(result):
    """Fill in the summary fields of an assessment from its checks.

    `outcome` combines the declared completion gates; legacy contracts count every
    check. Computed, judged, supplementary and ranking summaries remain visible.
    """
    checks = result["checks"]
    result["checks"] = dict(sorted(checks.items()))
    result["computed_outcome"] = combine([row for row in checks.values() if row.get("decided_by") != JUDGE])
    result["judged_outcome"] = combine([row for row in checks.values() if row.get("decided_by") == JUDGE] or [outcome(PASS)])
    result["all_checks_outcome"] = combine(list(checks.values()))
    explicit = "assessment_policy" in result
    result["outcome"] = combine([row for row in checks.values() if "completion" in row.get("required_for", [])]) if explicit else result["all_checks_outcome"]
    result["ranking_outcome"] = combine([row for row in checks.values() if "ranking" in row.get("required_for", [])]) if explicit else result["computed_outcome"]
    result["advisory_outcome"] = combine([row for row in checks.values() if not row.get("required_for")]) if explicit else result["judged_outcome"]
    result["unresolved_reasons"] = sorted({row["reason"] for row in checks.values() if row["state"] == UNRESOLVED})
    if "skill" in result:
        result["skill_valid_for_ranking"] = result["ranking_outcome"] == PASS and result.get("ranking_enabled", True)
    return result
