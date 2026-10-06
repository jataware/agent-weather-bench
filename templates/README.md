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
- `reference(inputs, params, conventions)` — product mode only: the results for
  one instance under one combination of conventions.
- `expected_coordinates(inputs, params)` and `score(results, params, private,
  split)` — outcome mode only: the cases a forecast must cover, and its skill
  against the withheld observations.
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
.venv/bin/python -m assessment run weeks34-rainfall final-2015-2017--all-cells --system weeks34-level2-fixture --level 2
.venv/bin/python -m assessment runs
.venv/bin/python -m assessment reassess RUN_ID
.venv/bin/python -m assessment attempts kenya-forecast-revision
```

`reassess` assesses an existing run again under the current spec and code and
keeps the earlier assessment. `attempts` refreshes the fifth certification test
from the agent runs on disk.

To run the Codex systems after the default command-line install has moved past
the verified version, name the verified binary and use the pinned system:

```sh
export CODEX_BINARY=$HOME/.codex/packages/standalone/releases/0.160.0-aarch64-apple-darwin/bin/codex
.venv/bin/python -m assessment run kenya-forecast-revision central--weeks-2-3 --system codex-luna-pinned
```

`certify` and `assess` run submitted code in the offline Docker runtime. The
`--local-trusted` flag runs it on the controller without isolation and is only
for the controller's own control solutions.

## Standards for process-mode templates

A process-mode spec names a standard and lists the steps it requires. The
standard's practices and checklist live in `standards/<standard>/`, so that one
checklist serves every template that names it. A test keeps each spec's steps
identical to the checklist's. The only standard so far,
`standards/wmo-objective-seasonal-forecasting/`, is a draft from a secondary
source and has not been reviewed.

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
measured. The fifth test reads the agent runs on disk: it needs at least two
attempts assessed under the current fingerprint, with no answer left
unclassified. `certified` stays false until a domain scientist approves the
task. A test in `tests/test_assessment_format.py` fails when the spec, the
reference or a module that decides outcomes changes without a new
certification.

## Current templates

| Template | Task-set row | Mode | Certification |
| --- | --- | --- | --- |
| `kenya-forecast-revision` | 4 | Product | All five tests pass; two attempts by one cheap model |
| `weeks34-rainfall` | 15 | Outcome, Levels 1 and 2 | All five tests pass; three attempts by one cheap model |
| `seasonal-rainfall-calibration` | 11 | Process | All five tests pass; two attempts by one cheap model; the checklist is a draft |

No template is approved by a domain scientist.
