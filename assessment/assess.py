"""Assessment of one submission against one instance of a template.

Product mode checks the requested quantity under every accepted reading of the
brief. Process mode adds conformance to a named standard, step by step. Outcome
mode has no reference answer: it checks that the submission is a valid forecast
and scores it against withheld observations.
"""
import hashlib
import json
import re
import shutil
from pathlib import Path

from .compare import STORE, EnvelopeError, align, compare, read_results, summary
from .execute import valid_argv
from .judge import interpretation_question, pending, report_question, statement_question, views
from .outcomes import FAIL, JUDGE, PASS, UNRESOLVED, blocked, combine, headline, outcome
from .variant import _reference, classes, consistent, decide, split, summarise, table

__all__ = ["assess", "judge_files", "answer_digest", "JUDGE"]


def read_envelope(template, submission):
    """(answer, usable results, run command or None, problems by part). An EnvelopeError when no result can be read."""
    path, problems, answer = Path(submission) / "answer.json", {}, {}
    if not path.is_file():
        problems["answer.json"] = "The submission has no answer.json"
    else:
        try:
            answer = json.loads(path.read_text())
        except ValueError:
            problems["answer.json"] = "answer.json is not valid JSON"
        if not isinstance(answer, dict):
            answer, problems["answer.json"] = {}, "answer.json must be an object"
    results, unusable = read_results(template.spec["results"], submission, answer)
    if not results:
        raise EnvelopeError("The submission has no usable results: " + "; ".join(unusable.values()))
    problems.update(unusable)
    argv = (answer.get("run") or {}).get("argv") if isinstance(answer.get("run"), dict) else None
    if not valid_argv(argv):
        argv = None
        problems.setdefault("answer.json", "answer.json needs run.argv containing {input_dir} and {output_dir}")
    return answer, results, argv, problems


def answer_digest(submission):
    """Identity of a submitted answer: answer.json and every file of the results store. Rulings are keyed by it."""
    submission, digest = Path(submission), hashlib.sha256()
    if (submission / "answer.json").is_file():
        digest.update((submission / "answer.json").read_bytes())
    if not (submission / STORE).is_dir():
        return digest.hexdigest()                                  # an answer from before results moved into a store
    for path in sorted(p for p in (submission / STORE).rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(submission)).encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def judge_files(template, params, submission, level=1, supplied=()):
    """What the judge is shown for one submission: the brief, the submission's text and a summary of its arrays."""
    try:
        results, _ = read_results(template.spec["results"], submission, None)
        extra = {"controller/results-summary.txt": "Summary of the arrays in results.zarr, written by the controller.\n" + summary(template.spec["results"], results)}
    except EnvelopeError:
        extra = {}
    return views(submission, template.brief(params, level, supplied), extra)


class _Context:
    """Everything one assessment shares: the template, the submission, and how to rerun its code."""

    def __init__(self, template, params, submission, executor, scratch, seed):
        self.template, self.spec, self.hooks = template, template.spec, template.hooks
        self.params, self.submission, self.executor, self.scratch, self.seed = params, submission, executor, scratch, seed
        self.argv, self.usable, self.reference_rows, self.probe_rows = None, set(), None, None
        self.framed = callable(getattr(self.hooks, "expected_coordinates", None))

    def stage(self, label, prepare=None):
        folder = self.scratch / f"inputs-{label}"
        self.hooks.stage_inputs(self.template.private, self.params, folder)
        if prepare:
            prepare(folder)
        return folder

    def frame(self, raw, inputs):
        """Results reordered to the required cases, where the template names them. Raises EnvelopeError on a gap."""
        if not self.framed:
            return raw
        return align(self.spec["results"], raw, self.hooks.expected_coordinates(inputs, self.params))

    def rerun(self, label, inputs):
        """Run the declared command on `inputs`: (framed results, slim run record, problem outcome or None)."""
        if self.argv is None:
            return None, {}, blocked("envelope", "Fails with the envelope: the answer declares no usable run command, so its results cannot be regenerated.")
        record = self.executor.run(self.submission, inputs, self.argv, self.scratch / f"probe-{label}")
        slim = {key: record[key] for key in ("exit_code", "executor") if key in record}
        if record.get("infrastructure_unavailable"):
            return None, slim, outcome(UNRESOLVED, "The controller could not run the command: " + record.get("stderr", "")[:300], "infrastructure", run=slim)
        try:
            raw, problems = read_results(self.spec["results"], record["output"], record.get("answer"))
            if not raw:
                raise EnvelopeError("; ".join(problems.values()))
            framed = self.frame(raw, inputs)
        except EnvelopeError as error:
            slim["stderr"] = record.get("stderr", "")[-600:]
            if record.get("crashed_by_signal") and not (Path(record["output"]) / STORE).is_dir():
                # A native crash is the runtime's doing as far as anyone can tell; it does not show a defect in the method.
                return None, slim, outcome(UNRESOLVED, "The runtime crashed before the command wrote its results.", "infrastructure", run=slim)
            return None, slim, outcome(FAIL, "The run command did not produce usable results: " + str(error), run=slim)
        if record["exit_code"] != 0:
            slim["note"] = "The command wrote complete results and then exited abnormally; the results are used."
        return framed, slim, None


def assess(template, params, submission, executor, scratch, level=1, feedback=None, seed=20261006):
    """`feedback` is the controller's public summary of development-score requests, for Level 2.

    Checks that only a judge can decide are returned unresolved, each with its question;
    `assessment.judge.apply` decides them.
    """
    spec, submission, scratch = template.spec, Path(submission), Path(scratch)
    scratch.mkdir(parents=True, exist_ok=False)
    if level == 2 and "level2" not in spec:
        raise ValueError("This template has no Level 2")
    result = {"schema_version": 2, "template": template.name, "spec_version": spec["spec_version"], "fingerprint": template.fingerprint(),
              "mode": spec["mode"], "level": level, "instance": params, "executor": executor.name, "seed": seed}
    claims = {**spec.get("claims", {}), **(spec["level2"].get("claims", {}) if level == 2 else {})}
    context = _Context(template, params, submission, executor, scratch, seed)
    planned = ((["variant"] if spec["mode"] != "outcome" else []) + (["coverage"] if context.framed else [])
               + [f"invariant.{n}" for n in spec.get("invariants", [])] + [f"probe.{n}" for n in spec.get("probes", [])]
               + [f"claim.{n}" for n in claims] + (["feedback.limit"] if level == 2 else []))
    checks = {}

    def finish(answer):
        _process_steps(context, answer, checks, result)
        for name in spec.get("interpretation", []):
            checks[f"interpretation.{name}"] = pending(name, interpretation_question(name))
        for folder in scratch.glob("probe-*/stage"):
            shutil.rmtree(folder, ignore_errors=True)
        result["checks"] = checks
        return headline(result)

    def stop(check, message, answer):
        """Nothing usable to assess: this check fails, and every check that rests on the answer fails with it."""
        checks[check] = outcome(FAIL, message)
        for name in planned:
            checks.setdefault(name, blocked(check, f"Fails with the {check}: the submission has no usable answer to check."))
        return finish(answer)

    try:
        answer, raw, context.argv, problems = read_envelope(template, submission)
    except EnvelopeError as error:
        return stop("envelope", str(error), {})
    # One unusable part fails the envelope. Everything that does not need it is still assessed on its merits.
    checks["envelope"] = (outcome(FAIL, "Unusable parts: " + "; ".join(problems.values()), unusable_parts=sorted(problems)) if problems
                          else outcome(PASS, "The results store holds the named results, and answer.json declares a run command."))
    original = context.stage("original")
    context.usable = set(raw)
    try:
        results = context.frame(raw, original)
        if context.framed:
            checks["coverage"] = outcome(PASS, "The results cover exactly the required cases, each labelled with its own coordinates.")
    except EnvelopeError as error:
        return stop("coverage", "The results do not cover exactly the required cases: " + str(error), answer)

    for name in spec.get("invariants", []):
        try:
            ok, detail = template.hooks.INVARIANTS[name](results, params, original)
            checks[f"invariant.{name}"] = outcome(PASS if ok else FAIL, detail)
        except KeyError as missing:
            checks[f"invariant.{name}"] = blocked("envelope", f"Fails with the envelope: it needs the result {missing}, which is unusable.")
    if spec["mode"] == "outcome":
        _forecast_probes(context, results, original, checks)
    else:
        _reference_checks(context, results, original, answer, checks, result)
    _invariance_probes(context, results, checks)
    if spec.get("skill") and "coverage" in checks:
        try:
            result["skill"] = {name: template.hooks.score(results, params, template.private, name) for name in spec["skill"].get("splits", ["final"])}
        except KeyError:
            result["skill_not_scored"] = "The forecast it would score is unusable."
    _claims(context, results, answer, claims, checks, result)
    if level == 2:
        _feedback_limit(spec, feedback, checks, result)
    return finish(answer)


# ---- product and process modes: a reference answer exists -------------------------

def _follows_inputs(context, submitted, hits, rerun, rows, slim):
    """Verdict for the changed-data probe, and the consistent set on the changed data."""
    template = context.template
    unchanged = compare(context.spec["results"], rerun, submitted)[0]
    local, _ = consistent(template, rerun, rows, context.usable)
    if not hits:
        if unchanged:
            return outcome(FAIL, "The results did not change when the data changed.", run=slim), local
        return outcome(UNRESOLVED, "The results change with the data, but the submitted answer matches no listed reading, so their correctness is not established.",
                       "unknown_answer", run=slim), local
    shared = sorted(set(local) & set(hits))
    if shared:
        return outcome(PASS, "On changed data, the rerun agrees with a reading consistent with the submitted answer.", run=slim,
                       consistent_with=summarise(template, rows, shared)), shared
    detail = ("The results did not change when the data changed." if unchanged else
              "On changed data, the rerun matches no reading consistent with the submitted answer.")
    return outcome(FAIL, detail, run=slim, rerun_consistent_with=summarise(template, rows, local)), []


def _separating_seed(context, rows, hits, results, tries=4):
    """A data change under which the accepted and pitfall readings that fit the answer come apart.

    Returns (seed, True) when one of the candidate changes separates every accepted
    reading from every pitfall, (seed, False) when none does, and (seed, None) when
    the answer already fits only one kind of reading.
    """
    template = context.template
    accepted, pitfall = split(template, rows, hits)
    if not (accepted and pitfall):
        return context.seed, None
    best = None
    for offset in range(tries):
        seed = context.seed + offset
        folder = context.stage(f"candidate-{offset}", prepare=lambda folder, seed=seed: context.hooks.perturb_inputs(folder, seed, "data"))
        local = []
        for index in hits:
            try:
                local.append((rows[index][0], _reference(template, folder, context.params, rows[index][0], results), None))
            except (ValueError, KeyError) as error:
                local.append((rows[index][0], None, str(error)))
        mixed = sum({bool(template.pitfalls_in(local[i][0])) for i in group} == {True, False} for group in classes(template, local, list(range(len(local)))))
        shutil.rmtree(folder, ignore_errors=True)
        if best is None or mixed < best[0]:
            best = (mixed, seed)
        if mixed == 0:
            break
    return best[1], best[0] == 0


def _reference_checks(context, results, original, answer, checks, result):
    template, spec, hooks, params = context.template, context.spec, context.hooks, context.params
    probes = spec.get("probes", [])
    rows = table(template, original, params, given=results)
    unusable = sorted(set(template.matched()) - context.usable)
    hits, partial = consistent(template, results, rows, context.usable)        # matched on the results that can be read
    first = decide(template, rows, hits, partial)
    narrowed, probes_passed = list(hits), True

    if "replay" in probes:
        rerun, slim, problem = context.rerun("replay", original)
        if problem is None:
            same = compare(spec["results"], rerun, results)[0]
            problem = outcome(PASS if same else FAIL, "The run command regenerates the submitted results." if same else
                              "The run command produces results that differ from the submitted answer.", run=slim)
        checks["probe.replay"] = problem
        probes_passed &= problem["state"] == PASS
    if "changed_data" in probes:
        # Where the answer fits both an accepted reading and a pitfall, the controller looks for a data change that tells them apart.
        seed, separates = _separating_seed(context, rows, hits, results)
        changed = context.stage("changed-data", prepare=lambda folder: hooks.perturb_inputs(folder, seed, "data"))
        rerun, slim, problem = context.rerun("changed-data", changed)
        if problem is None:
            changed_rows = context.probe_rows = table(template, changed, params, given=rerun)
            if hits and any(rows[i][1] is not None and changed_rows[i][1] is not None and compare(template.matched(), changed_rows[i][1], rows[i][1])[0] for i in hits):
                problem, shared = outcome(UNRESOLVED, "The controller's data change did not alter the reference, so the probe cannot decide.", "infrastructure"), []
            else:
                problem, shared = _follows_inputs(context, results, hits, rerun, changed_rows, slim)
            if problem["state"] == PASS:
                narrowed = [i for i in narrowed if i in shared]
        if separates is not None:
            problem["data_change_chosen_to_separate_accepted_from_pitfall"] = separates
        checks["probe.changed_data"] = problem
        probes_passed &= problem["state"] == PASS

    final = decide(template, rows, narrowed, partial) if hits else first
    if first.get("reason") == "ambiguous_variant" or final.get("reason") == "ambiguous_variant":
        final["first_match"] = first["consistent_with"]
        if final["state"] == UNRESOLVED and probes_passed:
            # The results are right for this task and follow its data. Whether the method would also be right on another
            # task is a question for that task's own episode, not a defect shown here.
            final = outcome(PASS, "The results are correct on this instance. No data change separated the accepted reading from the pitfall, "
                            "so which of the two the method follows is undetermined.",
                            "ambiguous_variant", consistent_with=final["consistent_with"], pitfalls_possible=final["pitfalls_possible"],
                            first_match=first["consistent_with"])
    ruling = _ruling(template, context.submission) if final.get("reason") == "unknown_answer" else None
    if ruling:
        final = outcome(FAIL, "The results match no listed reading, and review ruled them incorrect: " + ruling["reason"],
                        ruling={key: ruling[key] for key in ("status", "ruled_by", "ruled_on", "evidence") if key in ruling}, nearest=final.get("nearest"))
    if unusable and final["state"] == PASS:
        final = {**blocked("envelope", "Fails with the envelope: " + ", ".join(unusable) + " is unusable. The results that can be read are consistent only with accepted readings."),
                 "consistent_with": final["consistent_with"], "unusable_results": unusable}
    checks["variant"] = final
    result["matched_conventions"] = summarise(template, rows, narrowed) if narrowed else None
    result["first_match_conventions"] = summarise(template, rows, hits) if hits else None
    declared = answer.get("choices") if isinstance(answer.get("choices"), dict) else {}
    public = spec.get("public_conventions", [])
    result["declared_choices"] = {"declared": declared, "public_conventions": public,
                                  "disagreements": [name for name in public if narrowed and name in declared and declared[name] not in result["matched_conventions"][name]],
                                  "note": "A disagreement is evidence for the interpretation check, not proof."}
    context.reference_rows, context.partial, context.narrowed, context.probes_passed = rows, partial, narrowed, probes_passed


def _ruling(template, submission):
    """A reviewer's ruling on this exact answer, if one is recorded."""
    import yaml
    path = template.folder / "rulings.yaml"
    if not path.is_file():
        return None
    digest = answer_digest(submission)
    return next((row for row in yaml.safe_load(path.read_text())["rulings"] if row["answer_sha256"] == digest), None)


# ---- outcome mode: no reference answer --------------------------------------------

def _forecast_probes(context, forecast, original, checks):
    """Leakage part of the validity gate. Any method is acceptable; only a forecast that does not come from its inputs fails."""
    spec, hooks = context.spec, context.hooks
    probes = spec.get("probes", [])
    if "replay" in probes:
        produced, slim, problem = context.rerun("replay", original)
        if problem is None:
            same = compare(spec["results"], produced, forecast)[0]
            problem = outcome(PASS if same else FAIL, "The run command regenerates the submitted forecast." if same else
                              "The run command produces a forecast that differs from the submitted one.", run=slim)
        checks["probe.replay"] = problem
    if "responds_to_inputs" in probes:
        moved, records, broken = [], {}, None
        for kind in hooks.RESPONSE_PERTURBATIONS:
            folder = context.stage(f"changed-{kind}", prepare=lambda folder, kind=kind: hooks.perturb_inputs(folder, context.seed, kind))
            produced, slim, problem = context.rerun(f"changed-{kind}", folder)
            records[kind] = slim
            if problem is not None:
                broken = problem
                break
            if not compare(spec["results"], produced, forecast)[0]:
                moved.append(kind)
        checks["probe.responds_to_inputs"] = broken or outcome(
            PASS if moved else FAIL, ("The forecast changes when these inputs change: " + ", ".join(moved) + ".") if moved else
            "The forecast does not change when any supplied input changes, so it does not come from the supplied data.",
            responds_to=moved, runs=records)


# ---- checks shared by every mode ---------------------------------------------------

def _invariance_probes(context, results, checks):
    """Probes of the form: change this input; that part of the results must not move.

    A template declares them in INVARIANCE_PROBES. They express rules such as "a
    forecast must not use later information" without reading any code.
    """
    declared = getattr(context.hooks, "INVARIANCE_PROBES", {})
    for name in context.spec.get("probes", []):
        if name not in declared:
            continue
        probe = declared[name]
        folder = context.stage(f"invariance-{name}", prepare=lambda folder, probe=probe: context.hooks.perturb_inputs(folder, context.seed, probe["perturb"]))
        produced, slim, problem = context.rerun(f"invariance-{name}", folder)
        if problem is None:
            try:
                same = compare(context.spec["results"], probe["unchanged"](produced, folder, context.params), probe["unchanged"](results, folder, context.params))[0]
                problem = outcome(PASS if same else FAIL, probe["passes"] if same else probe["fails"], run=slim)
            except KeyError as missing:
                problem = {**blocked("envelope", f"Fails with the envelope: it needs the result {missing}, which is unusable."), "run": slim}
        checks[f"probe.{name}"] = problem


def _claims(context, results, answer, claims, checks, result):
    stated = answer.get("claims") if isinstance(answer.get("claims"), dict) else {}
    # Claims made once per label of a dimension are keyed by that label; a bare list is read in the order of the submission's own labels.
    dimension = context.spec.get("claims_by")
    labels = [str(label) for label in results[dimension]] if dimension and dimension in results else []
    try:
        expected = context.hooks.expected_claims(results, context.params) if callable(getattr(context.hooks, "expected_claims", None)) else {}
    except KeyError:
        for name in claims:
            checks[f"claim.{name}"] = blocked("envelope", "Fails with the envelope: the results this claim rests on are unusable.")
        return
    for name, row in claims.items():
        got = stated.get(name) if name in stated else ...
        if isinstance(got, dict) and labels and all(label in got for label in labels):
            got = [got[label].get(name) if isinstance(got[label], dict) else got[label] for label in labels]
        elif got is ... and labels and all(isinstance(stated.get(label), dict) and name in stated[label] for label in labels):
            got = [stated[label][name] for label in labels]
        if got is ...:
            checks[f"claim.{name}"] = outcome(FAIL, "The brief asks for this claim and the answer does not state it.")
        elif isinstance(row, dict) and "metric" in row:              # a stated score, checked against the controller's own
            if got is None:
                checks[f"claim.{name}"] = outcome(PASS, "Stated as not measured.", stated=None)
                continue
            scores = result.get("skill", {}).get(row["split"]) or context.hooks.score(results, context.params, context.template.private, row["split"])
            ok = isinstance(got, (int, float)) and not isinstance(got, bool) and abs(got - scores[row["metric"]]) <= row["atol"]
            checks[f"claim.{name}"] = outcome(PASS if ok else FAIL, "The stated value equals the controller's score of the submitted forecast." if ok else
                                              "The stated value differs from the controller's score of the submitted forecast.",
                                              stated=got, **({} if ok else {"controller_value": scores[row["metric"]]}))
        else:                                                        # a conclusion that must follow from the submission's own numbers
            want = expected[name]
            if not isinstance(got, list) or len(got) != len(want):
                checks[f"claim.{name}"] = outcome(FAIL, f"The claim must have {len(want)} entries.", stated=got)
                continue
            wrong = [i for i, (value, allowed) in enumerate(zip(got, want)) if value not in allowed]
            checks[f"claim.{name}"] = outcome(FAIL if wrong else PASS, "The stated claim contradicts the submission's own numbers." if wrong else
                                              "The stated claim follows from the submission's own numbers.", stated=got,
                                              **({"contradicted_entries": wrong} if wrong else {}))


def _feedback_limit(spec, feedback, checks, result):
    limit = spec["level2"]["feedback"]["max_submissions"]
    if not isinstance(feedback, dict) or not isinstance(feedback.get("requests"), list):
        checks["feedback.limit"] = outcome(UNRESOLVED, "No trusted record of development-score requests is available.", "missing_evidence")
        return
    used = len(feedback["requests"])
    checks["feedback.limit"] = outcome(PASS if used <= limit else FAIL, f"{used} of {limit} development-score requests were used.",
                                       requests=used, limit=limit, denied=feedback.get("limit_denials", 0))
    result["feedback"] = feedback


def _process_steps(context, answer, checks, result):
    """One outcome per step of the standard, each from the most exact evidence the spec names."""
    files = None
    # `method` is a section of answer.json; one nested under `claims` is read as the same thing
    nested = answer["claims"].get("method") if isinstance(answer.get("claims"), dict) else None
    method = answer["method"] if isinstance(answer.get("method"), dict) else nested if isinstance(nested, dict) else {}
    for step in context.spec.get("process", []):
        base = {"requirement": step["requirement"], "source": step["source"]}
        if "checks" in step:
            rows = [checks[name] for name in step["checks"]]
            state = combine(rows)
            reason = next((row["reason"] for row in rows if row["state"] == UNRESOLVED), None) if state == UNRESOLVED else None
            row = outcome(state, {PASS: "Every check this step rests on passed.", FAIL: "A check this step rests on failed.",
                                  UNRESOLVED: "A check this step rests on is unresolved."}[state], reason, evidence_checks=step["checks"], **base)
        elif "results" in step:
            row = _results_step(context, step["results"], base)
        elif "method_statement" in step:
            files = files if files is not None else views(context.submission)
            entry = method.get(step["method_statement"])
            where = entry.get("where") if isinstance(entry, dict) else None
            if not (isinstance(entry, dict) and isinstance(entry.get("what"), str) and entry["what"].strip() and isinstance(where, dict)):
                row = outcome(FAIL, f"The brief asks for the method entry `{step['method_statement']}` and the answer does not give it (it needs `what` and `where`).", **base)
            elif not _pointer_resolves(where, files):
                row = outcome(FAIL, "The method entry points to no place in the submission: it needs a file, and a symbol that appears in it or a line range inside it.",
                              pointer=where, **base)
            else:
                row = pending(step["id"], statement_question(step, entry), pointer=where, stated=entry["what"][:400], **base)
        else:
            row = pending(step["id"], report_question(step), **base)
        checks[f"process.{step['id']}"] = row
    if context.spec.get("process"):
        result["process_not_applicable"] = context.spec.get("process_not_applicable", [])


def _pointer_resolves(where, files):
    """A pointer is a file in the submission plus a name that appears in it, or a line range that lies inside it.

    The symbol must be a name, optionally with `def` or `class` before it. A phrase does
    not count: a script that writes its own answer contains every phrase of that answer.
    """
    text = files.get(where.get("file")) if isinstance(where.get("file"), str) else None
    if text is None:
        return False
    symbol = where.get("symbol")
    if isinstance(symbol, str) and re.fullmatch(r"(?:def |class |function )?[A-Za-z_][\w.]*", symbol.strip()) and re.search(r"(?<![\w.])" + re.escape(symbol.strip()) + r"(?!\w)", text):
        return True
    lines = where.get("lines")
    return (isinstance(lines, list) and len(lines) == 2 and all(type(n) is int for n in lines) and 1 <= lines[0] <= lines[1] <= text.count("\n") + 1)


def _results_step(context, names, base):
    """Do the named results agree with the reference, looking only at the conventions that can change them?"""
    template, rows, partial = context.template, context.reference_rows, getattr(context, "partial", None)
    if rows is None:
        return {**blocked("envelope", "Fails with the envelope: the submission has no usable answer to check."), "evidence_results": names, **base}
    subset = {name: template.matched()[name] for name in names}
    relevant = []
    for dimension in template.spec.get("conventions", {}):
        # A convention matters to these results if switching it alone ever changes their reference, on the submitted
        # data or on the changed data. Two readings can coincide on one and still differ on the other.
        for table_rows in (rows, context.probe_rows or []):
            for a, (first, reference, _) in enumerate(table_rows):
                twins = [b for b, (other, _, _) in enumerate(table_rows) if b > a and all(other[d] == first[d] for d in first if d != dimension)]
                if reference is not None and any(table_rows[b][1] is not None and not compare(subset, table_rows[b][1], reference)[0] for b in twins):
                    relevant.append(dimension)
                    break
            if dimension in relevant:
                break
    if any(name not in context.usable for name in names):
        return {**blocked("envelope", "Fails with the envelope: " + ", ".join(n for n in names if n not in context.usable) + " is unusable."),
                "evidence_results": names, **base}
    agreeing = [i for i in range(len(rows)) if partial[i] and all(partial[i].get(name, {}).get("agrees") for name in names)]
    # What the probes established about the code narrows the readings: a reading the reruns ruled out is not one it follows.
    agreeing = [i for i in agreeing if i in context.narrowed] or agreeing
    seen = {tuple(rows[i][0][d] for d in relevant) for i in agreeing}
    pitfalls = [sorted(value for d, value in zip(relevant, combo) if template.spec["conventions"][d][value] == "pitfall") for combo in seen]
    extra = {"evidence_results": names, "conventions_that_matter": relevant, **base}
    if not seen:
        return outcome(UNRESOLVED, "These results match no listed reading.", "unknown_answer", **extra)
    if not any(pitfalls):
        return outcome(PASS, "These results agree with the reference only under accepted readings.", **extra)
    named = sorted({value for combo in pitfalls for value in combo})
    if all(pitfalls):
        return outcome(FAIL, "These results agree with the reference only under a known pitfall: " + ", ".join(named) + ".", pitfalls_possible=named, **extra)
    if getattr(context, "probes_passed", False):
        return outcome(PASS, "These results are correct on this instance. They fit both an accepted reading and a known pitfall (" + ", ".join(named)
                       + "), and no data change separated the two.", "ambiguous_variant", pitfalls_possible=named, **extra)
    return outcome(UNRESOLVED, "These results fit both an accepted reading and a known pitfall (" + ", ".join(named) + ").", "ambiguous_variant",
                   pitfalls_possible=named, **extra)
