"""Interpretation obligations: one narrow question each, decided on exact quotes.

No model backend is wired in yet. Without one every obligation is unresolved with
reason `judge_not_run`, which is reported separately from the computed outcome.
The verdict validator is complete, so a backend only has to return verdicts.
"""
from .outcomes import FAIL, PASS, UNRESOLVED, outcome

OBLIGATIONS = {
    "statistical_support": "Does any claim of significance or uncertainty respect the dependence in the data?",
    "causation": "Does the report attribute a cause that the evidence cannot establish?",
    "generalization": "Does the report extend a result beyond the sample, region or period it was computed on?",
    "consistency_across_artifacts": "Do the report, the captions, the structured answer and the code say the same thing?",
    "source_attribution": "Does the report correctly separate what comes from the data source, from the brief, and from the agent's own choices?",
}


def validate_verdict(verdict, files):
    """Turn a judge's raw verdict into an outcome, voiding it when a quote is not exact."""
    if not isinstance(verdict, dict) or verdict.get("verdict") not in (PASS, FAIL, UNRESOLVED) or not isinstance(verdict.get("reason"), str):
        return outcome(UNRESOLVED, "The judge response is not a valid verdict.", "invalid_citation")
    citations = verdict.get("citations")
    if not isinstance(citations, list) or not all(isinstance(c, dict) and isinstance(c.get("source"), str) and isinstance(c.get("quote"), str) and c["quote"].strip() for c in citations):
        return outcome(UNRESOLVED, "The judge response lacks well-formed citations.", "invalid_citation")
    inexact = [c for c in citations if c["quote"] not in files.get(c["source"], "")]
    if inexact:
        return outcome(UNRESOLVED, "A quoted passage does not appear in the cited file, so the verdict is discarded.", "invalid_citation",
                       inexact_citations=inexact)
    if verdict["verdict"] == FAIL and len(citations) < 2:
        return outcome(UNRESOLVED, "A failure must quote both the claim and the evidence that contradicts it.", "invalid_citation")
    if verdict["verdict"] == PASS and not citations:
        return outcome(UNRESOLVED, "A pass must quote the evidence it rests on.", "invalid_citation")
    if verdict["verdict"] == UNRESOLVED:
        reason = verdict.get("reason_code") if verdict.get("reason_code") in ("missing_evidence", "ambiguous_clause") else "missing_evidence"
        return outcome(UNRESOLVED, verdict["reason"], reason, citations=citations)
    return outcome(verdict["verdict"], verdict["reason"], citations=citations)


def interpret(obligations, files, backend=None):
    """One outcome per obligation. `backend(question, files)` returns a raw verdict."""
    unknown = sorted(set(obligations) - set(OBLIGATIONS))
    if unknown:
        raise ValueError(f"Unknown interpretation obligations: {unknown}")
    if backend is None:
        return {name: outcome(UNRESOLVED, "No judge was run. " + OBLIGATIONS[name], "judge_not_run") for name in obligations}
    return {name: validate_verdict(backend(OBLIGATIONS[name], files), files) for name in obligations}
