# Reviewing the first three task packages

The [three packages](../tasks/README.md) are revised to `review-0.2` after
[the exported critiques](reviews/2026-10-02/response.md), and await joint review.
They include concrete scientific goals, deliverables, source records, hashed local
input copies, rubric trees, controller references and static numerical checks.
They remain development material: expert approval, public redistribution review,
experiment settings and clean submission execution are not completed.

Start with the seasonal task, where the scientific goal and existing evidence are
best established. Then review the ACMAD objective task and the WVG audit. The
common question is whether each task is sufficiently useful scientific work,
with success requirements that an independent reviewer can assess.

## What is available to review

| Task | Input and numerical reference | Scope limits | Decision to make |
| --- | --- | --- | --- |
| [Seasonal calibration](../tasks/seasonal-calibration/review.md) | Agent acquires declared products; controller fixtures match the pilot aggregation reference | Acquisition runtime/preflight is pending; open methods need fold review; 2005–06 is inspected development data | Choose acquisition mode and validate the full workflow. |
| [ACMAD objective](../tasks/acmad-objective/review.md) | Three actual component MMEs; independent combination matches the existing objective within the declared tolerance | Tests final combination and support/sensitivity, not component fitting, consensus adjustment or forecast skill | Is this a substantial standalone task, and is the missing-component convention correct? |
| [WVG definition audit](../tasks/wvg-definition-audit/review.md) | Real inherited ERSSTv5, checked against its provenance; separate NumPy/xarray calculations agree | Curator conventions isolate geometry; the shorter baseline and missing author data prevent exact published analysis reproduction | Include this audit now, or expand it after obtaining the author workbook? |

The local reference fixtures are in `var/private/tasks/<task>/agent-inputs/`.
Despite that historical directory name, seasonal normalized arrays are controller
development fixtures and must not be mounted as starting inputs in the acquisition
task. Its starting material is the tracked source plan and shared artifact contracts.
ACMAD and WVG still use the permitted supplied-input inventory.
Corresponding expected arrays and private seasonal inputs are in `controller/`.
Agent exports must include only allowed inputs, the prompt, success criteria and
approved source context. Neither controller artifacts nor other submissions
belong in the accumulated substrate.

The WVG packet currently links the literature rather than storing a full paper
snapshot. Before a controlled run, supply an approved frozen document or retrieval
snapshot. The author archive metadata was accessible, but workbook download
returned authorization/access errors. The package does not substitute local SST
for that archive while claiming to reproduce the paper's forecast result.

## Rubric review

The revised rubrics have six scored seasonal outcomes and four each for ACMAD and
WVG. Relative weights apply to scientific outcomes. Basic file/schema validity,
provenance records and source coverage are unweighted, as is trusted information
integrity. All required outcomes and prerequisites must pass for completion.
Detailed reference diagnostics remain evidence inside outcomes.

For each leaf, check that its requirement is in the prompt, its evidence is
obtainable, its evaluator can discriminate meaningful failures, and it does not
reward a particular library or presentation style. Missing expert/execution
evidence remains unresolved. The static checker verifies numerical and artifact
evidence and aggregates it into outcomes; it does not infer replay, scientific correctness or integrity
from file presence. Numeric agreement cannot establish the method's isolation
from verification observations.

The older [seasonal rubric proposal](seasonal-rubric-proposal.yaml) remains an
expanded design discussion. The package's revised smaller tree is the current proposed
implementation contract. Neither has replaced the historical pilot's rubric.
The two should be reconciled during review rather than used as interchangeable
scoring versions.

## Accretion across standalone tasks

The main experiment now lets a system build its substrate while doing other tasks
in the benchmark. Tasks have no required successor. The
[experiment manifest](../experiments/accretion-review.yaml) owns sequence order,
retention, feedback access and fresh-workspace controls.

With three tasks, comparing the six permutations is one possible development
design; models, replication and budget remain unset. Evaluate retained/reset
differences within the same task and order. A faster third task than first task
does not establish learning when their difficulties differ. Count failed attempts
and work spent maintaining the substrate, and inspect whether retained code,
notes, indexes or scientific knowledge actually get used.

Retained artifacts and a fresh conversation per task make the evolving substrate
inspectable. Conversation retention can be another condition. Verification
observations, numerical references and grader feedback stay outside the workspace
throughout the sequence. Before adding other tasks, check that their permitted
observations cannot reveal private targets of a later prediction task. Explicit
related follow-ups remain a complementary way to isolate saved-fit reuse.

## Preparation and validation

The controller tooling independently checks monthly aggregation, combination and
index arithmetic using existing local data. It makes zero model calls, performs
zero agent attempts and never executes submission scripts. The checked snapshot
is recorded in the local validation report at `var/validation/task-packages.json`. Generate it with `./bench tasks validate` after installing the internal data bundle.
Source hashes record what was inspected; they do not imply institutional approval.

Reference tests exercise incorrect month coverage, unit mistakes, missing
observational area, differing component grids, partial probability vectors,
missing-support masks, index baseline/season coverage and static-check limitations.
These are evaluator diagnostics, not new invented benchmark tasks.

Before launching the revised acquisition task, validate provider requests,
freeze raw response content and verify acquisition and replay adapters. Existing
normalized numerical fixtures do not establish that this runtime is operational.

After our review, record approved methods, tolerances, weights and information
boundaries under a new package version. Then complete clean execution adapters
and the expert evidence protocol before any bounded agent comparison. The current
launch controls remain closed; no budget or models have been selected here.
