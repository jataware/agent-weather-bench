"""Checks that no computation can settle: one narrow question each, decided on exact quotations.

A language model reads the brief and the submission and returns one verdict per
question. A verdict counts only if every passage it quotes appears in the file it
names. The judge is pinned: its model, effort, prompt and reply schema together
form its identity, and every judgement records that identity.
"""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .outcomes import FAIL, JUDGE, PASS, UNRESOLVED, headline, outcome

MODEL, EFFORT = "claude-opus-5-5", "high"
PROMPT = Path(__file__).with_name("judge-prompt.md")
TEXT_SUFFIXES = (".md", ".txt", ".json", ".py", ".sh", ".R", ".jl", ".yaml", ".yml", ".ipynb", ".toml", ".cfg")
FILE_LIMIT, TOTAL_LIMIT = 60_000, 400_000                       # characters shown to the judge, per file and in all

# Requirements on the written account. Each says when silence passes.
OBLIGATIONS = {
    "statistical_support": "Every claim of statistical significance, confidence or uncertainty respects the dependence in the data "
                           "(neighbouring grid cells, overlapping periods, a small number of years). Silence passes: a report that makes no such claim meets this.",
    "causation": "The report attributes no cause that its own evidence cannot establish. Silence passes: a report that attributes no cause meets this.",
    "generalization": "The report does not extend a result beyond the sample, region or period it was computed on. "
                      "Silence passes: a report that only describes what it computed meets this.",
    "consistency_across_artifacts": "The report, the structured answer and the code say the same thing about what was done and what was found. "
                                    "A statement in one that another contradicts is a violation.",
    "source_attribution": "The report separates correctly what the data source provides, what the brief specified, and what the agent chose. "
                          "Presenting the agent's own choice as a fact about the data, or as an instruction of the brief, is a violation.",
}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdicts"], "properties": {"verdicts": {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["id", "verdict", "basis", "reason_code", "reason", "citations"], "properties": {
        "id": {"type": "string"}, "verdict": {"type": "string", "enum": [PASS, FAIL, UNRESOLVED]},
        "basis": {"type": "string", "enum": ["quoted", "nothing_to_assess", "required_statement_absent"]},
        "reason_code": {"type": "string", "enum": ["none", "ambiguous_clause", "missing_evidence"]}, "reason": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["source", "quote"],
                                                 "properties": {"source": {"type": "string"}, "quote": {"type": "string"}}}}}}}}}


class JudgeUnavailable(RuntimeError):
    """The judge could not be reached or did not return a usable reply. Never the submission's fault."""


def judge_id():
    """Identity of the judge: its model, effort, prompt, obligations and reply schema."""
    material = json.dumps([MODEL, EFFORT, PROMPT.read_text(), OBLIGATIONS, SCHEMA], sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()[:16]


# ---- the questions an assessment leaves to the judge -------------------------------

def interpretation_question(name):
    return {"kind": "interpretation", "requirement": OBLIGATIONS[name], "silence": "passes"}


def statement_question(step, entry):
    """Does the code a method entry points to do what the entry says, and does that meet the step?"""
    return {"kind": "method_statement", "silence": "not applicable",
            "requirement": f"{step['requirement']} The answer documents this as: \"{entry['what'].strip()}\" and points to {json.dumps(entry['where'])}. "
                           "The requirement is met when the code at that place does what the statement says and that satisfies the first sentence. "
                           "It is violated when the code there does something else, or when what it does breaks the first sentence."}


def report_question(step):
    return {"kind": "report_statement", "silence": "fails", "requirement": f"{step['requirement']} {step['judge']} The statement is required: a report without it violates this."}


def pending(name, question, **evidence):
    """The row an assessment holds for a judge question until a judge decides it."""
    return {**outcome(UNRESOLVED, "No judge was run. " + question["requirement"], "judge_not_run", question=question, **evidence), "decided_by": JUDGE}


def questions_for(result, spec=None):
    """{check name: question} for every judge-decided row. Rows recorded before questions were stored are rebuilt from the row."""
    steps = {step["id"]: step for step in (spec or {}).get("process", [])}
    out = {}
    for name, row in result["checks"].items():
        if row.get("decided_by") != JUDGE:
            continue
        if "question" in row:
            out[name] = row["question"]
        elif name.startswith("interpretation."):
            out[name] = interpretation_question(name.split(".", 1)[1])
        elif "stated" in row and "pointer" in row:
            out[name] = statement_question(row, {"what": row["stated"], "where": row["pointer"]})
        else:
            step = steps.get(name.split(".", 1)[1], {})
            out[name] = report_question({"requirement": row.get("requirement", ""), "judge": step.get("judge", "")})
    return out


# ---- what the judge is shown ---------------------------------------------------------

def _digest(node):
    """A JSON value with every large numeric array replaced by a one-line description of it."""
    if isinstance(node, dict):
        return {key: _digest(value) for key, value in node.items()}
    if isinstance(node, list):
        flat, stack = [], [node]
        while stack and len(flat) <= 24:
            item = stack.pop()
            stack.extend(item) if isinstance(item, list) else flat.append(item)
        if len(flat) > 24 and all(isinstance(item, (int, float)) or item is None for item in flat):
            import numpy as np
            try:
                values = np.asarray(node, dtype=float)
                return f"<array of shape {tuple(values.shape)}: min {np.nanmin(values):.6g}, mean {np.nanmean(values):.6g}, max {np.nanmax(values):.6g}>"
            except (TypeError, ValueError):
                return f"<ragged array of {len(node)} rows>"
        return [_digest(item) for item in node]
    return node


def views(submission, brief=None, extra=None):
    """{name: text} of everything the judge may quote: the brief, the submission's text files, and controller summaries."""
    submission, files, withheld = Path(submission), {}, []
    if brief:
        files["task/brief.md"] = brief
    for path in sorted(submission.rglob("*")):
        relative = path.relative_to(submission)
        if not path.is_file() or path.is_symlink() or any(part.endswith(".zarr") or part.startswith(".") for part in relative.parts):
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(errors="replace")
        if path.suffix == ".json" and len(text) > 4000:
            try:
                text = json.dumps(_digest(json.loads(text)), indent=1)
            except ValueError:
                pass
        if len(text) > FILE_LIMIT:
            withheld.append(f"{relative} ({len(text)} characters)")
            continue
        files[str(relative)] = text
    for name, text in (extra or {}).items():
        files[name] = text
    core = {"task/brief.md", "report.md", "answer.json"} | set(extra or {})
    while sum(map(len, files.values())) > TOTAL_LIMIT:
        largest = max((name for name in files if name not in core), key=lambda name: len(files[name]), default=None)
        if largest is None:
            break
        withheld.append(f"{largest} ({len(files.pop(largest))} characters)")
    if withheld:
        files["controller/files-not-shown.txt"] = "These submitted files were too large to show:\n" + "\n".join(sorted(withheld)) + "\n"
    return files


def render(questions, files):
    parts = ["The files:\n"]
    parts += [f'<file name="{name}">\n{text}\n</file>\n' for name, text in files.items()]
    parts.append("The questions, as JSON. Return one verdict for each `id`.\n")
    parts.append(json.dumps([{"id": name, **{key: value for key, value in question.items() if key != "kind"}} for name, question in questions.items()], indent=1))
    return "\n".join(parts)


# ---- verdicts ------------------------------------------------------------------------

def _squash(text):
    return re.sub(r"\s+", " ", text).strip()


def validate_verdict(verdict, files, question=None):
    """Turn a judge's raw verdict into an outcome. A verdict whose quotation is not exact is discarded."""
    if not isinstance(verdict, dict) or verdict.get("verdict") not in (PASS, FAIL, UNRESOLVED) or not isinstance(verdict.get("reason"), str):
        return outcome(UNRESOLVED, "The judge response is not a valid verdict.", "invalid_citation")
    citations, basis = verdict.get("citations"), verdict.get("basis", "quoted")
    if not isinstance(citations, list) or not all(isinstance(c, dict) and isinstance(c.get("source"), str) and isinstance(c.get("quote"), str) and c["quote"].strip() for c in citations):
        return outcome(UNRESOLVED, "The judge response lacks well-formed citations.", "invalid_citation")
    inexact = [c for c in citations if _squash(c["quote"]) not in _squash(files.get(c["source"], ""))]
    if inexact:
        return outcome(UNRESOLVED, "A quoted passage does not appear in the cited file, so the verdict is discarded.", "invalid_citation",
                       inexact_citations=inexact)
    silence = (question or {}).get("silence")
    if verdict["verdict"] == UNRESOLVED:
        reason = verdict.get("reason_code") if verdict.get("reason_code") in ("missing_evidence", "ambiguous_clause") else "missing_evidence"
        return outcome(UNRESOLVED, verdict["reason"], reason, citations=citations)
    if verdict["verdict"] == PASS and not citations and not (basis == "nothing_to_assess" and silence == "passes"):
        return outcome(UNRESOLVED, "A pass must quote the evidence it rests on.", "invalid_citation")
    if verdict["verdict"] == FAIL and not citations and not (basis == "required_statement_absent" and silence == "fails"):
        return outcome(UNRESOLVED, "A failure must quote the passage at fault.", "invalid_citation")
    return outcome(verdict["verdict"], verdict["reason"], citations=citations, basis=basis if not citations else "quoted")


def apply(result, files, backend, spec=None, recorded=None):
    """Decide every judge question of an assessment, in one request, and recompute its headline.

    `backend(questions, files)` returns (raw verdicts, record). `recorded` is an earlier
    judgement of the same questions by the same judge, reused instead of asking again.
    Returns the judgement record to keep.
    """
    questions = questions_for(result, spec)
    key = hashlib.sha256(json.dumps([judge_id(), questions, sorted((name, hashlib.sha256(text.encode()).hexdigest()) for name, text in files.items())],
                                    sort_keys=True).encode()).hexdigest()
    if not questions:
        return None
    if recorded and recorded.get("key") == key:
        judgement = recorded
    else:
        judgement = {"key": key, "judge": {"id": judge_id(), "model": MODEL, "effort": EFFORT}, "questions": questions, "requests": []}
        try:
            raw, record = backend(questions, files)
            judgement["requests"].append(record)
            verdicts = {row.get("id"): row for row in raw if isinstance(row, dict)}
            voided = {name: validate_verdict(verdicts.get(name), files, question) for name, question in questions.items()}
            again = {name: {**questions[name], "earlier_reply_discarded": row["detail"] + " Quote character for character, or change the basis."}
                     for name, row in voided.items() if row.get("reason") == "invalid_citation"}
            if again:                                              # one more request, for the discarded verdicts only
                raw, record = backend(again, files)
                judgement["requests"].append(record)
                verdicts.update({row.get("id"): row for row in raw if isinstance(row, dict) and row.get("id") in again})
            judgement["verdicts"] = verdicts
        except JudgeUnavailable as error:
            judgement["unavailable"] = str(error)[:500]
    for name, question in questions.items():
        kept = {key: result["checks"][name][key] for key in ("requirement", "source", "pointer", "stated") if key in result["checks"][name]}
        if "unavailable" in judgement:
            row = outcome(UNRESOLVED, "The judge could not be run: " + judgement["unavailable"], "infrastructure")
        else:
            row = validate_verdict(judgement["verdicts"].get(name), files, question)
        result["checks"][name] = {**row, **kept, "question": question, "decided_by": JUDGE}
    result["judge"] = {**judgement["judge"], "requests": len(judgement["requests"]), "unavailable": "unavailable" in judgement,
                       "usage": [record.get("usage") for record in judgement["requests"]]}
    headline(result)
    return judgement


# ---- the pinned judge ---------------------------------------------------------------

def claude_cli(questions, files, seconds=900):
    """Ask the pinned model through the Claude command line: no tools, no project settings, one structured reply."""
    binary = shutil.which("claude")
    if not binary:
        raise JudgeUnavailable("The claude command is not installed")
    command = [binary, "--print", "--model", MODEL, "--effort", EFFORT, "--safe-mode", "--tools", "", "--no-session-persistence",
               "--disable-slash-commands", "--system-prompt", PROMPT.read_text(), "--output-format", "json", "--json-schema", json.dumps(SCHEMA)]
    with tempfile.TemporaryDirectory(prefix="assessment-judge-") as empty:
        try:
            done = subprocess.run(command, input=render(questions, files), capture_output=True, text=True, cwd=empty, timeout=seconds)
        except subprocess.TimeoutExpired:
            raise JudgeUnavailable("The judge request timed out") from None
    try:
        reply = json.loads(done.stdout)
        verdicts = reply["structured_output"]["verdicts"]
    except (ValueError, KeyError, TypeError):
        raise JudgeUnavailable(f"The judge returned no structured reply (exit {done.returncode}): {(done.stdout or done.stderr)[-300:]}") from None
    if reply.get("is_error"):
        raise JudgeUnavailable("The judge reported an error: " + str(reply.get("result"))[:300])
    usage = reply.get("usage") or {}
    return verdicts, {"model": next(iter(reply.get("modelUsage") or {}), MODEL), "seconds": (reply.get("duration_ms") or 0) / 1000,
                      "usage": {"input_tokens": usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0),
                                "output_tokens": usage.get("output_tokens", 0), "list_price_usd": reply.get("total_cost_usd")}}
