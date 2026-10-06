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
           "judge_not_run", "invalid_citation", "missing_evidence")


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

    `outcome` is the headline and counts every check. `computed_outcome` leaves out
    the checks a judge decides, and is kept as a component.
    """
    checks = result["checks"]
    result["checks"] = dict(sorted(checks.items()))
    result["computed_outcome"] = combine([row for row in checks.values() if row.get("decided_by") != JUDGE])
    result["judged_outcome"] = combine([row for row in checks.values() if row.get("decided_by") == JUDGE] or [outcome(PASS)])
    result["outcome"] = combine(list(checks.values()))
    result["unresolved_reasons"] = sorted({row["reason"] for row in checks.values() if row["state"] == UNRESOLVED})
    if "skill" in result:
        result["skill_valid_for_ranking"] = result["computed_outcome"] == PASS
    return result
