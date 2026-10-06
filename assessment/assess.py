"""Assessment of one submission against one instance of a template.

Product mode checks the requested quantity under every accepted reading of the
brief. Outcome mode has no reference answer: it checks that the submission is a
valid forecast and scores it against withheld observations.
"""
import json
import shutil
from pathlib import Path

from .compare import EnvelopeError, align, compare, normalise
from .execute import valid_argv
from .judge import interpret
from .outcomes import FAIL, PASS, UNRESOLVED, combine, outcome
from .variant import consistent, decide, discriminating_instance, summarise, table

TEXT_SUFFIXES = (".md", ".txt", ".json", ".py", ".sh", ".R", ".jl", ".yaml", ".yml")


def read_envelope(template, submission):
    """(answer, results, argv) or an EnvelopeError naming what is missing."""
    path = Path(submission) / "answer.json"
    if not path.is_file():
        raise EnvelopeError("The submission has no answer.json")
    try:
        answer = json.loads(path.read_text())
    except ValueError:
        raise EnvelopeError("answer.json is not valid JSON") from None
    if not isinstance(answer, dict):
        raise EnvelopeError("answer.json must be an object")
    results = normalise(template.spec["results"], answer.get("results"))
    argv = (answer.get("run") or {}).get("argv") if isinstance(answer.get("run"), dict) else None
    if not valid_argv(argv):
        raise EnvelopeError("answer.json needs run.argv containing {input_dir} and {output_dir}")
    return answer, results, argv


def _rerun(template, executor, submission, inputs, argv, scratch):
    """Run the declared command; return (results, record, problem outcome or None)."""
    record = executor.run(submission, inputs, argv, scratch)
    slim = {key: record[key] for key in ("exit_code", "executor") if key in record}
    if record.get("infrastructure_unavailable"):
        return None, slim, outcome(UNRESOLVED, "The controller could not run the command: " + record.get("stderr", "")[:300], "infrastructure", run=slim)
    if record["exit_code"] != 0 or record.get("answer") is None:
        slim["stderr"] = record.get("stderr", "")[-600:]
        return None, slim, outcome(FAIL, "The run command did not produce an answer.json.", run=slim)
    try:
        return normalise(template.spec["results"], record["answer"].get("results") if isinstance(record["answer"], dict) else None), slim, None
    except EnvelopeError as error:
        return None, slim, outcome(FAIL, "The run command's answer is unusable: " + str(error), run=slim)


def _follows_inputs(template, name, submitted, hits, rerun, rows, slim):
    """Shared verdict for the two changed-input probes; returns (outcome, consistent set on the changed inputs)."""
    if rerun is None:
        return None, []
    unchanged = compare(template.spec["results"], rerun, submitted)[0]
    local, _ = consistent(template, rerun, rows)
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


def _texts(submission, limit=200000):
    files = {}
    for path in sorted(Path(submission).rglob("*")):
        if path.is_file() and path.suffix in TEXT_SUFFIXES and path.stat().st_size <= limit:
            files[str(path.relative_to(submission))] = path.read_text(errors="replace")
    return files


def assess(template, params, submission, executor, scratch, level=1, feedback=None, judge_backend=None, seed=20261006):
    """`feedback` is the controller's public summary of development-score requests, for Level 2."""
    spec, submission, scratch = template.spec, Path(submission), Path(scratch)
    scratch.mkdir(parents=True, exist_ok=False)
    if level == 2 and "level2" not in spec:
        raise ValueError("This template has no Level 2")
    result = {"schema_version": 1, "template": template.name, "spec_version": spec["spec_version"], "fingerprint": template.fingerprint(),
              "mode": spec["mode"], "level": level, "instance": params, "executor": executor.name, "seed": seed}
    claims = {**spec.get("claims", {}), **(spec["level2"].get("claims", {}) if level == 2 else {})}
    planned = ((["variant"] if spec["mode"] != "outcome" else ["coverage"]) + [f"invariant.{n}" for n in spec.get("invariants", [])]
               + [f"probe.{n}" for n in spec.get("probes", [])] + [f"claim.{n}" for n in claims] + (["feedback.limit"] if level == 2 else []))
    checks = {}

    def stop(check, message):
        """A submission with no usable answer: fail here, and guess at nothing else."""
        checks[check] = outcome(FAIL, message)
        for name in planned:
            checks.setdefault(name, outcome(UNRESOLVED, "Not assessed: the submission has no usable answer.", "not_assessed"))
        checks.update({f"interpretation.{k}": v for k, v in interpret(spec.get("interpretation", []), _texts(submission), judge_backend).items()})
        return _finish(result, checks)

    try:
        answer, results, argv = read_envelope(template, submission)
        checks["envelope"] = outcome(PASS, "answer.json holds the named results and a run command.")
    except EnvelopeError as error:
        return stop("envelope", str(error))
    work = (_outcome_mode if spec["mode"] == "outcome" else _product_mode)
    finished = work(template, params, submission, executor, scratch, seed, result, checks, answer, results, argv, claims, level, feedback, stop)
    if finished is not None:
        return finished
    checks.update({f"interpretation.{k}": v for k, v in interpret(spec.get("interpretation", []), _texts(submission), judge_backend).items()})
    for folder in scratch.glob("probe-*/stage"):
        shutil.rmtree(folder, ignore_errors=True)
    return _finish(result, checks)


def _product_mode(template, params, submission, executor, scratch, seed, result, checks, answer, results, argv, claims, level, feedback, stop):
    spec, hooks = template.spec, template.hooks

    original = scratch / "inputs-original"
    hooks.stage_inputs(template.private, params, original)
    rows = table(template, original, params)
    hits, partial = consistent(template, results, rows)
    first = decide(template, rows, hits, partial)

    for name in spec.get("invariants", []):
        ok, detail = hooks.INVARIANTS[name](results, params, original)
        checks[f"invariant.{name}"] = outcome(PASS if ok else FAIL, detail)

    expected = hooks.expected_claims(results, params) if spec.get("claims") else {}
    stated = answer.get("claims") if isinstance(answer.get("claims"), dict) else {}
    for name in spec.get("claims", {}):
        want, got = expected[name], stated.get(name)
        if got is None:
            checks[f"claim.{name}"] = outcome(UNRESOLVED, "The answer does not state this claim.", "missing_evidence")
        elif not isinstance(got, list) or len(got) != len(want):
            checks[f"claim.{name}"] = outcome(FAIL, f"The claim must have {len(want)} entries, one per period.", stated=got)
        else:
            wrong = [i for i, (value, allowed) in enumerate(zip(got, want)) if value not in allowed]
            checks[f"claim.{name}"] = outcome(FAIL if wrong else PASS, "The stated claim contradicts the submission's own numbers." if wrong else
                                              "The stated claim follows from the submission's own numbers.", stated=got,
                                              **({"contradicted_entries": wrong} if wrong else {}))

    narrowed, probes_passed = list(hits), True
    if "replay" in spec.get("probes", []):
        rerun, slim, problem = _rerun(template, executor, submission, original, argv, scratch / "probe-replay")
        if problem is None:
            same = compare(spec["results"], rerun, results)[0]
            problem = outcome(PASS if same else FAIL, "The run command regenerates the submitted results." if same else
                              "The run command produces results that differ from the submitted answer.", run=slim)
        checks["probe.replay"] = problem
        probes_passed &= problem["state"] == PASS
    if "changed_data" in spec.get("probes", []):
        changed = scratch / "inputs-changed-data"
        hooks.stage_inputs(template.private, params, changed)
        hooks.perturb_inputs(changed, seed)
        changed_rows = table(template, changed, params)
        if hits and any(rows[i][1] is not None and changed_rows[i][1] is not None and compare(spec["results"], changed_rows[i][1], rows[i][1])[0] for i in hits):
            checks["probe.changed_data"] = outcome(UNRESOLVED, "The controller's data change did not alter the reference, so the probe cannot decide.", "infrastructure")
            probes_passed = False
        else:
            rerun, slim, problem = _rerun(template, executor, submission, changed, argv, scratch / "probe-changed-data")
            verdict, shared = (problem, []) if problem else _follows_inputs(template, "changed data", results, hits, rerun, changed_rows, slim)
            checks["probe.changed_data"] = verdict
            probes_passed &= verdict["state"] == PASS
            if verdict["state"] == PASS:
                narrowed = [i for i in narrowed if i in shared]
    if "changed_instance" in spec.get("probes", []):
        shared_inputs = getattr(hooks, "INPUTS_SHARED_ACROSS_INSTANCES", False)
        def inputs_for(candidate):
            if shared_inputs:
                return original
            folder = scratch / "candidates" / candidate["id"]
            if not folder.exists():
                hooks.stage_inputs(template.private, candidate, folder)
            return folder
        other, separates = discriminating_instance(template, inputs_for, params, rows, narrowed)
        staged = scratch / "inputs-changed-instance"
        hooks.stage_inputs(template.private, other, staged)
        other_rows = table(template, staged, other)
        rerun, slim, problem = _rerun(template, executor, submission, staged, argv, scratch / "probe-changed-instance")
        verdict, shared = (problem, []) if problem else _follows_inputs(template, f"instance {other['id']}", results, narrowed or hits, rerun, other_rows, slim)
        verdict["probe_instance"], verdict["chosen_to_separate_accepted_from_pitfall"] = other["id"], bool(separates)
        checks["probe.changed_instance"] = verdict
        probes_passed &= verdict["state"] == PASS
        if verdict["state"] == PASS:
            narrowed = [i for i in narrowed if i in shared]

    final = decide(template, rows, narrowed, partial) if hits else first
    if first.get("reason") == "ambiguous_variant" or final.get("reason") == "ambiguous_variant":
        final["first_match"] = first["consistent_with"]
        if final["state"] == UNRESOLVED and spec["mode"] == "product" and probes_passed:
            # The delivered product is correct for this instance; the method stays undetermined.
            final = outcome(PASS, "The product is correct on this instance. No probe separated the accepted reading from the pitfall, so the method is undetermined.",
                            "ambiguous_variant", consistent_with=final["consistent_with"], pitfalls_possible=final["pitfalls_possible"],
                            first_match=first["consistent_with"])
    checks["variant"] = final
    result["matched_conventions"] = summarise(template, rows, narrowed) if narrowed else None
    result["first_match_conventions"] = summarise(template, rows, hits) if hits else None

    declared = answer.get("choices") if isinstance(answer.get("choices"), dict) else {}
    public = spec.get("public_conventions", [])
    result["declared_choices"] = {"declared": declared, "public_conventions": public,
                                  "disagreements": [name for name in public if narrowed and name in declared and declared[name] not in result["matched_conventions"][name]],
                                  "note": "A disagreement is evidence for the interpretation check, not proof."}
    return None


def _valid_forecast(template, raw_results, inputs, params):
    """(aligned results, list of problems) for a forecast with no reference answer."""
    try:
        aligned = align(template.spec["results"], raw_results, template.hooks.expected_coordinates(inputs, params))
    except EnvelopeError as error:
        return None, ["coverage: " + str(error)]
    problems = []
    for name in template.spec.get("invariants", []):
        ok, detail = template.hooks.INVARIANTS[name](aligned, params, inputs)
        if not ok:
            problems.append(f"{name}: {detail}")
    return aligned, problems


def _outcome_mode(template, params, submission, executor, scratch, seed, result, checks, answer, results, argv, claims, level, feedback, stop):
    """Validity gate and skill. Any method is acceptable; only invalid or leaking forecasts fail."""
    spec, hooks = template.spec, template.hooks
    original = scratch / "inputs-original"
    hooks.stage_inputs(template.private, params, original)
    try:
        forecast = align(spec["results"], results, hooks.expected_coordinates(original, params))
        checks["coverage"] = outcome(PASS, "The forecast covers exactly the required cases, each labelled with its own issue and cell.")
    except EnvelopeError as error:
        return stop("coverage", "The forecast does not cover exactly the required cases: " + str(error))
    for name in spec.get("invariants", []):
        ok, detail = hooks.INVARIANTS[name](forecast, params, original)
        checks[f"invariant.{name}"] = outcome(PASS if ok else FAIL, detail)

    def rerun_on(label, prepare=None, instance=params):
        folder = scratch / f"inputs-{label}"
        hooks.stage_inputs(template.private, instance, folder)
        if prepare:
            prepare(folder)
        produced, slim, problem = _rerun(template, executor, submission, folder, argv, scratch / f"probe-{label}")
        return folder, produced, slim, problem

    probes = spec.get("probes", [])
    if "replay" in probes:
        _, produced, slim, problem = rerun_on("replay")
        if problem is None:
            same = compare(spec["results"], produced, forecast)[0]
            problem = outcome(PASS if same else FAIL, "The run command regenerates the submitted forecast." if same else
                              "The run command produces a forecast that differs from the submitted one.", run=slim)
        checks["probe.replay"] = problem
    if "responds_to_inputs" in probes:
        moved, records, broken = [], {}, None
        for kind in hooks.RESPONSE_PERTURBATIONS:
            _, produced, slim, problem = rerun_on(f"changed-{kind}", lambda folder, kind=kind: hooks.perturb_inputs(folder, seed, kind))
            records[kind] = slim
            if problem is not None:
                broken = problem
                break
            if not compare(spec["results"], produced, forecast)[0]:
                moved.append(kind)
        checks["probe.responds_to_inputs"] = broken or outcome(
            PASS if moved else FAIL, ("The forecast changes when these inputs change: " + ", ".join(moved) + ".") if moved else
            "The forecast does not change when the training observations or the model forecasts change, so it does not come from the supplied data.",
            responds_to=moved, runs=records)
    if "no_future_information" in probes:
        folder, produced, slim, problem = rerun_on("changed-later-features", lambda folder: hooks.perturb_inputs(folder, seed, "features_after_cut"))
        if problem is None:
            aligned, problems = _valid_forecast(template, produced, folder, params)
            if aligned is None:
                problem = outcome(FAIL, "With later features changed, the forecast no longer covers the required cases.", run=slim)
            else:
                same = compare(spec["results"], hooks.before_cut(aligned, folder, params), hooks.before_cut(forecast, folder, params))[0]
                problem = outcome(PASS if same else FAIL, "Forecasts issued before the cut date do not move when later model forecasts change." if same else
                                  "Forecasts issued before the cut date move when later model forecasts change, so they use information from after their issue time.",
                                  run=slim, cut_date=str(hooks.cut_date(folder))[:10])
        checks["probe.no_future_information"] = problem
    if "changed_instance" in probes:
        others = [c for c in hooks.candidate_instances() if c["id"] != params["id"]]
        other = max(others, key=lambda c: sum(c[k] != params[k] for k in params if k != "id"))
        folder, produced, slim, problem = rerun_on("changed-instance", instance=other)
        if problem is None:
            aligned, problems = _valid_forecast(template, produced, folder, other)
            problem = outcome(FAIL if problems else PASS, ("On another instance the code does not produce a valid forecast: " + "; ".join(problems)) if problems
                              else "On another instance the code produces a valid forecast.", run=slim)
            if aligned is not None and not problems:
                problem["skill_on_probe_instance"] = hooks.score(aligned, other, template.private)
        problem["probe_instance"] = other["id"]
        checks["probe.changed_instance"] = problem

    score_spec = spec.get("skill", {})
    result["skill"] = {split: hooks.score(forecast, params, template.private, split) for split in score_spec.get("splits", ["final"])}
    stated = answer.get("claims") if isinstance(answer.get("claims"), dict) else {}
    for name, row in claims.items():
        if name not in stated:
            checks[f"claim.{name}"] = outcome(UNRESOLVED, "The answer does not state this claim.", "missing_evidence")
        elif stated[name] is None:
            checks[f"claim.{name}"] = outcome(PASS, "Stated as not measured.", stated=None)
        else:
            actual = result["skill"][row["split"]][row["metric"]] if row["split"] in result["skill"] else hooks.score(forecast, params, template.private, row["split"])[row["metric"]]
            ok = isinstance(stated[name], (int, float)) and not isinstance(stated[name], bool) and abs(stated[name] - actual) <= row["atol"]
            checks[f"claim.{name}"] = outcome(PASS if ok else FAIL, "The stated value equals the controller's score of the submitted forecast." if ok else
                                              "The stated value differs from the controller's score of the submitted forecast.",
                                              stated=stated[name], **({} if ok else {"controller_value": actual}))
    if level == 2:
        limit = spec["level2"]["feedback"]["max_submissions"]
        if not isinstance(feedback, dict) or not isinstance(feedback.get("requests"), list):
            checks["feedback.limit"] = outcome(UNRESOLVED, "No trusted record of development-score requests is available.", "missing_evidence")
        else:
            used = len(feedback["requests"])
            checks["feedback.limit"] = outcome(PASS if used <= limit else FAIL, f"{used} of {limit} development-score requests were used.",
                                               requests=used, limit=limit, denied=feedback.get("limit_denials", 0))
            result["feedback"] = feedback
    return None


def _finish(result, checks):
    computed = [row for name, row in checks.items() if not name.startswith("interpretation.")]
    result["checks"] = dict(sorted(checks.items()))
    result["computed_outcome"] = combine(computed)
    result["outcome"] = combine(list(checks.values()))
    result["unresolved_reasons"] = sorted({row["reason"] for row in checks.values() if row["state"] == UNRESOLVED})
    if "skill" in result:
        result["skill_valid_for_ranking"] = result["computed_outcome"] == PASS
    return result
