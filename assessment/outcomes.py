"""Every check returns pass, fail or unresolved. Fail means a demonstrated defect."""

PASS, FAIL, UNRESOLVED = "pass", "fail", "unresolved"

# Why the evidence did not decide a question. Never merged with a failure.
REASONS = ("missing_evidence", "ambiguous_clause", "invalid_citation", "ambiguous_variant",
           "unknown_answer", "infrastructure", "judge_not_run", "not_assessed")


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


def combine(rows):
    """Pass only when everything passes; any failure fails; otherwise unresolved."""
    states = [row["state"] for row in rows]
    if FAIL in states:
        return FAIL
    return UNRESOLVED if UNRESOLVED in states else PASS
