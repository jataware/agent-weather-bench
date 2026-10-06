"""Level 1 assessment of one submission against one instance of a template."""
import json
import shutil
from pathlib import Path

from .compare import EnvelopeError, compare, normalise
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


def assess(template, params, submission, executor, scratch, judge_backend=None, seed=20261006):
    spec, hooks, submission, scratch = template.spec, template.hooks, Path(submission), Path(scratch)
    scratch.mkdir(parents=True, exist_ok=False)
    result = {"schema_version": 1, "template": template.name, "spec_version": spec["spec_version"], "fingerprint": template.fingerprint(),
              "mode": spec["mode"], "level": 1, "instance": params, "executor": executor.name, "seed": seed}
    checks = {}
    planned = (["variant"] + [f"invariant.{n}" for n in spec.get("invariants", [])] + [f"probe.{n}" for n in spec.get("probes", [])]
               + [f"claim.{n}" for n in spec.get("claims", {})])
    try:
        answer, results, argv = read_envelope(template, submission)
        checks["envelope"] = outcome(PASS, "answer.json holds the named results and a run command.")
    except EnvelopeError as error:
        checks["envelope"] = outcome(FAIL, str(error))
        for name in planned:
            checks[name] = outcome(UNRESOLVED, "Not assessed: the submission has no usable answer.", "not_assessed")
        checks.update({f"interpretation.{k}": v for k, v in interpret(spec.get("interpretation", []), _texts(submission), judge_backend).items()})
        return _finish(result, checks)

    original = scratch / "inputs-original"
    hooks.stage_inputs(template.private, params, original)
    rows = table(template, original, params)
    hits, partial = consistent(template, results, rows)
    first = decide(template, rows, hits, partial)

    for name in spec.get("invariants", []):
        ok, detail = hooks.INVARIANTS[name](results, params)
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
    checks.update({f"interpretation.{k}": v for k, v in interpret(spec.get("interpretation", []), _texts(submission), judge_backend).items()})
    for folder in scratch.glob("probe-*/stage"):
        shutil.rmtree(folder, ignore_errors=True)
    return _finish(result, checks)


def _finish(result, checks):
    computed = [row for name, row in checks.items() if not name.startswith("interpretation.")]
    result["checks"] = dict(sorted(checks.items()))
    result["computed_outcome"] = combine(computed)
    result["outcome"] = combine(list(checks.values()))
    result["unresolved_reasons"] = sorted({row["reason"] for row in checks.values() if row["state"] == UNRESOLVED})
    return result
