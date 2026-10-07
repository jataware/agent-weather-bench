# Running and extending the benchmark

The current entry point is `./bench` (equivalently `.venv/bin/python -m weatherbench`).
The repository separates current tasks/systems/judging from the historical pilot.
Docker is required for scientific execution and offline replay. The wrapper uses
the existing local `.venv`; a fresh checkout creates a Python 3.12+ virtual
environment and installs `pip install -r requirements-controller.lock`.

## Add a system

```sh
./bench systems init my-agent
./bench systems validate my-agent
```

Edit `systems/my-agent/system.yaml` and its adapter. Set a local runtime image
by its full `sha256:...` content ID, resource/time/tool limits, and substrate paths.
Keep skills, workflow helpers, retrieval indexes or domain notes inside that
system directory and list them in `substrate.paths`. The harness snapshots and
hashes the listed files, mounts them read-only at `/substrate`, and includes
`substrate.instructions` in the agent's starting request. An image can contain
the libraries/tools the system uses; its content ID is recorded on every run.
The scaffold defaults to the locally built scientific image. On another
machine, build your scientific image, obtain its ID with
`docker image inspect YOUR_IMAGE --format '{{.Id}}'`, and pass that full ID to
`systems init NAME --image sha256:...`. The current scientific image recipe is `runtime/Dockerfile`, with pinned Python packages in `runtime/requirements.lock`. Follow the complete build and data bundle instructions in [internal setup](internal-setup.md). Archived recipes describe the historical pilot.
The harness checks for the exact local image and never silently pulls a tag.

The controller adapter is trusted integration code. It calls your model or agent
library and translates its tool requests to the protocol below. **Model-generated
scientific commands must go through the protocol, never execute on the controller
host.** An agent CLI that executes its own tools needs an integration that routes
them into the harness container; pointing a host-executing CLI at this repository
does not establish the benchmark's information boundary.

Adapters run in their snapshotted directory. `{python}` expands to the controller
interpreter; `{driver}` expands to that directory. `driver.env` lists environment
variable names to pass to the trusted controller; do not store secret values in
the system definition. Model credentials stay on the controller and are never
mounted into the scientific tool container.

## Adapter protocol

The harness writes one JSON `start` request to adapter stdin. It contains the
task prompt, shared artifact contracts, budgets, runtime paths, substrate guidance
and an inventory of retained prior artifacts. The adapter writes JSON lines to
stdout; stdout is reserved for the protocol, and diagnostics go to stderr.

```json
{"type":"execute","id":"step-1","command":"python workflow.py","timeout_seconds":60}
```

The harness executes the command in `/work` in the isolated container and replies:

```json
{"type":"tool_result","id":"step-1","exit_code":0,"stdout":"...","stderr":"...","remaining_seconds":300}
```

Continue request/result pairs, then emit cumulative usage when available and a
final event:

```json
{"type":"usage","usage":{"input_tokens":1234,"output_tokens":567,"usd":0.02,"calls":3}}
{"type":"final","message":"Deliverables written to /work/submission"}
```

Missing usage is `unknown`, not zero. Custom-adapter usage is labelled self-reported;
the built-in provider driver records controller-observed usage with pinned
accounting. The harness enforces wall/tool limits; arbitrary custom adapters must
enforce their own provider spending limits. No claim is made that a generic
adapter's self-reported dollars are a reconciled invoice.

`systems/example/adapter.py` is a minimal scaffold. The deterministic
`systems/harness-fixture/` exercises ACMAD processing and replay with no model calls;
it is explicitly excluded from agent capability claims.

## Built-in model driver

Alternatively, replace `driver` with the following structure, using the model and
accounting rates selected for your experiment:

```yaml
driver:
  kind: anthropic
  model: YOUR_FIXED_MODEL_ID
  api_key_env: ANTHROPIC_API_KEY
  input_usd_per_million: YOUR_INPUT_RATE
  output_usd_per_million: YOUR_OUTPUT_RATE
  max_usd: 5
  max_total_tokens: 200000
  max_output_tokens: 8192
  max_turns: 60
```

It uses the provider Messages API with token-count-based cost reservations, runs
only the harness's isolated `execute` tool and rejects truncated tool calls. Other
providers or agent frameworks use the command adapter contract; they do not need
to imitate this model loop.

## Run, import, assess and inspect

```sh
./bench tasks list
./bench run acmad-objective --system my-agent
./bench runs list
./bench runs show RUN_ID
./bench runs report
```

The default judge is `auto-v1`. Supply `ANTHROPIC_API_KEY` in the controller
environment for native judging. `--judge none` performs numeric checks and offline
replay with no judge model call; expert evidence remains pending. For a complete
zero-model-call harness check:

```sh
./bench run acmad-objective --system harness-fixture --judge none
```

To assess artifacts produced elsewhere, use `ingest`:

```sh
./bench ingest acmad-objective --system my-agent --submission /path/to/output
./bench assess RUN_ID
./bench judge packet RUN_ID
```

Imported artifacts receive the same numerical/replay/judge pipeline, but their
original execution integrity remains unresolved. They cannot be labelled complete
merely because their arrays match. The harness never runs an imported script on
the host; declared commands run only in a constrained offline container.

## Standard run layout

```text
var/runs/<run-id>/
  run.json, system.yaml, system.json, task-manifest.json
  task/                    pinned public task and artifact contracts
  system/                  pinned adapter and substrate files
  inputs/                  controller-prepared allowed inputs, mounted read-only
  work/submission/         live agent deliverables
  work/state/, work/prior/  agent-owned reusable artifacts
  frozen/, artifacts.json  exact submitted artifact snapshot and hashes
  retained/                reusable state; assessment/feedback never enters it
  logs/                    protocol/model/tool events and adapter diagnostics
  controller/              private boundary and assessment evidence
  assessment.json          convenience pointer to the latest selected assessment
```

Each assessment stores static checks, replay/prediction outputs, the judge packet,
raw response, validated ratings, model usage and a copy of the judge lock under
`controller/assessments/<judge-fingerprint>-<mode>/`. Re-assessing the same snapshot
and mode uses that record; `--retry` creates another assessment without replacing
earlier evidence or silently paying for another judgment.

`var/index.html` is a searchable run index generated by `runs report`. Runtime
artifacts and private data are ignored by Git. Public task manifests identify
the local references; run metadata pins task, system, substrate and runtime hashes.

## Substrate use

A mounted substrate measures availability; a substrate comparison also needs to know
whether the agent used it. `runs list` and `runs report` derive this from
`logs/events.jsonl`, for both drivers and for earlier runs, with no model call and no
change to scoring. Each command that reached the runtime is classed by its strongest
use of a `/substrate` path: `ran` (a script executed directly or through `python`,
`bash`, `sh`, `Rscript` or `uv run`), `read` (any other reference, such as `cat` or
`sed`), `listed` (`ls`, `find`, `tree`) or `entered` (`cd`). Runs are split into
`ran_ok` and `ran_failed` by exit status; the status belongs to the whole command, so a
chained or piped command is attributed as one. Tool calls the built-in driver refused
as truncated or invalid were never executed and are not counted. Log lines that cannot
be parsed, such as a partial line from a killed run, are skipped and counted in
`unreadable_log_lines` rather than failing the run list. The record also gives
the first step that touched the substrate and the paths named.

This implements the [benchmark design](../archive/docs-2026-10/benchmark-design.md#comparing-substrates-and-cost)
requirement to record whether an agent opened a skill or retrieved a document, and ports
the historical pilot's trace audit (`archive/pilot-2026-10-01/smoke/audit.py`,
`revision/collect.py`) from `/catalog` to any mounted substrate. Library invocation is
not yet measured. As the design states, use is diagnostic evidence: compare assigned
configurations as the primary analysis, not only the runs that used the substrate. A run
can follow its substrate and still be misled by it.

This is a lower bound from command text. Relative paths after `cd /substrate`, shell
variables, and workflow code that opens substrate files itself are not attributed. A
substrate installed as a library in the runtime image, rather than mounted, is not
measured. `unknown` means the run has no execution log; `none` means it ran commands
but none named the substrate.

## Reuse across other tasks

```sh
./bench run wvg-definition-audit --system my-agent --parent RUN_ID
./bench suite experiments/my-sequence.yaml
```

A sequence file contains `system`, ordered `tasks`, and `condition: retained` or
`reset`. Every task gets a fresh controller conversation. Retained runs carry the
agent's state and prior submitted artifacts, never assessments, private forecasts,
verification observations or judge feedback. Parent system definitions and
substrate hashes must match. Reset runs receive no prior artifacts. Counterbalance
task orders and compare the same task/position; the example is a runner mechanism,
not evidence of accretion on its own.
`continue_after_failure` controls whether execution errors stop a suite. Every
step and error is recorded; failed steps without frozen retained state do not
replace the last valid parent. Scientific partial/pending scores remain recorded
outcomes and do not stop the sequence.

## Current readiness

ACMAD and WVG support supplied-data development runs and independent numerical
checking/replay. WVG's full approved literature snapshot and expert source review
remain release work; its numerical geometry definitions are in the prompt and
the implementation excerpt is an input. Current task publication approvals are
false and assessments report `benchmark_eligible: false` until those reviews are
completed. This does not prevent assessing development attempts.

Seasonal acquisition development runs use the reviewed controller-owned frozen
replay transport. Agents initially receive only the source plan, then call
`acquire` for each allowlisted native training source. Forecast requests must
match the plan exactly; later observation years are denied. Native bytes travel
through Docker stdin, with hashes, coverage, cache hits and denials retained in
controller logs. The sandbox has no provider network or private targets.
This tests scientific acquisition/processing from native training subsets,
not live provider authentication, availability or download speed. Preparing
the native source replay bundle is a separate step; normalized fixtures are
never an acquisition substitute. See [internal setup](internal-setup.md).

The short-rains workflow task adds nested rolling predictor selection and
independent retrospective targets. Its controller checks alternate-path replay,
held-out/future-input perturbations, and changed-predictor inference with rainfall
removed. Scientific output agreement and expert interpretation remain separate.
The run report exposes criterion outcomes alongside aggregate score bounds.

## The locked autojudge

`judges/auto-v1.yaml`, `judges/system-v1.md` and `judges/auto-v1.lock.json` define
the operational assessment contract. The native model identifier and accounting
schedule are pinned from the completed pilot; the code does not choose a floating
latest model or fall back to another judge. Provider availability/rates should be
checked when selecting a new experiment configuration. The request/response contract is covered by tests. The development calibration
pilot also prepares blinded real and constructed cases; its call status and
operational expectations are recorded separately from human judgments.

### Four evidence layers

1. **Validity and numerical checks.** Deliverables, schemas, provenance records,
   retained-file hashes, source coverage and independently calculated scientific
   references. Detailed diagnostics support the task's grouped scientific outcomes.
2. **Trusted execution.** Offline replay from the submitted workflow in the pinned
   runtime. Seasonal inference receives only the forecast batch; observation-based
   skill is a separately reported controller outcome. Replay must match declared
   scientific arrays/answer fields, not optional session notes.
3. **Scientific judgment.** One evidence-citing model assessment of expert, mixed
   and execution outcomes. The packet includes task criteria, submission text/code,
   a verified figure, controller checks/execution evidence, and bounded scientific
   tool traces with explicit omissions. System, model,
   cost and parent labels are omitted. Library names inside artifacts can still
   reveal part of a substrate; complete blinding is not claimed.
4. **Information integrity.** Trusted sandbox configuration and artifact invariants.
   The scientific tool container has no network, host secrets, Docker socket,
   references or other run's controller files. Imported artifacts lack original
   boundary evidence and remain unresolved on integrity.

The controller, adapter integration and Docker daemon are trusted infrastructure.
Custom adapter authors must route model tool execution through the isolated
container. This is not an adversarial sandbox for arbitrary host adapter code.

### Structured ratings and completion

The judge returns exactly the supplied outcome IDs with `score: 0|1|2|null`, a
reason, evidence IDs and uncertainty. Unknown citations, boolean scores, omitted
criteria and invalid/incomplete JSON are rejected. Full credit requires a complete
cited submission artifact; figure-dependent criteria also require a verified
cited figure. Missing or truncated required evidence cannot be assumed correct.

The controller computes weighted score bounds. Unresolved outcomes contribute
zero to the lower bound and their full weight to the upper bound. Unavailable controller infrastructure leaves execution unresolved; scientific
command or output failures remain failures. Numeric failures
and failed replay force the relevant outcome to fail, irrespective of model prose.
Completion requires every required outcome at full credit, passing basic validity,
passing execution requirements and passing trusted integrity. Known failures are
reported as partial/failed; missing judgment or integrity is pending. Free-text
concerns are informational, rather than an additional hidden gate.

Correct negative results can complete. Forecast skill is reported continuously,
with inspected-development status; it never overrides method correctness or
becomes an arbitrary pass threshold. Fixtures are labelled and excluded from
capability claims. Development completion is distinct from task publication approval.

### Locking, retries and audit

```sh
./bench judge status
./bench judge packet RUN_ID
./bench assess RUN_ID
```

The lock fingerprints the judge prompt/configuration, evaluator/controller source,
task contracts/manifests, package configuration and dependency lock. Installed
controller dependencies must also match every pinned version. Drift stops
execution/assessment.
Changing grading means reviewing/versioning it and deliberately running
`./bench judge lock`; it does not change existing raw responses or assessments.
Run reports include fingerprints so scores from different policies are identifiable.

The judge makes one call with no automatic retry. It reserves the next call against
configured token/cost limits. Raw responses, packets, ratings and usage are retained.
Structurally invalid submissions are assessed without paying for model judgment.
Missing credentials or invalid responses leave expert evidence pending and record
the error. After fixing setup, `assess RUN_ID --retry` explicitly creates another
record; all previous attempts and their usage remain available.

The locked judge is a reproducible operational procedure, not a claim of perfect
scientific judgment. Domain-reviewed task definitions, scorer diagnostics and
human audits of borderline or disputed ratings remain necessary release work.

