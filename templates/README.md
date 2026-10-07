# Templates are parameterised tasks assessed by the controller

A template is a task whose brief, inputs and answer key take parameters
such as region and time window. One template yields many instances. Templates
are assessed by the `assessment/` package, which implements
[the assessment format](../docs/assessment-format.md). The controller is the
trusted evaluator in `assessment/`; it launches the agent in a Docker sandbox,
holds the private references and runs the checks.

## A template folder holds these files

- `spec.yaml` — the assessment specification: mode, named results with their
  dimensions and error bounds, conventions labelled accepted or pitfall,
  invariants, probes, claims and interpretation checks. It has a
  `spec_version`.
- `brief.md` — the text given to the agent, with fill-in fields. It names every
  array, its dimensions and its unit. Briefs run to about 150 words.
- `conventions.md` — optional. A page that states the accepted conventions. It
  is handed to the agent only when a run asks for it with `--supply
  conventions`, which makes it a supplement that can be switched on and off.
- `reference.py` — the reference function and the controller hooks. This is the
  only science code a template needs.
- `reference_independent.py` — a second implementation that shares no code with
  the first.
- `instances.yaml` — the public development instances.
- `sources.json` — the identity and hashes of the frozen source data.
- `controls/` — a known-correct submission and deliberately incorrect ones, used
  to certify the spec.
- `certification.json` — the record of the last certification run.
- `rulings.yaml` — optional. A reviewer's rulings on answers that matched no
  listed reading, keyed by the hash of the answer.

## A submission holds these parts

The text every agent receives is [`assessment/envelope.md`](../assessment/envelope.md).

- `results.zarr` — every array the brief names, in a Zarr store of format
  version 3, each on named dimensions with a coordinate array of labels for
  every dimension. The controller matches arrays by dimension name and label.
- `answer.json` — single-number results, the agent's choices, its claims, its
  method entries where the brief asks for them, and the run command.
- The code the run command needs. The controller reruns it offline on changed
  data for the same task. The task's parameters may be written into the code.
- `report.md` — a short account of the work.

## How a tolerance is declared

A result's `tolerance` is an error bound, not a judgement.

- `{precision: float32, operations: n, magnitude: m}` gives the tolerance
  `2 * n * u * m`, where `u` is the unit roundoff of the precision. `n` is the
  number of rounded operations in the longest chain that produces the result,
  and `m` is the largest quantity that enters it. Two correct implementations
  cannot differ by more.
- `{exact: true}` requires equality, for whole numbers such as categories.
- The spec states in a comment where `n` and `m` come from.
- Certification checks `m` against the data: the largest reference value under
  an accepted reading must not exceed it. Certification also reports, for each
  pitfall, how many tolerances separate it from the accepted reading.

## `reference.py` must provide these hooks

- `prepare(private, source_dir)` — restore the private data from hash-checked
  source archives.
- `stage_inputs(private, params, destination)` — write exactly what the agent
  may see, including `instance.json`.
- `perturb_inputs(inputs, seed, kind)` — change the staged data in place, for
  the changed-data probe and the invariance probes. A good change makes each
  pitfall give different numbers from the accepted reading.
- `reference(inputs, params, conventions)` — product and process modes: the
  results for one instance under one combination of conventions, including the
  coordinate labels.
- `expected_coordinates(inputs, params)` and `score(results, params, private,
  split)` — outcome mode: the cases a forecast must cover, and its skill
  against the withheld observations.
- `candidate_instances()` — every instance the frozen data supports.
- `brief_fields(params)` — the values that fill the brief.
- `INVARIANTS`, `INVARIANCE_PROBES`, `expected_claims`, `independent`,
  `regression_checks` — the rules any valid answer obeys, the data changes that
  must leave part of the results unmoved, the claims that follow from a set of
  results, the second implementation, and any agreement checks against outside
  answers.

## These commands run, assess and certify a template

```sh
.venv/bin/python -m assessment templates
.venv/bin/python -m assessment prepare kenya-forecast-revision --source ../weather-skills-bench/fixtures
.venv/bin/python -m assessment instances kenya-forecast-revision
.venv/bin/python -m assessment brief kenya-forecast-revision service-area--weeks-1-2
.venv/bin/python -m assessment certify kenya-forecast-revision
.venv/bin/python -m assessment assess kenya-forecast-revision service-area--weeks-1-2 PATH/TO/SUBMISSION
.venv/bin/python -m assessment run kenya-forecast-revision service-area--weeks-1-2 --system kenya-revision-fixture
.venv/bin/python -m assessment run kenya-forecast-revision central--weeks-2-3 --system kenya-revision-fixture --supply conventions
.venv/bin/python -m assessment run kenya-forecast-revision north-west--weeks-3-4 --system kenya-revision-fixture --parent RUN_ID
.venv/bin/python -m assessment run weeks34-rainfall final-2015-2017--all-cells --system weeks34-level2-fixture --level 2
.venv/bin/python -m assessment runs
.venv/bin/python -m assessment reassess RUN_ID
.venv/bin/python -m assessment judge RUN_ID
.venv/bin/python -m assessment judge-calibration
.venv/bin/python -m assessment attempts kenya-forecast-revision
```

- `run` launches a system on an instance, assesses its submission and has the
  judge decide the questions no computation can settle. `--no-judge` leaves
  those unresolved.
- `--supply conventions` hands the agent the template's conventions sheet.
- `--parent RUN_ID` starts a second episode: the earlier run's submission is
  placed under `/work/prior`, and the agent may use it or not. The parent may be
  a run of another instance, another level or another template, by the same
  system.
- `reassess` assesses an existing run again under the current spec and code and
  keeps the earlier assessment. It refuses a run made under another spec
  version, whose agent answered a different contract.
- `judge` has the judge decide the open questions of a run's recorded
  assessment, and leaves the computed checks as recorded. It works on runs of
  any spec version.
- `judge-calibration` runs the pinned judge on its twelve cases with known
  answers and writes `assessment/judge-calibration.json`.
- `attempts` refreshes the fifth certification test from the agent runs on disk.

The judge is Claude Opus 5.5, called through the `claude` command line with no
tools and a fixed prompt. It sends the brief, the report, `answer.json`, the
submitted code and a summary of the arrays to Anthropic.

To run the Codex systems after the default command-line install has moved past
the verified version, name the verified binary and use the pinned system:

```sh
export CODEX_BINARY=$HOME/.codex/packages/standalone/releases/0.160.0-aarch64-apple-darwin/bin/codex
.venv/bin/python -m assessment run kenya-forecast-revision central--weeks-2-3 --system codex-luna-pinned
```

`certify` and `assess` run submitted code in the offline Docker runtime. The
`--local-trusted` flag runs it on the controller without isolation and is only
for the controller's own control submissions.

## Process-mode templates cite a standard

A process-mode spec names a standard and lists the steps it requires. The
standard's practices and checklist live in `standards/<standard>/`, so that one
checklist serves every template that names it. A test keeps each spec's steps
identical to the checklist's. The only standard so far,
`standards/wmo-objective-seasonal-forecasting/`, is a draft from a secondary
source and has not been reviewed.

## The data lives outside the repository

Private data stays under `var/private/templates/<template>/`, which Git
ignores. The tracked `sources.json` records the hash of every source object, so
`prepare` either reproduces the private data exactly or fails. A fresh checkout
needs the source archives named in `sources.json`.

## A run records its provenance

Each run lives in `var/template-runs/<run-id>/`. The controller writes
`controller/provenance.json`: input hashes, source identity, artifact hashes at
freeze, the system and its tooling files, the spec version and fingerprint,
the tool trace hash, the sandbox boundary, the tooling-use record (`substrate_record`), and the
parent run if any, the supplements handed to the agent, and, for a second
episode, how many commands named the earlier work. The agent writes none of it.
`assessment.json` holds every check with its outcome, the headline `outcome`,
and its two components `computed_outcome` and `judged_outcome`.
`controller/judgements/` holds the judge's raw replies under its identifier.

## Certification runs five tests

`certify` runs four automatic tests: the two reference implementations agree,
and every declared magnitude covers the data; known-correct submissions pass;
deliberately incorrect submissions are caught by the right check; and the
separability of every accepted–pitfall pair is measured, in tolerances, on the
submitted data and on the controller's changed data. The fifth test reads the agent runs on disk: it needs at least two
attempts assessed under the current fingerprint, with no answer left
unclassified. `certified` stays false until a domain scientist approves the
task. A test in `tests/test_assessment_format.py` fails when the spec, the
reference or a module that decides outcomes changes without a new
certification.

## Three templates are certified today

| Template | Spec version | Task-set entry | Mode | Certification |
| --- | --- | --- | --- | --- |
| `kenya-forecast-revision` | 2 | 4 | Product | All five tests pass; 4 attempts by one cheap model under this version |
| `weeks34-rainfall` | 3 | 15 | Outcome, Levels 1 and 2 | All five tests pass; 3 attempts by one cheap model under this version |
| `seasonal-rainfall-calibration` | 3 | 11 | Process | All five tests pass; 4 attempts by one cheap model under this version; three proposed rulings; the checklist is a draft |

The judge passed its 12 control cases. Twenty-five earlier attempts were made
under the first contract; their recorded assessments stand, with the judge's
verdicts added.

No template is approved by a domain scientist.

## The sandbox boundary keeps model-generated commands off the controller host

The harness's adapter (`systems/<id>/adapter.py`) is trusted integration code.
It calls the model or agent library and translates its tool requests to the
protocol below. Model-generated commands go through the protocol and run in the
offline Docker runtime, never on the controller host. An agent command line
that executes its own tools needs an integration that routes them into the
runtime container; pointing a host-executing command line at this repository
does not establish the benchmark's information boundary.

Adapters run in their snapshotted directory. `{python}` expands to the
controller interpreter; `{driver}` expands to that directory. `driver.env` lists
environment variable names to pass to the controller; do not store secret
values in the system definition. Model credentials stay on the controller and
are never mounted into the runtime container.

## The adapter protocol is JSON lines over standard input and output

The controller writes one JSON `start` request to the adapter's stdin. It
contains the brief, the envelope, the budgets, the runtime paths, the tooling
notes and an inventory of the retained earlier submission. The adapter writes
JSON lines to stdout; stdout is reserved for the protocol, and diagnostics go to
stderr.

```json
{"type":"execute","id":"step-1","command":"python workflow.py","timeout_seconds":60}
```

The controller executes the command in `/work` in the isolated container and
replies:

```json
{"type":"tool_result","id":"step-1","exit_code":0,"stdout":"...","stderr":"...","remaining_seconds":300}
```

Request and result pairs continue, then the adapter emits cumulative usage when
it is available and a final event:

```json
{"type":"usage","usage":{"input_tokens":1234,"output_tokens":567,"usd":0.02,"calls":3}}
{"type":"final","message":"Submission written to /work/submission"}
```

Missing usage is `unknown`, not zero. A custom adapter's usage is labelled
self-reported; the built-in provider driver records controller-observed usage.
The controller enforces the wall-clock and tool limits; a custom adapter must
enforce its own provider spending limit.

## The tooling-use record says whether the agent touched the tooling

A mounted tooling image measures availability; a tooling comparison also needs
to know whether the agent used it. The controller derives this from the run's
command log (`assessment/substrate_use.py`, kept under its original name; its
output is the tooling-use record) with no model call and no change to any
check. Each command that reached the runtime is classed by its strongest use of
a path under the tooling mount: `ran` (a script executed directly or through
`python`, `bash`, `sh`, `Rscript` or `uv run`), `read` (any other reference,
such as `cat` or `sed`), `listed` (`ls`, `find`, `tree`) or `entered` (`cd`).
Runs are split into `ran_ok` and `ran_failed` by exit status; the status
belongs to the whole command, so a chained or piped command is attributed as
one. Tool calls the built-in driver refused as truncated or invalid were never
executed and are not counted. Log lines that cannot be parsed are skipped and
counted in `unreadable_log_lines`. The record also gives the first step that
touched the tooling and the paths named.

This is a lower bound from command text. Relative paths after a `cd` into the
mount, shell variables, and workflow code that opens tooling files itself are
not attributed. Tooling installed as a library in the runtime image, rather
than mounted, is not measured. `unknown` means the run has no execution log;
`none` means it ran commands but none named the tooling. Use is diagnostic
evidence: compare assigned tooling images as the primary analysis, not only the
runs that used the tooling.

## A second episode retains the earlier submission and nothing else

A run with `--parent RUN_ID` carries the agent's earlier submission under
`/work/prior`, never the assessment, the private references, the verification
observations or the judge's verdicts. A plain run receives nothing. To separate
reuse from difficulty, counterbalance instance order and compare the same
instance at the same position.

## Source data is frozen once and never replaced in place

Start from a published outlook, a centre's replication procedure or a paper's
analysis. Record the source version and the exact method or result to
reproduce, and state the region, period, lead time, variable and resolution.
Distinguish the source's requirements from the template author's choices, and
state each open convention in the brief with its accepted reading in the spec.
For a forecast template, freeze the data cutoff before the observations
resolve, and keep later observations and the private reference outside the
agent's workspace.

`prepare` must fail if an existing frozen input differs from the source. Create
a new reviewed spec version rather than silently replacing evidence, and keep
the earlier references when a reference function is corrected; assessments keep
the fingerprint they were made under.

Useful controls include changed coordinates, wrong units, shifted periods, wrong
category labels, changed missing masks, leaked verification data and a run
command that cannot regenerate the result. Choose the controls that matter for
the method, rather than repeating the implementation as checks. Numerical
agreement alone can reward a copied output; a probe that reruns the submitted
code on changed data catches it.

## The runtime image is built with Docker

```sh
docker build -f runtime/Dockerfile -t agent-weather-bench-runtime:local .
docker image inspect agent-weather-bench-runtime:local --format '{{.Id}}'
```

The base defaults to `python:3.13-slim`. For a fixed base image, add
`--build-arg BASE=python@sha256:YOUR_BASE_DIGEST`. The system definition names
the image a system runs in; `certify` and `assess` use the offline runtime.
