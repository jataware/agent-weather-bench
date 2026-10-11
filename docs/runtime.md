# Systems, runtimes and adapters

The subsequent [parallel investigation](parallel-investigations-2026-10-08.md)
uses a [separate matched environment record](../experiments/investigation-runtime-2026-10-08.json):
242 general distributions have identical versions in every arm; only declared
weather packages and documentation differ. The
[runtime incident report](investigation-runtime-findings-2026-10-08.md) documents
optional scratch-state retention recovery and an HDF5 crash in threaded trusted
validation. Scientific file I/O now runs in separate processes. These incidents
are separate from the native import-order workaround below.

The [8 October runtime manifest](../experiments/runtime-manifest-2026-10-08.json)
pins the focused study's derived images and current library commits. Original
images remain attached to historical attempts. `Dockerfile.tooling-repair`
initializes pyproj before cfgrib can be discovered through xarray: their original
wheel combination aborts at shutdown in the opposite order. This tested
workaround preserves every installed package. The
[native import probe](../experiments/native-import-probe-2026-10-08.json)
records both the failure and repaired results. Run `runtime/probe_native.py`
or `runtime/probe_io.py` to reproduce checks inside Docker, without crashing
host Python. The focused ACCORD image installs wheels built from the clean
commits in the manifest with `uv build --wheel`, using
`runtime/Dockerfile.accord-current` and `--no-deps --force-reinstall`; matching
skills and READMEs live at `/opt/accord-current/docs`.

Rhiza's documented `uv run` entrypoint is unavailable in the frozen image;
invoke its installed scripts with `python`. Direct probes verify actual
deaccumulation and rate guards. The original reader requested consolidated Zarr
metadata unconditionally and failed on valid stores without it. The derived
`runtime/Dockerfile.rhiza-reader` changes that request to automatic detection,
preserving the scientific computation. The prepared, unrun focused Rhiza
configuration pins this new image; historical attempts retain their original
images. The [current diagnostics](../experiments/tooling-diagnostics-2026-10-08.json)
pass all six Rhiza cases across both metadata layouts; the
[original diagnostics](../experiments/tooling-diagnostics-before-reader-repair-2026-10-08.json)
preserve the reader failure. This repair is independent of the native
import-order workaround.

## The sandbox boundary keeps model-generated commands off the controller host

The harness's adapter (`systems/<id>/adapter.py`) is trusted integration code.
It calls the model or agent library and translates its tool requests to the
protocol below. Model-generated commands go through the protocol and run in the
isolated Docker runtime, never on the controller host. An agent command line
that executes its own tools needs an integration that routes them into the
runtime container; pointing a host-executing command line at this repository
does not establish the benchmark's information boundary.

Adapters run in their snapshotted directory. `{python}` expands to the
controller interpreter; `{driver}` expands to that directory. `driver.env` lists
environment variable names to pass to the controller; do not store secret
values in the system definition. Model credentials stay on the controller and
are never mounted into the runtime container.

Acquisition tasks may supply task-owned `sandbox_factory` and `executor_factory`
hooks. `mam-multimodel-outlook` uses an internal Docker bridge with isolated
gateway mode, exact actor/source memberships and no published ports. Only
public endpoint descriptors are actor-mounted; raw monthly files are served
read-only by a source sidecar. Every replay gets a fresh controller-selected
snapshot. Controller request logs retain hashes, bytes and server timings;
they are separate from scientific completion and agent submission time. This
requires Docker Engine 28's isolated bridge support and fails closed when that
boundary is unavailable. It does not provide live CDS transport or credentials.

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

## Retained-work attempts explicitly use --parent

A run with `--parent RUN_ID` carries the agent's earlier submission and retained state under
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
the image a system runs in; `certify` and `assess` use the task's executor, with
the offline runtime as the default.
