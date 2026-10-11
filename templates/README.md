# Author a task and inspect its rubric

Start with a known-correct control. Certification comes after the authoring loop.

```sh
.venv/bin/python -m assessment assess kenya-forecast-revision service-area--weeks-1-2 --control correct --output var/review/first-control
.venv/bin/python -m assessment rubric kenya-forecast-revision
```

Choose another name from `controls/build.py` to see a planted fault fire. Every
row shows its requirement, implementation, result and effect on completion or
ranking. `assessment.json` retains evidence; `review.md` is the readable view.
`--format json` emits the machine-readable assessment. `--local-trusted` is
available only with `--control`; agent submissions always run in Docker.

## Four decisions, each with a home

| Decision | Write it here | Inspect it here |
| --- | --- | --- |
| The job: arrays, dimensions, units and claims | `brief.md`, with detailed method material in staged inputs when the job prescribes one | `assessment brief TEMPLATE INSTANCE` |
| The primary question: compute, conform, or forecast | `question` in `spec.yaml` | `assessment rubric TEMPLATE` |
| The instruments and their scientific decisions | Declarations in `spec.yaml`, hooks in `reference.py`, template-owned judge wording | One row per instrument in the rubric |
| Completion and ranking policy | `assessment_policy.completion` and `.ranking` in `spec.yaml` | Each row's `required_for`, plus the separate result columns |

`mode` remains a compatibility label. `reference_match` selects the reference
instrument explicitly. A task may combine reference quantities, freely chosen
forecasts, process requirements and scores; its primary question does not add
hidden checks. A checklist step based on reference results requires that
instrument. Judge wording can be reused by name, but the five pilot templates
own all wording they use.

## Implement only the instruments the job needs

| Declaration | Scientific implementation |
| --- | --- |
| `results` | Names, coordinate axes, dimensions, units in the brief, and numerical error bounds |
| `reference_match: true`, `conventions`, `pitfalls` | `reference(inputs, params, conventions)`; accepted readings and named faults |
| Exact required cases | `expected_coordinates(inputs, params)` |
| `invariants` | Functions in `INVARIANTS` |
| `probes` | `perturb_inputs`; optional `INVARIANCE_PROBES` for data that must leave an output unchanged |
| Forecast input response | Optional `response_results` selects scientific outputs; `RESPONSE_GROUPS` requires each named deliverable to respond to at least one `RESPONSE_PERTURBATIONS` kind |
| `claims` | `expected_claims(results, params)`, or `score` for a stated metric |
| `process` | Evidence checks, reference results, method pointers or one explicit judge question per requirement |
| `interpretation`, `judge_questions` | Exact requirement and silence policy for each prose review |
| `skill` | `score(results, params, private, split)`; baselines and an independent metric implementation |

Every template also stages inputs (`stage_inputs`), restores data (`prepare`),
enumerates supported instances (`candidate_instances`) and fills the brief
(`brief_fields`). A template whose prose is judged against figures may define
`judge_summary(results, params)`, whose text is appended to the controller's
array summary shown to the judge. Keep science helpers within the template folder so their code
is fingerprinted. A Python implementation is part of the rubric's contract even
when it lives in another file.

For acquisition tasks, the job can start with a source catalogue rather than
analysis-ready arrays. `mam-multimodel-outlook` stages public endpoint descriptors
and a separate controller-owned provider snapshot. Its task-owned, fingerprinted
`sandbox_factory` and `executor_factory` expose only the public descriptors to
the actor and serve raw monthly files over an isolated HTTP source service.
`acquisition_evidence` retains controller request logs before temporary replay
directories disappear. Existing tasks keep their offline runtime unchanged.
Use changed-source reruns to test that computation follows freshly acquired data;
request logs alone cannot establish this. This snapshot transport does not test
live-provider authentication, discovery or download speed.

A reference task supplies an independent implementation through `independent`.
A scoring task supplies `independent_score` and `baseline_results`. Independence
means separate scientific implementation, not a switch inside the same function.
Controls may reuse the primary implementation because they test the controller;
they do not establish independent scientific agreement.

For a task with audit diagnostics and multiple forecasts, changing diagnostics
must not establish forecast responsiveness. Project onto the forecast arrays
and declare separate response groups for each deliverable. A climatology method
can legitimately respond to training targets while ignoring SST predictors.
Test cached outputs both together and separately. Parallel scientific file I/O
belongs in fresh Python processes: shared-thread HDF5 validation has crashed the
host controller.

Keep fitted parameters, nested selection, verification, production and saved
inference visible separately when the job asks for each. Correct hindcasts can
coexist with wrong production forecasts. Compare every required numerical field
even when a separate units declaration or metadata check fails; state explicitly
whether unit attributes are checked. `monthly-cycle-calibration` plants both
faults together to verify that one does not hide the other.

Calibrate prose questions on real faulty submissions, narrow corrected controls
and unaffected components. Exact quotations establish that the cited text exists;
they do not establish that the judge's reasoning is correct. The
[historical calibration](../experiments/failure-judge-calibration-eight-call-2026-10-08.json)
includes a broad method review that approves an incorrect combined diagnostic.
Keep deterministic numerical checks in the completion gate, and distinguish a
general discovery test from questions aimed at a particular required component.

For an ordinary tooling comparison, give both arms the same job definition and
let the tooling arm discover installed libraries through their normal
documentation. Audit staged files for curated function excerpts, worked solutions
or required helper recipes before launch. If such assistance is an experimental
condition, label and compare it separately. A prescribed scientific algorithm
defines a reproduction job; supplied implementation code is a different condition.

## Declare the result policy

```yaml
question: compute_quantity
reference_match: true
assessment_policy:
  completion: [envelope, coverage, variant, invariant.*, probe.*, claim.*, process.*]
  ranking: [envelope, coverage, variant, invariant.*, probe.*, claim.*, process.*]
```

Include only patterns that match declared instruments. Both gates must require
the envelope. List a prose check explicitly if it gates the task. Required
process statements stay required even when a judge decides them. Checks omitted
from both lists are supplementary and still appear in the result. Skill never
becomes a pass/fail check. `skill.ranking_enabled: false` prevents an informative
score on a small sample from being presented as a ranking.

The envelope is shared in [assessment/envelope.md](../assessment/envelope.md).
The [assessment contract](../docs/assessment-format.md) defines error bounds,
variant matching, rulings and the three possible check results.

## Declare stages for a long-horizon composition

A job with several dependent parts declares `stages`, in order. Each stage
names its `results` (the group it owns), an `absolute` verdict (`results:` for
a reference match on matched results, or `checks:` for named instruments
computed on the controller's inputs), a `local` verdict (`checks:` that
recompute the stage from the submission's own upstream arrays, including
`probe.<name>.<part>` rows from a probe that declares `parts`), its
`upstream` stages, an optional `weight` and the judge `review` rows it owns.
Gate completion on `stage.*` plus the envelope, coverage and any invariant
that spans every stage; leave the whole-submission `variant` and probes
supplementary. The record then carries a stage profile and a weighted
fraction, and a fault in one stage stays in that stage. The reference module
provides the local-verdict invariants; they take the submission's arrays and
never read the controller's inputs. See
[objective-seasonal-outlook/spec.yaml](objective-seasonal-outlook/spec.yaml).

## Freeze data and build controls

`instances.yaml` lists public development IDs. `sources.json` identifies frozen
source files and their hashes. Private inputs stay under
`var/private/templates/<template>/`, outside Git. Withheld targets are never
staged for the agent. The two converted tasks can be restored from the original
frozen task directories recorded in their manifests, using `prepare --source`.

`controls/build.py` names the correct solution, accepted alternatives and planted
faults. Each faulty control declares the checks expected to catch it. Test
scientific defects, such as leakage or failed conservation, rather than incidental
formatting. A correct control with an unrun required judge is numerically valid
but not yet complete; the review must show that distinction.

## Validate, then lock a comparison

```sh
.venv/bin/python -m assessment certify TEMPLATE --full
.venv/bin/python -m assessment attempts TEMPLATE
```

The four automatic tests compare independent implementations, assess correct
controls, catch planted faults on their intended checks, and measure pitfall
separability. These control tests validate computed checks; required prose
checks must also be evaluated before claiming a complete passing submission.
The fifth test records real agent attempts and open unknown answers. Trial
review requires at least two attempts under the current fingerprint.

The record distinguishes `automatic_checks`, `trial_attempts`, and
`scientific_approval`. `certified` remains false pending scientific approval.
Lock the spec before comparing systems. New scientific or verdict policy changes
require a new version; earlier contracts and assessments remain historical.

System configuration, the adapter protocol, tooling-use evidence and Docker
setup belong in the [runtime guide](../docs/runtime.md).
