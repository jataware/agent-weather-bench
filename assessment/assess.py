"""Assessment of one submission against one instance of a template.

Product mode checks the requested quantity under every accepted reading of the
brief. Process mode adds conformance to a named standard, step by step. Outcome
mode has no reference answer: it checks that the submission is a valid forecast
and scores it against withheld observations.
"""
import json
import re
import shutil
from pathlib import Path

from .compare import EnvelopeError, align, compare, regroup, usable
from .execute import valid_argv
from .judge import interpret
from .outcomes import FAIL, PASS, UNRESOLVED, combine, outcome
from .variant import consistent, decide, discriminating_instance, split, summarise, table

TEXT_SUFFIXES = (".md", ".txt", ".json", ".py", ".sh", ".R", ".jl", ".yaml", ".yml")
JUDGE = "judge"                                                    # value of `decided_by` for checks no computation can settle


def _labels(template, params):
    """(dimension, labels) when the spec lets results be grouped by the labels of a leading dimension."""
    grouping = template.spec.get("grouping")
    return (grouping["dim"], [str(label) for label in params[grouping["labels_from"]]]) if grouping else (None, [])


def read_envelope(template, submission, params):
    """(answer, usable results, argv, per-result problems), or an EnvelopeError when nothing can be assessed."""
    path = Path(submission) / "answer.json"
    if not path.is_file():
        raise EnvelopeError("The submission has no answer.json")
    try:
        answer = json.loads(path.read_text())
    except ValueError:
        raise EnvelopeError("answer.json is not valid JSON") from None
    if not isinstance(answer, dict):
        raise EnvelopeError("answer.json must be an object")
    raw, regrouped = regroup(template.spec["results"], answer.get("results"), *_labels(template, params))
    results, problems = usable(template.spec["results"], raw)
    answer["_results_were_grouped_by_label"] = regrouped
    if not results:
        raise EnvelopeError("answer.json has no usable results: " + "; ".join(problems.values()))
    argv = (answer.get("run") or {}).get("argv") if isinstance(answer.get("run"), dict) else None
    if not valid_argv(argv):
        raise EnvelopeError("answer.json needs run.argv containing {input_dir} and {output_dir}")
    return answer, results, argv, problems


def _texts(submission, limit=200000):
    files = {}
    for path in sorted(Path(submission).rglob("*")):
        if path.is_file() and path.suffix in TEXT_SUFFIXES and path.stat().st_size <= limit:
            files[str(path.relative_to(submission))] = path.read_text(errors="replace")
    return files


class _Context:
    """Everything one assessment shares: the template, the submission, and how to rerun its code."""

    def __init__(self, template, params, submission, executor, scratch, seed):
        self.template, self.spec, self.hooks = template, template.spec, template.hooks
        self.params, self.submission, self.executor, self.scratch, self.seed = params, submission, executor, scratch, seed
        self.argv = None
        self.framed = callable(getattr(self.hooks, "expected_coordinates", None))

    def stage(self, label, instance=None, prepare=None):
        folder = self.scratch / f"inputs-{label}"
        self.hooks.stage_inputs(self.template.private, instance or self.params, folder)
        if prepare:
            prepare(folder)
        return folder

    def frame(self, raw, inputs, instance=None):
        """Results reordered to the required cases, where the template names them. Raises EnvelopeError on a gap."""
        if not self.framed:
            return raw
        return align(self.spec["results"], raw, self.hooks.expected_coordinates(inputs, instance or self.params))

    def rerun(self, label, inputs, instance=None):
        """Run the declared command on `inputs`: (framed results, slim run record, problem outcome or None)."""
        record = self.executor.run(self.submission, inputs, self.argv, self.scratch / f"probe-{label}")
        slim = {key: record[key] for key in ("exit_code", "executor") if key in record}
        if record.get("infrastructure_unavailable"):
            return None, slim, outcome(UNRESOLVED, "The controller could not run the command: " + record.get("stderr", "")[:300], "infrastructure", run=slim)
        if record.get("answer") is None:
            slim["stderr"] = record.get("stderr", "")[-600:]
            if record.get("crashed_by_signal"):
                # A native crash is the runtime's doing as far as anyone can tell; it does not show a defect in the method.
                return None, slim, outcome(UNRESOLVED, "The runtime crashed before the command wrote an answer.", "infrastructure", run=slim)
            return None, slim, outcome(FAIL, "The run command did not produce an answer.json.", run=slim)
        if record["exit_code"] != 0:
            slim["note"] = "The command wrote a complete answer and then exited abnormally; the answer is used."
        try:
            given = record["answer"].get("results") if isinstance(record["answer"], dict) else None
            given, _ = regroup(self.spec["results"], given, *_labels(self.template, instance or self.params))
            raw, problems = usable(self.spec["results"], given)
            if not raw:
                raise EnvelopeError("; ".join(problems.values()))
            return self.frame(raw, inputs, instance), slim, None
        except EnvelopeError as error:
            return None, slim, outcome(FAIL, "The run command's answer is unusable: " + str(error), run=slim)


def assess(template, params, submission, executor, scratch, level=1, feedback=None, judge_backend=None, seed=20261006):
    """`feedback` is the controller's public summary of development-score requests, for Level 2."""
    spec, submission, scratch = template.spec, Path(submission), Path(scratch)
    scratch.mkdir(parents=True, exist_ok=False)
    if level == 2 and "level2" not in spec:
        raise ValueError("This template has no Level 2")
    result = {"schema_version": 1, "template": template.name, "spec_version": spec["spec_version"], "fingerprint": template.fingerprint(),
              "mode": spec["mode"], "level": level, "instance": params, "executor": executor.name, "seed": seed}
    claims = {**spec.get("claims", {}), **(spec["level2"].get("claims", {}) if level == 2 else {})}
    context = _Context(template, params, submission, executor, scratch, seed)
    planned = ((["variant"] if spec["mode"] != "outcome" else []) + (["coverage"] if context.framed else [])
               + [f"invariant.{n}" for n in spec.get("invariants", [])] + [f"probe.{n}" for n in spec.get("probes", [])]
               + [f"claim.{n}" for n in claims] + (["feedback.limit"] if level == 2 else []) + [f"process.{s['id']}" for s in spec.get("process", [])])
    checks = {}

    def interpretation():
        rows = interpret(spec.get("interpretation", []), _texts(submission), judge_backend)
        return {f"interpretation.{name}": {**row, "decided_by": JUDGE} for name, row in rows.items()}

    def stop(check, message):
        """A submission with no usable answer: fail here, and guess at nothing else."""
        checks[check] = outcome(FAIL, message)
        for name in planned:
            checks.setdefault(name, outcome(UNRESOLVED, "Not assessed: the submission has no usable answer.", "not_assessed"))
        checks.update(interpretation())
        return _finish(result, checks)

    try:
        answer, raw, context.argv, problems = read_envelope(template, submission, params)
        result["results_layout"] = "grouped by label; read as arrays" if answer.pop("_results_were_grouped_by_label") else "arrays"
    except EnvelopeError as error:
        return stop("envelope", str(error))
    # One unusable result fails the envelope, and everything that does not need it is still assessed.
    checks["envelope"] = (outcome(FAIL, "Unusable results: " + "; ".join(problems.values()), unusable_results=sorted(problems)) if problems
                          else outcome(PASS, "answer.json holds the named results and a run command."))
    original = context.stage("original")
    context.usable = set(raw)
    try:
        results = context.frame(raw, original)
        if context.framed:
            checks["coverage"] = outcome(PASS, "The results cover exactly the required cases, each labelled with its own coordinates.")
    except EnvelopeError as error:
        return stop("coverage", "The results do not cover exactly the required cases: " + str(error))

    for name in spec.get("invariants", []):
        try:
            ok, detail = template.hooks.INVARIANTS[name](results, params, original)
            checks[f"invariant.{name}"] = outcome(PASS if ok else FAIL, detail)
        except KeyError as missing:
            checks[f"invariant.{name}"] = outcome(UNRESOLVED, f"Not assessed: it needs the result {missing}, which is unusable.", "not_assessed")
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
    _process_steps(context, answer, checks, result)
    checks.update(interpretation())
    for folder in scratch.glob("probe-*/stage"):
        shutil.rmtree(folder, ignore_errors=True)
    return _finish(result, checks)


# ---- product and process modes: a reference answer exists -------------------------

def _follows_inputs(context, name, submitted, hits, rerun, rows, slim):
    """Verdict for a changed-input probe, and the consistent set on the changed inputs."""
    template = context.template
    unchanged = compare(context.spec["results"], rerun, submitted)[0]
    local, _ = consistent(template, rerun, rows, context.usable)
    if not hits:
        if unchanged:
            return outcome(FAIL, "The results did not change when the inputs changed.", run=slim), local
        return outcome(UNRESOLVED, "The results change with the inputs, but the submitted answer matches no listed reading, so their correctness is not established.",
                       "unknown_answer", run=slim), local
    shared = sorted(set(local) & set(hits))
    if shared:
        return outcome(PASS, f"On {name}, the rerun agrees with a reading consistent with the submitted answer.", run=slim,
                       consistent_with=summarise(template, rows, shared)), shared
    detail = ("The results did not change when the inputs changed." if unchanged else
              f"On {name}, the rerun matches no reading consistent with the submitted answer.")
    return outcome(FAIL, detail, run=slim, rerun_consistent_with=summarise(template, rows, local)), []


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
        changed = context.stage("changed-data", prepare=lambda folder: hooks.perturb_inputs(folder, context.seed, "data"))
        rerun, slim, problem = context.rerun("changed-data", changed)
        if problem is None:
            changed_rows = table(template, changed, params, given=rerun)
            if hits and any(rows[i][1] is not None and changed_rows[i][1] is not None and compare(template.matched(), changed_rows[i][1], rows[i][1])[0] for i in hits):
                problem, shared = outcome(UNRESOLVED, "The controller's data change did not alter the reference, so the probe cannot decide.", "infrastructure"), []
            else:
                problem, shared = _follows_inputs(context, "changed data", results, hits, rerun, changed_rows, slim)
            if problem["state"] == PASS:
                narrowed = [i for i in narrowed if i in shared]
        checks["probe.changed_data"] = problem
        probes_passed &= problem["state"] == PASS
    if "changed_instance" in probes:
        shared_inputs = getattr(hooks, "INPUTS_SHARED_ACROSS_INSTANCES", False)

        def inputs_for(candidate):
            if shared_inputs:
                return original
            folder = context.scratch / "candidates" / candidate["id"]
            if not folder.exists():
                hooks.stage_inputs(template.private, candidate, folder)
            return folder
        other, separates = discriminating_instance(template, inputs_for, params, rows, narrowed)
        staged = context.stage("changed-instance", instance=other)
        rerun, slim, problem = context.rerun("changed-instance", staged, instance=other)
        if problem is None:
            problem, shared = _follows_inputs(context, f"instance {other['id']}", results, narrowed or hits, rerun,
                                              table(template, staged, other, given=rerun), slim)
            if problem["state"] == PASS:
                narrowed = [i for i in narrowed if i in shared]
        problem["probe_instance"], problem["chosen_to_separate_accepted_from_pitfall"] = other["id"], bool(separates)
        checks["probe.changed_instance"] = problem
        probes_passed &= problem["state"] == PASS

    final = decide(template, rows, narrowed, partial) if hits else first
    if first.get("reason") == "ambiguous_variant" or final.get("reason") == "ambiguous_variant":
        final["first_match"] = first["consistent_with"]
        if final["state"] == UNRESOLVED and spec["mode"] == "product" and probes_passed:
            # The delivered product is correct for this instance; the method stays undetermined.
            final = outcome(PASS, "The product is correct on this instance. No probe separated the accepted reading from the pitfall, so the method is undetermined.",
                            "ambiguous_variant", consistent_with=final["consistent_with"], pitfalls_possible=final["pitfalls_possible"],
                            first_match=first["consistent_with"])
    ruling = _ruling(template, context.submission) if final.get("reason") == "unknown_answer" else None
    if ruling:
        final = outcome(FAIL, "The results match no listed reading, and review ruled them incorrect: " + ruling["reason"],
                        ruling={key: ruling[key] for key in ("status", "ruled_by", "ruled_on", "evidence") if key in ruling}, nearest=final.get("nearest"))
    if unusable and final["state"] == PASS:
        # Nothing wrong was found in what can be read, but a required result cannot be read at all.
        final = outcome(UNRESOLVED, "The usable results are consistent only with accepted readings; not assessed in full because "
                        + ", ".join(unusable) + " is unusable.", "not_assessed", consistent_with=final["consistent_with"], unusable_results=unusable)
    checks["variant"] = final
    result["matched_conventions"] = summarise(template, rows, narrowed) if narrowed else None
    result["first_match_conventions"] = summarise(template, rows, hits) if hits else None
    declared = answer.get("choices") if isinstance(answer.get("choices"), dict) else {}
    public = spec.get("public_conventions", [])
    result["declared_choices"] = {"declared": declared, "public_conventions": public,
                                  "disagreements": [name for name in public if narrowed and name in declared and declared[name] not in result["matched_conventions"][name]],
                                  "note": "A disagreement is evidence for the interpretation check, not proof."}
    context.reference_rows, context.partial = rows, partial


def _ruling(template, submission):
    """A reviewer's ruling on this exact answer, if one is recorded. Rulings are keyed by the hash of answer.json."""
    import hashlib

    import yaml
    path = template.folder / "rulings.yaml"
    if not path.is_file():
        return None
    digest = hashlib.sha256((Path(submission) / "answer.json").read_bytes()).hexdigest()
    return next((row for row in yaml.safe_load(path.read_text())["rulings"] if row["answer_sha256"] == digest), None)


# ---- outcome mode: no reference answer --------------------------------------------

def _forecast_probes(context, forecast, original, checks):
    """Leakage part of the validity gate. Any method is acceptable; only a forecast that does not come from its inputs fails."""
    spec, hooks, params = context.spec, context.hooks, context.params
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
    if "changed_instance" in probes:
        hidden = getattr(hooks, "UNDOCUMENTED_PARAMS", ())            # never vary a parameter the brief does not explain
        others = [c for c in hooks.candidate_instances() if c["id"] != params["id"] and all(c[k] == params[k] for k in hidden)]
        other = max(others, key=lambda c: sum(c[k] != params[k] for k in params if k != "id"))
        folder = context.stage("changed-instance", instance=other)
        produced, slim, problem = context.rerun("changed-instance", folder, instance=other)
        if problem is None:
            broken = [f"{name}: {detail}" for name in spec.get("invariants", [])
                      for ok, detail in [hooks.INVARIANTS[name](produced, other, folder)] if not ok]
            problem = outcome(FAIL if broken else PASS, ("On another instance the code does not produce a valid forecast: " + "; ".join(broken)) if broken
                              else "On another instance the code produces a valid forecast.", run=slim)
            if not broken and spec.get("skill"):
                problem["skill_on_probe_instance"] = hooks.score(produced, other, context.template.private, spec["skill"].get("splits", ["final"])[0])
        elif problem["state"] == FAIL:
            problem["detail"] = "On another instance the code does not produce a valid forecast. " + problem["detail"]
        problem["probe_instance"] = other["id"]
        checks["probe.changed_instance"] = problem


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
                problem = outcome(UNRESOLVED, f"Not assessed: it needs the result {missing}, which is unusable.", "not_assessed", run=slim)
        checks[f"probe.{name}"] = problem


def _claims(context, results, answer, claims, checks, result):
    stated = answer.get("claims") if isinstance(answer.get("claims"), dict) else {}
    _, labels = _labels(context.template, context.params)
    try:
        expected = context.hooks.expected_claims(results, context.params) if callable(getattr(context.hooks, "expected_claims", None)) else {}
    except KeyError:
        for name in claims:
            checks[f"claim.{name}"] = outcome(UNRESOLVED, "Not assessed: the results it rests on are unusable.", "not_assessed")
        return
    for name, row in claims.items():
        got = stated.get(name) if name in stated else ...
        # a claim given per label, as {label: value} or {label: {claim: value}}, is read as the list in label order
        if isinstance(got, dict) and labels and all(label in got for label in labels):
            got = [got[label].get(name) if isinstance(got[label], dict) else got[label] for label in labels]
        elif got is ... and labels and all(isinstance(stated.get(label), dict) and name in stated[label] for label in labels):
            got = [stated[label][name] for label in labels]
        if got is ...:
            checks[f"claim.{name}"] = outcome(UNRESOLVED, "The answer does not state this claim.", "missing_evidence")
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
    template, files = context.template, None
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
            files = files if files is not None else _texts(context.submission)
            entry = method.get(step["method_statement"])
            where = entry.get("where") if isinstance(entry, dict) else None
            if not (isinstance(entry, dict) and isinstance(entry.get("what"), str) and entry["what"].strip() and isinstance(where, dict)):
                row = outcome(UNRESOLVED, f"The answer's method section has no usable entry `{step['method_statement']}` (it needs `what` and `where`).",
                              "missing_evidence", **base)
            elif not _pointer_resolves(where, files):
                row = outcome(UNRESOLVED, "The method entry does not point to a place in the submission: it needs a file, and a symbol that appears in it or a line range inside it.",
                              "missing_evidence", pointer=where, **base)
            else:
                row = {**outcome(UNRESOLVED, "The pointer resolves. Whether that code does what the step requires is a judge question, and no judge was run.",
                                 "judge_not_run", pointer=where, stated=entry["what"][:400], **base), "decided_by": JUDGE}
        else:
            row = {**outcome(UNRESOLVED, "No judge was run. " + step["judge"], "judge_not_run", **base), "decided_by": JUDGE}
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
    template, rows, partial = context.template, context.reference_rows, context.partial
    subset = {name: template.matched()[name] for name in names}
    relevant = []
    for dimension, values in template.spec.get("conventions", {}).items():
        # a convention matters to these results if switching it alone ever changes their reference
        for a, (first, reference, _) in enumerate(rows):
            twins = [b for b, (other, _, _) in enumerate(rows) if b > a and all(other[d] == first[d] for d in first if d != dimension)]
            if reference is not None and any(rows[b][1] is not None and not compare(subset, rows[b][1], reference)[0] for b in twins):
                relevant.append(dimension)
                break
    if any(name not in context.usable for name in names):
        return outcome(UNRESOLVED, "Not assessed: " + ", ".join(n for n in names if n not in context.usable) + " is unusable.", "not_assessed",
                       evidence_results=names, **base)
    agreeing = [i for i in range(len(rows)) if partial[i] and all(partial[i].get(name, {}).get("agrees") for name in names)]
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
    return outcome(UNRESOLVED, "These results fit both an accepted reading and a known pitfall (" + ", ".join(named) + ").", "ambiguous_variant",
                   pitfalls_possible=named, **extra)


def _finish(result, checks):
    computed = [row for row in checks.values() if row.get("decided_by") != JUDGE]
    result["checks"] = dict(sorted(checks.items()))
    result["computed_outcome"] = combine(computed)
    result["outcome"] = combine(list(checks.values()))
    result["unresolved_reasons"] = sorted({row["reason"] for row in checks.values() if row["state"] == UNRESOLVED})
    if "skill" in result:
        result["skill_valid_for_ranking"] = result["computed_outcome"] == PASS
    return result
