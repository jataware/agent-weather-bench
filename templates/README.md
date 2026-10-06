# Task templates

A task template is a task whose brief, inputs and answer key take parameters
such as region and time window. One template yields many instances. Templates
are assessed by the `assessment/` package, which implements
[the assessment format](../docs/assessment-format.md). The ten packaged tasks in
`tasks/` are still assessed by the older `weatherbench` evaluator; each moves
here when it is converted.

## What a template folder holds

- `spec.yaml` — the assessment specification: mode, named results with
  tolerances, conventions labelled accepted or pitfall, invariants, probes,
  claims and interpretation obligations. It has a `spec_version`.
- `brief.md` — the text given to the agent, with fill-in fields. The cap is
  about 150 words.
- `reference.py` — the reference function and the controller hooks. This is the
  only science code a template needs.
- `reference_independent.py` — a second implementation that shares no code with
  the first.
- `instances.yaml` — the public development instances.
- `sources.json` — the identity and hashes of the frozen source data.
- `controls/` — a known-correct solution and deliberately incorrect ones, used
  to certify the spec.
- `certification.json` — the record of the last certification run.

## The hooks `reference.py` must provide

- `prepare(private, source_dir)` — restore the private data from hash-checked
  source archives.
- `stage_inputs(private, params, destination)` — write exactly what the agent
  may see, including `instance.json`.
- `perturb_inputs(inputs, seed)` — change the staged data in place, for the
  changed-data probe.
- `reference(inputs, params, conventions)` — the results for one instance under
  one combination of conventions.
- `candidate_instances()` — every instance the frozen data supports.
- `brief_fields(params)` — the values that fill the brief.
- `INVARIANTS`, `expected_claims`, `independent`, `regression_checks` — the
  rules any valid answer obeys, the claims that follow from a set of results,
  the second implementation, and any agreement checks against outside answers.

## Commands

```sh
.venv/bin/python -m assessment templates
.venv/bin/python -m assessment prepare kenya-forecast-revision --source ../weather-skills-bench/fixtures
.venv/bin/python -m assessment instances kenya-forecast-revision
.venv/bin/python -m assessment brief kenya-forecast-revision service-area--weeks-1-2
.venv/bin/python -m assessment certify kenya-forecast-revision
.venv/bin/python -m assessment assess kenya-forecast-revision service-area--weeks-1-2 PATH/TO/SUBMISSION
.venv/bin/python -m assessment run kenya-forecast-revision service-area--weeks-1-2 --system kenya-revision-fixture
.venv/bin/python -m assessment runs
```

`certify` and `assess` run submitted code in the offline Docker runtime. The
`--local-trusted` flag runs it on the controller without isolation and is only
for the controller's own control solutions.

## Where the data lives

Private data stays under `var/private/templates/<template>/`, which Git
ignores. The tracked `sources.json` records the hash of every source object, so
`prepare` either reproduces the private data exactly or fails. A fresh checkout
needs the source archives named in `sources.json`.

## What a run records

Each run lives in `var/template-runs/<run-id>/`. The controller writes
`controller/provenance.json`: input hashes, source identity, artifact hashes at
freeze, the system and its substrate files, the spec version and fingerprint,
the tool trace hash, the sandbox boundary, the substrate-use record, and the
parent run if any. The agent writes none of it. `assessment.json` holds every
check with its outcome.

## Certification

`certify` runs four automatic tests: the two reference implementations agree;
known-correct solutions pass; deliberately incorrect solutions are caught by
the right check; and the separability of every accepted–pitfall pair is
measured. The fifth test, agent attempts with every unknown answer ruled on,
needs model runs and is recorded as not run. A test in
`tests/test_assessment_format.py` fails when the spec, the reference or the
assessment code changes without a new certification.

## Current templates

| Template | Task-set row | Mode | Certification |
| --- | --- | --- | --- |
| `kenya-forecast-revision` | 4 | Product | Four automatic tests pass; agent attempts not run |
