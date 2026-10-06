# Developing tasks and calibrating evaluation

The next development cycle should establish whether our assessments recognize
valid forecasting work, reject consequential scientific mistakes, and explain
why a system succeeded or failed. Use the three existing tasks and two candidate
briefs to define the scope, then calibrate against reviewed submissions before
expanding the task collection or substantially refactoring the evaluator.

This is a proposed work plan. It changes no task contracts, scoring weights,
approval fields, or assessment code. Candidate briefs are not runnable tasks.

The initial cycle is work the coding agent can do autonomously, with Ezekiel
as the sole human reviewer. It requires no ACMAD involvement, RCC consultation,
or recruitment of additional evaluators. Later, RCC consultation can help check
seasonal forecasting requirements, and the existing small group can support
human testing and evaluation. Neither is a prerequisite for this cycle.

## What this cycle should produce

1. An agreed evidence map for the existing tasks and two complementary briefs.
2. Natural autonomous attempts and constructed contrasts for every packaged task,
   with human judgments, preserved traces and inspectable reasons.
3. A comparison of those judgments with the current evaluator, identifying
   missing checks, false acceptance, false rejection, and unresolved evidence.
4. Targeted evaluator changes justified by those disagreements, followed by
   checks on additional examples that were not used to develop the changes.

Calibrate across every existing task: `acmad-objective`, `seasonal-calibration`
and `wvg-definition-audit`. There are three packaged tasks today; the two briefs
below would bring the set to five once implemented. Use the readily available
combination fixture to check the mechanics first, without restricting the
exercise to that task or involving ACMAD staff. Review the candidate briefs at
the same time so their different evidence needs inform shared abstractions.

## Decide what must agree and what may differ

Reference agreement is appropriate when a task prescribes a calculation. Open
research tasks need checks on data, experimental validity, reproducibility, and
the support for conclusions, while permitting different sound methods and
different predictions. A reference implementation is evidence, not automatically
the only acceptable solution.

| Task | What is prescribed | What may differ | Evidence and present gap |
| --- | --- | --- | --- |
| [ACMAD objective](../tasks/acmad-objective/prompt.md), review-0.3 | Equal available-component combination, missing support, nominal 2/8/8 sensitivity, disagreement and summary calculations. | Implementation, supported language or tools, and presentation. Changing the prescribed weighting is not an alternative correct solution. | Independent numerical references exist. Interpretation requires source and report review; replay must establish recomputation. Scientific and scoring approval remain pending. |
| [Seasonal calibration](../tasks/seasonal-calibration/prompt.md), review-0.2 | Acquisition boundary, units and seasonal aggregation, training years, fold exclusion, target and metric definitions, and saved-fit prediction. | Documented sound calibration and training-only selection, with potentially different predictions. A valid negative finding can complete the task. | Processing references and controller verification exist. Acquisition transport is blocked; fold isolation and saved-fit behavior need stronger evidence. The inspected prediction years are development evidence. |
| [WVG definition audit](../tasks/wvg-definition-audit/prompt.md), review-0.2 | The supplied geometries, curator processing conventions, index calculations and comparison statistics. | Equivalent implementation and the explanation of source differences and limitations. | The geometry reference exists. Frozen literature access and source interpretation review by Ezekiel are pending. The missing author workbook prevents a broader published forecast-skill replication; it does not invalidate this narrower reference. |
| Literature-led predictor study, candidate | A reviewed source corpus, forecast issue boundary, evaluation cases and baseline calculations. | A supported interpretation and admissible method chosen using permitted evidence. | Needs a source and data audit, accepted example analyses, and an evaluator that can assess differing valid methods. See the brief below. |
| Forecast workflow adaptation, candidate | A frozen starting pipeline, an agreed change in forecasting requirements, data access, scientific invariants and verification definitions. | Code structure and supported implementation choices that satisfy the revised requirements. | Needs a working source snapshot, real data coverage for the change, and independently checked outputs. See the brief below. |

For each required outcome, record the public requirement, acceptable variation,
evidence needed, verification method, and consequence of failure. Every hidden
check must correspond to a public requirement. Resolve ambiguity in the task
before labelling an unfamiliar but plausible solution as wrong. Numerical
tolerances should follow the scientific calculation and precision requirements,
not be widened until one submission passes.

## Source the next cases from existing ACCORD work

The current `acmad-objective` contract covers combination of supplied component
forecasts. It does not assess reproducing the calibration that generated them.
Existing methodology-matching code gives us a route to that richer workflow
without commissioning new work or contacting its original authors.

The October 5 source review found newer evidence than the benchmark's snapshots:

- [September 30 replication result](https://jataware.slack.com/archives/C09U0JNKR45/p1790798504289269):
  a reported ACMAD result with no residuals. The newer
  [AfricaS2S transform implementation](https://github.com/ACMAD-Niamey/africas2s/commit/4f8526a32232f9c9af400a01e5a6f103a865c735)
  adds `transform_predictand="cpt_empirical"`, separate full-fit and fold
  transform conventions, transformed-space tercile boundaries, and per-cell
  missing-value replacement. Its commit reports agreement with archived CPT
  outputs within their float32 precision for three predictor types. This review
  inspected the patch; it did not rerun the archive comparison.
- [ICPAC parity implementation](https://github.com/ACMAD-Niamey/africas2s/commit/bbc52e34b6aedc709865d2365a43c91efa143c3d)
  supplies explicit eREG, logit and CCA compatibility settings, with tests under
  `tests/test_ereg_parity.py`, `tests/test_logit_parity.py` and
  `tests/test_cca_parity.py`. This is a source for reconstructing an existing
  method and explaining consequential numerical differences.
- [Paper-to-code calibration work](https://jataware.slack.com/archives/C09U0JNKR45/p1784728969913189)
  points to the Kharin 2017 reproduction and an East Africa field comparison in
  `accord-research/experiments`. The
  [IOD forecasting example](https://jataware.slack.com/archives/C09U0JNKR45/p1788979658086769)
  points to `accord-research/chc_analyses/IOD-forecasting`. These are alternative
  sources for the literature-research brief, subject to code and data inspection.
- [The reported tercile-map discrepancy](https://jataware.slack.com/archives/C09U0JNKR45/p1787589923120589)
  offers a real repair candidate for workflow adaptation. Separately, DeepScale's
  `scripts/benchmark_pycpt.py` documents a comparison of in-sample probabilistic
  hindcasts with held-out verification. That is a useful source for calibration
  cases where method reproduction succeeds but a forecast-skill claim is invalid.

First locate and freeze the exact code, library versions, inputs, archived outputs
and comparison scripts behind one matched seasonal case. Recompute intermediate
fields and final probabilities, including masks and support, and record the
precision and coverage of the comparison. Older local replication READMEs report
residuals that later compatibility work addresses; do not use those old results
to set the next task's tolerances. The missing evidence is a pinned, reproducible
benchmark package, not a new consultation with ACMAD.

Faithfully reproducing an operational method and establishing valid forecast
skill are separate requirements. Compatibility code may deliberately reproduce
a legacy convention; assess that fidelity against its specified reference, and
assess any scientific claims separately. Use these sources to sharpen the two
candidate briefs or a later reproduction task, not to register every example as
a new task in this cycle.

Use AfricaS2S and acmadDL as the current library checkouts. DeepScale and Rosetta
remain archived historical sources; preserve the benchmark's frozen snapshots
and revision-specific API references when reviewing old tasks and runs. A new
task should declare its library versions explicitly rather than silently mixing
the old and renamed packages.

## Separate scientific outcomes from assessment conditions

Keep the existing task-specific outcomes during the first cycle. Add a proposed
common reporting view rather than replacing them with a universal weighted rubric.

| Report dimension | Question | Typical evidence |
| --- | --- | --- |
| Scientific correctness | Are the data processing, calculations and implemented method correct? | Inputs, units, coordinates, intermediate arrays, code and independent calculations. |
| Experimental validity | Does the design support the claimed result? | Training and test membership, learned preprocessing, selection records, issue-time availability and baselines. |
| Reproducibility | Can the workflow recompute results and perform its declared inference? | Code and dependency snapshots, permitted inputs, fitted state and trusted execution. |
| Support for conclusions | Do the explanation and claims follow from the evidence? | Source passages, recomputed results, sample counts, uncertainty and limitations. |

These dimensions summarize evidence; they are not four new scored leaves. Avoid
counting the same error repeatedly. Show the relevant failed requirement and its
downstream consequences so similar totals do not hide different capabilities.

Record contract compliance separately: scientifically supported calculations can
still lack a required deliverable and therefore fail task completion. Record
assessment failures separately too: an unavailable runtime or judge does not
establish a scientific error in the submission. Missing original execution
evidence can leave integrity unresolved, including for imported examples.

Report forecast performance and cost alongside these outcomes. Neither better
skill nor cheaper execution compensates for invalid science. Existing weighted
scores and completion rules remain in force until a reviewed, versioned change
is implemented. Review whether each completion gate reflects an essential
scientific or operational requirement; document any remaining presentation or
packaging failures without treating them as proof of incorrect calculations.

## Candidate brief for literature research

**Goal:** assess whether a literature-supported predictor provides useful evidence
for a specified rainfall forecast, implementing and evaluating a defensible method.
The WVG source analysis is one possible starting point, not a requirement to
reproduce its published skill with the current geometry fixture.

Supply a frozen, searchable source corpus containing the relevant method and
data documentation, permitted development data, and a declared forecast issue
time. Ask the agent to extract the claim, resolve or explicitly identify missing
method details, establish predictor availability, and implement a comparison
with a predeclared baseline. Method choice and tuning use development evidence;
evaluation observations remain controller-only.

Expected artifacts are a sourced methodological argument, executable analysis,
selection and validation records, frozen predictions where the claim supports
them, and a report whose conclusions match independently computed results.
An unsupported forecast interpretation must be identified as such; a justified
negative or inconclusive result is acceptable. An incomplete analysis is not
made complete merely by calling it inconclusive.

Before registration, choose the claim, source passages, data vintages, permissible
choices, and verification cases through source inspection and review with
Ezekiel. Identify what an acceptable analysis of an unforecastable predictor
must deliver. The current WVG arrays
alone cannot supply this larger task. Assess retrieval through source accuracy
and its role in the method, rather than citation count or a mandatory search tool.

## Candidate brief for adapting a forecasting workflow

**Goal:** adapt an existing seasonal forecast pipeline to a reviewed new region
or initialization and target season, preserving valid processing, calibration
and verification while producing a reusable implementation.

An initial source anchor is AfricaS2S's
`examples/seasonal_forecast_eastafrica_mam.py` at revision
`4f8526a32232f9c9af400a01e5a6f103a865c735`. The historical DeepScale version was
inspected at `c0452442fae052bba2d1dd7177eac83f11781dae`. The current example still
uses the `rosetta` import name; verify its compatibility with the pinned acmadDL
package when assembling the environment. It connects acquisition to a multi-model
seasonal workflow. Curate and snapshot the relevant code and data documentation
inside the task package; a sibling checkout is not a task dependency.

Give the agent the starting pipeline and changed forecasting requirements.
Require correct issue and valid times, units, spatial support, member handling,
training and verification boundaries, and a runnable workflow for the new case.
Check scientific outputs independently, regression behavior on the original case,
and meaningful tests of the assumptions affected by the change. Evaluate code
quality through those behaviors and the reproducible handoff, rather than a
preferred code style or library invocation.

Pin one change and verify its real data coverage before packaging. Do not require
an arbitrary forecast-skill gain or speedup; measure performance and runtime
separately. AfricaS2S and acmadDL can be supplied as resources in a comparison,
and equivalent implementations can satisfy the same scientific contract. A repair
variant can follow if a documented real failure is available. Controlled defect
injection belongs in evaluator calibration, not in the sourcing claim for a task.

These candidates probe different work within related scientific families. They
do not establish five independent task families or broad coverage of forecasting.

## First calibration exercise

Combine two sources of cases for **each** packaged task. Natural autonomous
attempts reveal mistakes, valid alternatives and recovery behavior we did not
anticipate. Constructed contrasts test specific evaluator weaknesses, including
rare but consequential errors a small pilot may never produce naturally.

Begin with one inexpensive-model attempt per ready task, then two fresh repeats
per task within the agreed total cap: a target of nine natural attempts across
the three tasks once all are runnable. Keep the initial model, framework,
substrate and task versions fixed. Each repeat starts with a fresh conversation,
empty retained state and no judge feedback. Record provider sampling settings
and seeds when supported; fresh runs do not imply reproducible randomness. Do
not coach a run into making an intended error or discard unexpectedly good
solutions. Additional models can follow only if the first batch lacks useful
variation and budget remains. This pilot gathers diagnostic examples, not model
rankings or population success-rate estimates.

Run with `--judge none` initially to collect attempts, deterministic checks and
replay without automatically purchasing model judgments. Review all first
attempts, including incomplete and stopped runs, before selecting the repeat
batch. Budget exhaustion is a recorded run condition, not grounds to erase a
failure or label its scientific calculations wrong. Reserve part of the agreed
cap for later judgments; retries and unsuccessful calls count toward that cap.

Prefer subscription-backed Codex for the first natural attempts. The local CLI
is already authenticated through ChatGPT; `codex exec` can reuse that login and
emit JSON event records. A separately billed API key is not a prerequisite for
that route. Use fresh task contexts without this development conversation,
reference answers, constructed-case expectations or judge feedback. A lightweight
model is appropriate for these task attempts, while task and evaluator design
remain under substantive review.

Distinguish task-solving runs from subagents helping build the benchmark. Current
conversation subagents share the workspace, so giving one a task does not by
itself establish the benchmark's information boundary. A Codex integration must
route scientific tools through the isolated runtime to establish trusted
execution. Exploratory submissions made outside that integration can still help
calibrate evaluation when their original integrity is explicitly unresolved;
do not silently count them as complete trusted benchmark runs. Prefer separate
Codex runs with retained JSON event logs when a complete exported trace is
needed. The command driver currently records protocol events but does not yet
provide this Codex integration.

| Task | Natural attempt readiness | Initial constructed contrasts |
| --- | --- | --- |
| `acmad-objective` | Supplied-input development execution is supported; configure the Codex integration using the existing subscription login. | Equivalent combination, incorrect missing support or weighting, unsupported interpretation, cached replay, missing manifest. |
| `seasonal-calibration` | Agent acquisition transport is still blocked. Preflight controlled provider or raw-response replay access before launching the full task. | Different valid calibration methods, held-out leakage through preprocessing or selection, incorrect seasonal units or dates, refitting during saved-fit prediction, a justified negative result. |
| `wvg-definition-audit` | Supplied-input numerical execution is supported; freeze the literature passages promised by the prompt before interpreting research failures. | Equivalent index implementation, wrong geometry or weighting, incorrect baseline or standard deviation, unsupported forecast-skill claim, an accurate account of curator choices. |

Resolve readiness gaps as development work and retain them in the exercise
record. A seasonal processing-only example may help test the evaluator meanwhile,
but it is not a natural attempt at the full acquisition task. Extend the same
exercise to each candidate as it becomes a packaged task; do not invent runs or
task versions for the two briefs.

Use the existing `acmad-objective` fixture as an intake example, then build the
following contrasts. These are proposed reviewer expectations, not completed labels.

| Case | Construction | What evaluation should distinguish |
| --- | --- | --- |
| Existing fixture | Review its code, calculations, report and recorded execution. | Passing static checks does not alone establish full scientific completion. |
| Equivalent implementation | Independently implement the same specified combination with the same allowed inputs. | Correct scientific behavior should not depend on the author's implementation. |
| Missing-support defect | Replace all-missing cells with climatology while leaving the report plausible. | Incorrect support handling must fail the relevant numerical requirement. |
| Unsupported conclusion | Preserve correct arrays but claim verified forecast skill or exact member pooling. | Numerical correctness can coexist with a failed interpretation outcome. |
| Cached-output replay | Make replay copy the submitted result files without recomputing them. | Matching outputs does not establish a reusable computational workflow. |
| Missing required manifest | Omit a required manifest while retaining inspectable calculation evidence. | Contract failure and the supported scientific outcomes remain distinguishable. |
| Evaluator outage | Preserve a reviewed submission but make the evaluation runtime unavailable. | Assessment unavailability is different from submitted code failing in a working runtime. |

The available seed is
`20261002T135026-acmad-objective-harness-fixture-05ac4c`, a submitted
`harness_fixture` for review-0.3. Its frozen files match `artifacts.json`, current
static checks pass, and stored completion is pending. Its artifact-manifest
SHA-256 is `34de6c582ec87fdf4f23264bf6c495de8028a9878132bbcf9949562c66449a3f`.
It is neither an expert-approved complete solution nor an agent capability result.

The combination task cannot calibrate every proposed capability. Add seasonal
examples with different valid calibration methods, fold leakage, and honest negative results,
and candidate examples that exercise source interpretation and substantial code
adaptation. Acquisition can remain explicitly unassessed when examining seasonal
processing examples; those examples do not complete the acquisition task.

## Monitor traces and retain process evidence

Trace monitoring is part of the calibration exercise. Preserve the initial
request, model responses exposed by the provider, tool requests and results,
exit statuses, timing, stop reasons, usage and adapter diagnostics alongside the
frozen submission. Do not require access to undisclosed model reasoning. The
built-in driver already writes model/tool events to `logs/events.jsonl`; command
adapters record protocol events but must additionally retain their visible model
conversation to support the same analysis. Missing, truncated or malformed
records leave the affected behavior unknown rather than proving it never happened.

Observe live runs without steering their scientific choices. If a human supplies
a hint, modifies files, changes data access or rescues execution, record the event
and mark the attempt as assisted. Passive observation remains autonomous;
unrecorded intervention would invalidate that comparison. Stop a malfunctioning
run when necessary and retain its partial evidence and stop reason.

For each reviewed case, make a short trace timeline with event IDs: what sources
or substrate the agent actually inspected, how it interpreted requirements,
where it introduced a consequential mistake, which checks it ran, whether it
noticed and repaired an error, and what evidence supported its final claims.
Link these events to artifact-level findings. Command text alone does not prove
that a source was read, a branch executed or a scientific result recomputed.
The existing substrate-use summary is useful navigation, not sufficient evidence
of understanding or execution by itself.

Allow relevant trace evidence to support judgments about actual execution,
source engagement, validation boundaries and recovery. Assess final scientific
correctness from the submitted work and independent checks: a repaired mistake
does not make the final answer wrong, and a convincing narrative does not make
incorrect arrays right. Keep unsupported process claims unresolved. Human review
uses both artifacts and traces, with reasons identifying the evidence used.

The current autojudge packet contains submission artifacts and controller checks,
but not the raw agent trace. Preserve that baseline. To test trace-aware judging,
create a separately versioned evidence policy with bounded, cited event excerpts
and explicit omission/truncation indicators. Include all relevant competing
evidence rather than selecting only passages that support a desired label. Omit
model identity, spending, human labels and controller-private targets; prevent
agent prose from being treated as judge instructions. Compare artifact-only and
trace-aware judgments on the same frozen cases and report policy fingerprints.
Do not silently change the existing score or reward verbose reasoning as an
extra scientific outcome.

## Review and compare judgments

Preserve each case's source, modification, task version, artifact hashes and
execution evidence and trace coverage. Distinguish natural attempts, constructed
cases and harness fixtures in every record. Keep calibration copies and records under ignored local
state, such as `var/calibration/`, without modifying original runs. Human labels
and reference answers stay outside the model judge's evidence packet.

For each criterion, record a human judgment of satisfied, partially satisfied,
failed, unresolved, or not applicable, with an artifact citation and reason.
The coding agent assembles the cases, calculations and evidence; Ezekiel reviews
and labels them before seeing the model judgment. Treat these as single-reviewer
development labels. Agent-generated explanations and checks are supporting
evidence, not an independent human review. Leave uncertain scientific questions
unresolved rather than forcing a label. No second human reviewer is required to
proceed with local calibration.

Run deterministic checks first, then compare model judgments and aggregation
against the reviewed labels. Record disagreements at the criterion level:
false acceptance, false rejection, unnecessary abstention, unsupported certainty,
or a task or evidence ambiguity. Distinguish an incomplete criterion from a
scientifically wrong one, even where both prevent completion under current rules.
Report unresolved cases alongside disagreement counts and denominators.

For example, full credit for a scientifically wrong outcome established by
review is false acceptance. Rejecting a reviewed equivalent implementation is false
rejection. Awarding full credit where the supplied evidence cannot establish the
claim is unsupported certainty. A disagreement between Ezekiel and the coding
agent first needs an evidence review; it is not automatically an evaluator error.

Inspect the evidence packet as well as the judge response. A missing code file,
truncated record, overly strict comparator, ambiguous contract or infrastructure
failure can explain a poor assessment. Judge prompting is only one possible fix.
Implement fixes with targeted regression cases and preserved policy fingerprints.
Check additional examples from a separate implementation or natural attempt,
reviewed by Ezekiel, before expanding; performance
on this small curated set is diagnostic, not a general grader-accuracy estimate.

When broader human evaluation is useful, the available group can independently
label a selected subset, with initial labels hidden, and resolve disagreements.
RCC consultation can then address specific seasonal-method questions. Keep that
later validation distinct from the present single-reviewer development results.

## Work order and cost control

First the coding agent prepares the evidence map and sharpens the two briefs
using the sources above; Ezekiel reviews the scientific requirements. Inventory
all three task versions, resolve acquisition and literature access gaps, and
configure a lightweight Codex task-solving system with recorded usage and bounded
attempts. Collect natural attempts and constructed contrasts across every task, with
traces and a criterion-by-criterion evidence sheet for Ezekiel to label. Run
deterministic checks first, then identify which disagreements require paid model
judgments and whether trace-aware evidence resolves them. Compare the evaluator
and make the necessary corrections. In parallel with that source work, pin one
matched seasonal reproduction for the richer calibration cases; bring it in
before generalizing the reporting or evaluator interfaces. Package new tasks
once their source, data and evidence requirements are resolved, following
the existing [task authoring process](task-authoring.md).

Reuse existing artifacts and local checks for the first exercise. Small,
inexpensive task-solving models supply the natural attempts in this cycle;
their outputs still require review by Ezekiel. Keep task design,
reference validation and assessment-method decisions under substantive scientific
review by Ezekiel, supported by source audits and reproducible checks. The
economy-model preference applies to task-solving pilots, not drafting the plan or
substituting cheap-model judgments for scientific review. Pin evaluator
configurations and record every paid judgment and retry.
Set per-run and total spending limits before paid pilots. Record allocation,
spend and reserved remaining allowance across runs; independent per-run limits
alone do not enforce a suite total. The first pilot's agreed hard cap is **$10
total**, including retries and paid judgments. Initially allocate $7 to task
attempts and $3 to judgments, with at most $0.75 per natural attempt. Nine such
attempts would reserve $6.75; do not automatically recycle unused allowance into
more calls. If the caps prevent useful attempts, report that limitation and
adjust the remaining experiment within the $10 total. Before each launch,
reserve its maximum cost against the remaining allowance and reconcile recorded
usage afterward; a missing cost record keeps its reservation outstanding. The
local pilot manifest is `var/calibration/pilot-plan.json`.

For subscription-backed attempts, record authentication route, model, tokens
when available, elapsed time and limits reached. They consume the subscription's
allowance; they are not cost-free inference. Record separately billed API spend
as zero when no API calls are made, and leave any unobservable allocated dollar
cost of subscription usage unknown. The $10 cap applies to separately billed
calls; do not buy additional credits or switch to API billing automatically.

For cost comparisons, also report **estimated API-equivalent inference cost**:
sum each observed token category multiplied by its applicable per-million-token
rate, divided by one million. Separate uncached input, cached input, cache writes
when applicable, and billed output. Count reasoning within billed output without
adding it twice. Include all task-solving calls, delegated agents and retries;
report evaluator-model costs separately from solver costs. Pin the exact model,
pricing date, source and pricing basis, including relevant service-tier and
context-length rules. Use a common declared API pricing basis for subscription
runs, rather than claiming it is the subscription's actual marginal bill.

Retain raw usage records and avoid summing cumulative counters repeatedly.
If the exported Codex trace omits a price-relevant category, report the assumption
or a cost interval; do not silently record an unknown cache-write count as zero.
Missing model rates or token usage leave the corresponding estimate unresolved.
Keep tool/compute charges and wall time alongside the inference estimate.
The [official usage guide](https://developers.openai.com/api/docs/guides/agents-api/observability)
and [caching guide](https://developers.openai.com/api/docs/guides/prompt-caching)
describe these accounting distinctions; freeze the applicable
[pricing schedule](https://developers.openai.com/api/docs/pricing) for the pilot.

Writing this plan launches no model attempts,
chooses no provider model, and schedules no study.
