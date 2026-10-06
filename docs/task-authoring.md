# Create a task that can be checked

A task is a scientific goal, an information boundary, and a contract for evidence.
Choose a result that an independent evaluator can verify. A plausible report
alone is insufficient.

The framework has task-specific evaluators registered in `TASK_MODULES` alongside
the original three evaluators. New tasks require
Python integration code as well as a package. The CLI does not yet provide a
generic task plug-in loader or a `tasks init` command.

## Start with a source

Use a published outlook, a centre's replication procedure, or a paper's analysis.
Record the source version and the exact method or result to reproduce. Specify
the region, period, lead time, variable, resolution, and relevant method choices.

Distinguish source requirements from curator choices. State ambiguous points in
the brief. Define which outputs need reference agreement and which allow several
sound methods. For example, calibration predictions can differ while input
processing and verification arithmetic remain fixed.

For a forecast task, freeze the data cutoff before observations resolve. Keep later
observations and private reference outputs outside the agent workspace. An index
audit can use retrospective observations if the brief explicitly permits them.

## Create the package

Use a lowercase ID containing letters, digits, and hyphens. From the repository root:

```sh
cp -R tasks/acmad-objective tasks/YOUR_TASK_ID
```

Rewrite the copied files for the new goal. Replace the input manifest with one
for the new inputs and references. The copied manifest does not describe your task.

```text
tasks/YOUR_TASK_ID/
  task.yaml              ID, version, brief, outputs, input mode, review state
  prompt.md              Self-contained scientific instructions
  sources.yaml           Source versions, method locators, curator choices
  rubric.yaml            Weighted scientific outcomes and basic validity checks
  review.md              Questions for domain reviewers
  input-manifest.json    Frozen file hashes, visibility, reference evidence
  source-plan.json       Required if the agent must acquire data
  review.html            Generated review page
```

The current runner expects the standard filenames above. Use the shared
[provenance](../tasks/provenance-contract.md) and
[replay](../tasks/replay-contract.md) contracts through `artifact_contracts`.
Current judge packets prioritize `report.txt`, `answer.json`, `execution.json`,
`handoff.txt`, declared scientific entrypoints and fitted state. Provenance has a
separate cap so its inventory cannot crowd out the science. Packets record
selection, omissions and truncation, and inspect `outlook.png` as the main figure.
Use these names, or extend the packet builder deliberately.

In `task.yaml`, set `id`, `version`, `title`, `source_category`, `track`, `evaluation`,
`outputs`, and the shared contract paths. Set `input_contract.mode` to
`supplied_inputs` for the existing offline runner. An `agent_acquisition` task
requires its own validated acquisition transport. Seasonal calibration has an
audited frozen-replay acquisition transport; other acquisition tasks remain blocked
until they have their own preflight. Optimization feedback likewise requires the
reviewed controller scorer, bounded requests and a retained public feedback ledger.

Keep scientific, scoring, redistribution, and launch approvals false during
development. The current package validator is designed for development tasks;
public release approval also requires a release validation procedure.

## Write the rubric

Use a small set of scientific outcomes with clear evidence. Place generic delivery,
schema, provenance, and integrity requirements under unweighted basic validity.
Do not count the same numerical result in several weighted leaves.

Each scored leaf needs a unique ID, a positive weight, `required`, `evaluator`,
`criterion`, and `evidence`. A deterministic leaf also needs its named `checks`.
The supported evaluators are `deterministic`, `expert`, `execution`, and `mixed`.
Match `task_version` to the package version. The current validator requires every
scored leaf to be required.

Specify numerical tolerances in the evaluator. Record them in the review material.
Use scientific meaning to choose tolerances; avoid tuning them to one agent's
output. Scores against observations remain separate from method completion.

## Freeze inputs and references

Store local task data under:

```text
var/private/tasks/YOUR_TASK_ID/
  agent-inputs/          Only the files allowed during execution
  controller/           Independent reference arrays and verification targets
```

Use flat filenames within these directories for the current input mount. Include
`agent-inputs/source-manifest.json` with a `sources` list of identifiers that the
submission's provenance must cover. The existing checker expects that source
manifest for supplied-input tasks.

The input manifest records each relative filename, SHA-256 hash, byte count, and
visibility. `agent-inputs/` files have visibility `agent`; `controller/` files have
visibility `controller_only`. Record dimensions and units for scientific arrays.
Include source-record hashes, the reference code hash, and reference validation
results. Follow an existing manifest's structure.

Preparation must fail if an existing frozen input differs. Create a new reviewed
version rather than silently replacing evidence. Preserve prior references when
correcting a scorer. Assessments retain their original lock fingerprints.

## Register the implementation

The following are the current integration points. These are source edits, not
configuration-only task registration.

| File | Required change |
| --- | --- |
| [prepare.py](../weatherbench/task_tools/prepare.py) | Add the ID and module to `TASK_MODULES`; provide `prepare(repo)` to recompute and verify its references from the installed data. Author the manifest separately; default preparation must not rewrite it. Keep hashed source snapshots inside the repository. |
| [references.py](../weatherbench/task_tools/references.py) | Add independent reference calculations. Cross-check them against another implementation or a trusted source artifact. |
| [checks.py](../weatherbench/task_tools/checks.py) | Implement the module's `submission_checks(submission, private)`. Its named checks must exactly match the rubric. WVG is an explicit branch; unknown tasks are rejected. |
| [evaluation.py](../weatherbench/evaluation.py) | Implement the module's `evaluate(run, output)` with scientific comparison, clean offline replay, changed-input probes and saved-fit inference where relevant. The registry dispatches it. Original tasks still use `ARRAYS` and `ANSWERS`. |
| [render.py](../weatherbench/task_tools/render.py) | Add a `SUMMARIES` entry: display order, short name, category, summary, and limitation. |
| [judge.py](../weatherbench/judge.py) | Extend evidence collection and execution gates if the new task differs from the existing artifact and rubric conventions. |
| `tests/` | Add tests for the scientific invariants and credible failure cases. |

`tasks list` discovers `task.yaml` files. Validation, preparation, and review
rendering use the registered `TASKS` tuple. Complete both package and code
registration before treating the task as runnable.

The current aggregation recognizes `reusable_workflow` and `reusable_verifier`
as offline replay outcomes, including counterfactual results when present. New
execution outcome IDs need an explicit gate in `judge.aggregate()`.
Add corresponding prediction or acquisition gates when the scientific goal needs
them. An `evaluator: execution` label alone does not create a new controller check.

Check replay from retained inputs in a clean, offline runtime. Numerical agreement
alone can reward a copied output; inspect the submitted workflow as well. For a
saved calibration, prediction must use the saved state without fitting on targets.

Useful failure cases include changed coordinates, incorrect units, shifted periods,
wrong category labels, changed missing masks, leaked verification data, and a
replay command that cannot reconstruct the result. Select cases relevant to the
method, rather than adding checks that repeat the implementation.

## Review, validate, and lock

Ask domain reviewers to check source interpretation, reference calculations,
rubric weights, tolerances, and data rights. An agent can draft the brief and
rubric; that draft does not replace domain review.

After implementing the new task:

```sh
./bench tasks prepare
./bench tasks validate
./bench tasks render
.venv/bin/python -m pytest -q
./bench judge lock
./bench judge status
```

Review `tasks/YOUR_TASK_ID/review.html`. The page accepts comments and exports;
those notes do not edit the package or set approval fields.

Creating a task changes the judge's locked inputs. Regenerate the lock only after
reviewing those changes. The new fingerprint identifies the resulting assessment
policy; it does not rewrite previous assessments.

Keep task sequences in `experiments/`. A task has no mandatory successor.
Retained/reset sequences can mix tasks from across the collection. Explicit
related follow-ups are optional experiments.
