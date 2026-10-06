# A generic assessment format for the 25 task templates

Status: proposal agreed in outline on 6 October 2026 and revised the same day
after a five-point review, then revised again after a review of eight design
points (see "Two reviews changed the format" at the end). Product mode, outcome
mode with both levels, and process mode are implemented in the `assessment/`
package and proven on three templates; see "All three modes are implemented"
below. A pinned judge, Claude Opus 5.5, now decides the questions no
computation can settle. The process checklist is a draft from a secondary source and is not
signed off. The evaluator for the ten packaged
tasks (`weatherbench/evaluation.py`, `weatherbench/judge.py`, the per-task
`rubric.yaml` files) is unchanged and its lock still verifies. The companion
list of tasks is [the proposed starting set](task-set.md).

## The document answers one question, stated twice

**In plain terms.** How do we mark an agent's forecasting work so that the mark
is exact, catches the subtle mistakes a forecaster would catch, checks that the
agent followed the required method where a standard exists, and still lets the
agent solve the problem its own way?

**In technical terms.** What single declarative specification, written once per
task template, lets a controller (a) decide deterministically whether a
submission is correct under any defensible convention, (b) say which known
errors the submission is consistent with when it is not, (c) verify conformance
to a published forecasting standard where the task requires one, (d) assess
whether the agent's interpretation is supported by its evidence, and (e) score
forecast skill, without prescribing the agent's language, file layout or
intermediate steps?

## The document uses these terms

- **Task template, instance, brief, Level 1, Level 2.** Defined in
  [the task set](task-set.md). Level 1 is "produce a valid output". Level 2 is
  "optimize it", scored as skill on a leaderboard.
- **Envelope.** The small fixed set of things every submission must contain,
  whatever the task.
- **Spec.** The assessment specification for one task template: a short
  declarative file plus one reference function. Every spec has a version.
- **Reference function.** Controller code that computes the correct results for
  an instance. It takes the instance parameters and a set of conventions, so it
  can compute the answer under each defensible reading of the brief.
- **Convention.** A choice the brief leaves open and that changes the numbers,
  such as whether negative daily rainfall increments are clipped to zero.
- **Pitfall.** A known wrong way to do the task, such as summing cumulative
  rainfall as if it were daily rainfall. A pitfall has a name and a computable
  wrong answer.
- **Results store.** The Zarr store (format version 3) in which a submission
  delivers its arrays. Every array carries named dimensions, and every dimension
  carries a coordinate array of labels.
- **Probe.** A rerun of the agent's own code on data the controller has
  changed, to observe behaviour instead of reading code.
- **Episode.** One run of one system on one instance. A second episode may be
  given the first episode's submission.
- **Conventions sheet.** An optional page that states a task's accepted
  conventions. Handing it to the agent is an experimental condition.
- **Decision point.** A feature deliberately present in an instance where the
  standard requires a judgement, and where the right judgement shows in the
  output.
- **Standard.** A published document that defines correct practice. The first
  two are named in "Two WMO documents are the first standards" below.
- **Judge.** A language model that answers one narrow question about cited
  evidence. It returns pass, fail or unresolved, and must quote the exact text
  it relies on. The pinned judge is Claude Opus 5.5.
- **Pass, fail, unresolved.** The three outcomes of every check. *Fail* means
  the submission is at fault. *Unresolved* means a cause outside the submission
  left the question open. The two are never merged.
- **Blocked.** A check that cannot be made because an earlier part of the same
  submission is broken. A blocked check fails and names the part.
- **Error bound.** The largest difference that rounding can produce between two
  correct implementations. Each tolerance is such a bound.
- **Controller.** The trusted benchmark harness that launches the agent, holds
  the private references and runs the checks.

## The agent delivers a small fixed envelope and is free in everything else

**The envelope has four parts.** A results store, an `answer.json` file, one
command that regenerates the results from the data, and a free-form report.
Language, method, file layout and intermediate steps are not constrained. The
text every agent receives is [`assessment/envelope.md`](../assessment/envelope.md).

**Arrays are delivered in `results.zarr`, a Zarr store of format version 3.**

- Each array is stored under the name the brief gives it, on the dimension
  names the brief gives.
- Each dimension has a coordinate array of the same name that holds its labels.
- The controller matches each array to its own by dimension name and by label.
  The order of the dimensions and the order of the labels are the agent's to
  choose.
- `xarray.Dataset.to_zarr(path, zarr_format=3)` writes exactly this layout.

**The labelled store replaced nested lists in `answer.json` on 6 October.** One
earlier agent attempt failed because a nested list gave no way to tell which
axis was which. A labelled array removes that question instead of answering it
case by case. What remains open is only what a name can settle, so each brief
states the array names, the dimension names and the unit.

**Tables will be delivered as Parquet, and as GeoParquet where they carry
geometry.** No current template returns a table, so this is not implemented.

**`answer.json` has five sections.**

- `results` — any result that is a single number.
- `choices` — the conventions the agent used, as free text.
- `claims` — the conclusions the brief asks for. A claim made once per label of
  a dimension is keyed by that label.
- `method` — required only in process mode. One entry per named step: what was
  done, and a pointer to the file and function that did it.
- `run` — the command that regenerates the results.

**The run command is what makes probes possible.** The controller substitutes
an input directory and an output directory and runs the command offline, on
changed data for the same task.

**The task's parameters may be written into the code.** The command must read
the data from the input directory. It need not read the dates, the region or
the years from there. Reuse on another instance is measured by a second
episode, described under "A second instance is a second episode" below, and is
not demanded of every submission.

**The agent no longer keeps provenance paperwork.** The provenance file with
per-file hashes, the handoff file and the retained-file manifest are removed
from the envelope. In the development runs these caused failures that had
nothing to do with the science, such as a stale hash on a report and an
unwritable output path.

**The controller keeps the provenance instead.** For every run the controller
records the identity and hash of each input, the version of each data source,
the hash of each submitted artifact at the moment of freezing, every command
the agent ran, and the full tool trace. Where the agent downloads data itself,
the controller's acquisition tool logs each request and the bytes returned.
These records exist to investigate discrepancies. An administrative mistake by
the agent cannot fail a check, because the agent no longer writes the records.
The harness already keeps most of them (`artifacts.json`, the task snapshot,
`logs/events.jsonl`, the lock fingerprint).

## Each task declares one of three modes

Columns:

- **Mode** — the name used in the task set.
- **What Level 1 requires** — what must hold for a pass.
- **How prescriptive** — how much of the method the assessment fixes.
- **Typical rows** — rows of the task set that use the mode.

| Mode | What Level 1 requires | How prescriptive | Typical rows |
| --- | --- | --- | --- |
| Outcome | A valid submission: correct format and units, forecast and target times aligned, complete coverage, and the leakage probes passed | Not at all; any method | 15, 23 |
| Product | The requested quantity, correct under some accepted combination of conventions | The product is fixed; the method is free | 1–9, 16, 24, 25 |
| Process | Everything in product mode, plus conformance to a named standard | The method is fixed by the standard | 10–14, 17–22 |

Interpretation checks (defined below) apply in every mode.

## Level 1 and Level 2 are separate submissions with separate gates

This is the default, confirmed on 6 October 2026.

**The two levels measure different capabilities, so they take different
submissions.** At Level 1 the agent submits the output the brief asks for; on a
process row that is the standard-conformant forecast. At Level 2 the agent
submits a separate optimized forecast, made by any method.

**The Level 2 submission has its own validity gate.** It is assessed in outcome
mode: correct format and units, forecast and target times aligned, complete
coverage, and the leakage probes run on the optimized code. This gate, not the
Level 1 result, is what keeps an invalid or leaked forecast off the
leaderboard.

**A valid Level 2 score is always reported.** It is reported when Level 1
failed, and it is reported when Level 1 is unresolved. Following a required
procedure and producing skilful forecasts are distinct capabilities, and the
benchmark shows both.

**The optimized forecast does not have to satisfy the standard.** Requiring
that would measure "improve within the standard", which is a different and
narrower capability.

**The Level 1 result is shown beside the Level 2 score, not used to hide it.**
A system that forecasts well but cannot follow the standard is a real finding
about that system, and gating would conceal it.

**A process row therefore reports three things per system.**

1. The Level 1 result of the conformant submission: pass, fail or unresolved,
   with any conformance failure recorded.
2. The skill of the conformant forecast itself, wherever that forecast passes
   the same validity gate on its own. A forecast can be valid and scoreable
   while its method fails conformance.
3. The skill of the optimized forecast.

The difference between items 2 and 3 answers "did optimization beat the
standard method in this agent's own hands".

**"Optimization within the standard" is a separately named track.** It
requires the optimized forecast to pass the process checks as well. It is not
part of the default, and its scores are never mixed with the default
leaderboard.

## Every check returns pass, fail or unresolved

**Fail means the submission is at fault.** There are three ways.

1. *A demonstrated defect.* A wrong number, a leak shown by a probe, a claim
   contradicted by recomputation, or a quoted passage that breaks a
   requirement.
2. *A missing piece the brief asked for.* A claim not stated, a method entry not
   given, or a method pointer that names no place in the submission.
3. *A blocked check.* The check cannot be made because an earlier part of the
   same submission is broken. It fails, and its record names that part in
   `blocked_by`. A submission with no usable answer fails the envelope, and
   every check that rests on the answer fails with it.

**A correct result is never failed for a fault elsewhere.** When one array is
unusable, the checks that need it fail, and every other check is assessed on
its merits. An earlier version of this rule left blocked checks unresolved
with a reason `not_assessed`. That code is retired: a broken submission is a
failure, not an open question.

**Unresolved is reserved for causes outside the submission.** Each unresolved
outcome carries a reason code:

- `infrastructure` — the controller could not run the check, or the runtime
  crashed before the command wrote its results, or the judge could not be
  reached.
- `ambiguous_clause` — the standard or the brief can be read two ways.
- `ambiguous_variant` — the numbers fit both an accepted convention and a
  pitfall, and the probe that would separate them could not decide.
- `unknown_answer` — the numbers match no listed combination, and no reviewer
  has ruled on them yet.
- `invalid_citation` — the judge's quotation does not appear in the cited file,
  so its verdict is discarded.
- `missing_evidence` — the controller's own record is absent, or the judge was
  not shown enough to decide.
- `judge_not_run` — the question needs the judge and no judge was run.

**The headline outcome counts every check.** It is pass only when every check
passes, including the checks a judge decides. It is fail when any check fails,
and unresolved otherwise. Two components are reported beside it:
`computed_outcome`, which leaves out the judge's checks, and `judged_outcome`,
which holds only those. Unresolved runs are reported in their own column and
are never counted as failures.

## The spec draws on seven check types

Columns:

- **Check type** — the name used in a spec.
- **Question it answers** — what the controller decides.
- **Decided by** — whether computation or a judge decides it.
- **Modes** — where it is used.

| Check type | Question it answers | Decided by | Modes |
| --- | --- | --- | --- |
| Variant match | Which combinations of conventions are the results consistent with? | Computation | Product, process |
| Invariant | Do the results obey rules any valid answer must obey? | Computation | All |
| Probe | Does the agent's code behave correctly on changed inputs? | Computation | All |
| Claim check | Do the stated numbers and sample-level conclusions match what the controller recomputes? | Computation | All |
| Interpretation | Is each stated conclusion supported by the evidence, and do the report, captions, structured answer and code agree? | Judge, on cited evidence | All |
| Process conformance | Was each step the standard requires actually carried out? | Computation where possible, judge otherwise | Process |
| Skill | How good are the forecasts against private observations? | Computation | Outcome (Level 2) |

### Variant matching accepts reasonable answers and narrows down the wrong ones

**The reference is a function, not a stored answer.** It computes the results
for any combination of conventions.

**The spec labels each convention value.** A value is either *accepted* or a
named *pitfall*.

**The controller computes every combination and reports the set the answer is
consistent with.** A numerical match supports a diagnosis; it does not prove
one. Different implementations can produce identical numbers, and two
conventions can coincide on a given instance. Clipping and keeping negative
rainfall increments give the same totals whenever no negative increment
occurs.

**The outcome follows from the consistent set.**

- Only accepted combinations: pass.
- Only pitfall combinations: fail, reported as "consistent with" the named
  pitfalls.
- Accepted and pitfall combinations together: the controller looks for a change
  to the data under which the two give different numbers, and reruns the
  agent's code on it. An injected negative increment separates clipping from
  keeping. Rain that grows away from the equator separates a weighted regional
  mean from an unweighted one. If the rerun passes and no data change separates
  the two, the check passes with an `ambiguous_variant` flag: the results are
  correct for this instance, and which reading the method follows is recorded as
  undetermined. If the rerun could not be made, the check is unresolved.
- No combination: unresolved, with reason `unknown_answer`.

**The match is compared with the agent's declared `choices`.** A disagreement
is evidence that the agent did something other than it said. It is reported and
passed to the interpretation check; it is not treated as proof.

This mechanism would have settled a real dispute. In the earlier benchmark,
three frontier-model answers were marked wrong because the brief did not say
whether to clip negative rainfall increments; both readings are defensible
(`weather-skills-bench/results/rainfall-semantics-audit.json`).

### Invariants and probes are blind to method

**Invariants are properties of any valid answer.** Examples: probabilities sum
to one; fine-grid rainfall conserves the coarse total; a station with no valid
reports has an undefined score, not a zero.

**Probes observe behaviour.** Every probe reruns the agent's command on the
same task. There are three shapes.

1. *Replay.* The command regenerates the submitted results from the original
   data.
2. *Changed data.* The controller changes the data. The results must change to
   match an independent recomputation. A stored answer fails here.
3. *Invariance.* The controller changes one part of the data that a valid
   method must not use, and a named part of the results must not move. A
   forecast must not move when later model forecasts change. A cross-validated
   forecast for a year must not move when that year's own observation changes.

**No probe changes the task's parameters.** An earlier version reran the code
on another instance and failed a submission that could not follow. That demand
is gone; see "A second instance is a second episode".

### Claim checks establish sample facts and nothing more

**The controller recomputes what the agent reports.** A reported skill score is
recomputed from the submitted forecast files and the private observations. A
claim such as "method A has lower error than method B on these cases" is
checked against the recomputed scores.

**Recomputation has a hard limit.** It can establish that A has lower error
than B in this sample. It cannot establish that the difference is statistically
significant, that a stated cause is the cause, or that the result will hold
elsewhere. Those belong to the interpretation check.

**A conclusion the evidence cannot support must be marked inconclusive.** A
correct negative or inconclusive result passes.

### Interpretation checks keep a narrow judge available in every mode

**Each spec lists interpretation obligations.** An obligation is one narrow
question about the agent's reasoning. The standing obligations are:

- *Statistical support.* Does any claim of significance or uncertainty respect
  the dependence in the data, such as overlapping valid dates and neighbouring
  cells?
- *Causation.* Does the report attribute a physical cause that the evidence
  cannot establish?
- *Generalization.* Does the report extend a result beyond the sample, region
  or period it was computed on?
- *Consistency across artifacts.* Do the report, the figure captions, the
  structured answer and the code say the same thing?
- *Source attribution.* Does the report correctly separate what comes from the
  data source, from the standard, and from the agent's own choices?

**A task adds its own obligations where needed.** The station task, for
example, requires that curator-constructed faults are not described as real
observation outages.

**Each obligation is one question, decided on exact quotations.** The judge
returns pass, fail or unresolved, and says what the verdict rests on.

- A pass quotes the passage that shows the requirement is met.
- A fail quotes the passage at fault, and the passage it contradicts where the
  fault is a contradiction.
- Where a requirement only restricts what a report may claim, a report that
  says nothing on the subject passes without a quotation.
- Where a requirement demands a statement, a report without it fails without a
  quotation.
- A quotation that does not appear in the cited file voids the verdict and
  yields `invalid_citation`. White space is ignored in the comparison. The
  judge is asked once more for a voided verdict, and only for that one.

**The judge is pinned and its identity is recorded.** It is Claude Opus 5.5
(`claude-opus-5-5`) at high effort, with a fixed prompt
([`assessment/judge-prompt.md`](../assessment/judge-prompt.md)), no tools and a
fixed reply schema. The model, the effort, the prompt, the obligations and the
schema are hashed into a judge identifier that every judgement carries. One
request covers all the questions of one run.

**The judge sees text, never raw arrays.** It is shown the brief, the report,
`answer.json`, the submitted code, and a controller-written summary of each
array: its dimensions, shape, minimum, mean and maximum. It is not shown the
controller's findings, so a failed numerical check cannot be counted twice.

**The judge has its own control cases.** Twelve small submissions, each with one
planted defect or none, are kept in
[`assessment/calibration.py`](../assessment/calibration.py) with the verdict
each must receive. They cover the five obligations, the method-statement
question and the required-statement question. The pinned judge returned the
expected verdict, with valid quotations, on 12 of 12. The record is
`assessment/judge-calibration.json`, and a test fails when it was made by
another judge identifier. Twelve cases written by the same author as the prompt
show that the judge can apply the questions. They do not measure its agreement
with a domain scientist.

**The same form was used in the two station studies of 6 October.** A judge and
the agent-reviewed references agreed on 28 of 28 cases, including cases where a
caption contradicted a correct report and where a bootstrap never recomputed
its statistic. Those studies used one parent submission and no human labels.

### Process conformance checks the method against a standard

**The spec holds a checklist extracted from the standard.** Each step cites the
clause it comes from.

**Each step is verified by the most exact evidence available.** In order of
preference:

1. *Required intermediate product.* The standard's steps produce defined
   things, such as a cross-validated hindcast set or a skill map. The envelope
   requires them as named results, and variant matching or invariants check
   them.
2. *Probe.* A rerun on changed inputs shows whether a step was really done,
   such as model selection inside the validation fold.
3. *Trace.* The controller's tool log shows the order of operations, such as
   choosing the model before any verification score was seen.
4. *Method statement.* The agent's `method` entry points to the file and
   function for the step. The judge decides whether that function does what the
   clause requires, under the same quote rule and three outcomes as an
   interpretation obligation.

**A missing method entry fails; an unclear clause is unresolved.** The brief
asks for each method entry by name. An entry that is absent, or whose pointer
names no place in the submission, is the submission's omission and fails. A
step also fails when the cited code does something the clause forbids, or when
a probe shows the step was not done. A clause that can be read two ways is
unresolved.

**Scientific reasoning is also tested through decision points.** An instance is
built so that the standard demands a judgement whose result is visible in the
output. Examples: a region where the model has no skill, where the forecast
should revert to climatological probabilities; a hindcast with fewer ensemble
members than the real-time forecast, which changes how calibration must be
done. Two existing tasks already work this way: the station with no valid
midnight reports, and the rainfall predictor whose units cannot be resolved.

### Skill is the Level 2 score

**The controller scores frozen forecasts against private observations.** The
score is relative to a declared baseline. Any method is acceptable.

**The gate is the validity check on the Level 2 submission itself.** See
"Level 1 and Level 2 are separate submissions" above.

**The budget is fixed.** Compute, tokens and the number of feedback queries are
the same for every system, and the feedback tool
(`weatherbench/feedback.py`) already enforces a query limit.

## A product-mode spec looks like this

This is illustrative. The working spec is
`templates/kenya-forecast-revision/spec.yaml`.

```yaml
template: kenya-forecast-revision
spec_version: 2
mode: product
params: [issue_current, issue_previous, rectangle, period_start]
claims_by: period
results:
  period: {kind: coordinate, dtype: date}
  latitude: {kind: coordinate, tolerance: {precision: float32, operations: 1, magnitude: 180}}
  change_mm: {dims: [period, latitude, longitude], tolerance: {precision: float32, operations: 203, magnitude: 200}}
  regional_change_mm: {dims: [period], tolerance: {precision: float32, operations: 371, magnitude: 200}}
conventions:
  negative_increments:
    clipped: accepted
    unclipped: accepted
  rainfall_semantics:
    differenced_cumulative: accepted
    summed_cumulative: pitfall
  issue_alignment:
    same_valid_period: accepted
    same_lead: pitfall
supplements:
  conventions: conventions.md
invariants: [change_equals_current_minus_previous]
probes: [replay, changed_data]
interpretation: [consistency_across_artifacts, source_attribution, generalization]
```

## A process-mode spec adds a checklist

This is illustrative and predates the build. The working spec is
`templates/seasonal-rainfall-calibration/spec.yaml`, and its steps come from
`standards/wmo-objective-seasonal-forecasting/checklist.yaml`.

```yaml
template: seasonal-rainfall-calibration
spec_version: 1
mode: process
standard: wmo-1246
process:
  - step: forecast is objective and reproducible
    evidence: probe
    probe: replay
  - step: skill is estimated by cross-validation with all selection inside the fold
    evidence: probe
    probe: perturb_future_targets
  - step: calibration uses hindcasts consistent with the forecast system
    evidence: product
    result: hindcast_set
  - step: tercile categories use a stated reference period
    evidence: variant
    convention: reference_period
  - step: areas without skill revert to climatology
    evidence: decision_point
    result: probability
  - step: standard verification scores accompany the forecast
    evidence: product
    result: verification_scores
  - step: combination weights are justified before verification
    evidence: method_statement
interpretation: [statistical_support, generalization, consistency_across_artifacts]
```

## Two WMO documents are the first standards

**The WMO guidance on objective seasonal forecasting is the first standard.**
*Guidance on Operational Practices for Objective Seasonal Forecasting*,
WMO-No. 1246, 2020. Its stated good practices include a traceable, reproducible
and well-documented procedure covering model selection, bias correction,
calibration and downscaling; forecasts in probabilistic format; dynamical
models and multi-model ensembles as the primary basis; and adequate
observational records for verification and calibration. Record:
<https://library.wmo.int/records/item/57090-guidance-on-operational-practices-for-objective-seasonal-forecasting>.

**The WMO long-range verification standard is the second.** The Standardized
Verification System for Long-Range Forecasts is defined in the *Manual on the
Global Data-processing and Forecasting System*, WMO-No. 485. A companion
document for regional and national centres is *Guidance on Verification of
Operational Seasonal Climate Forecasts*:
<https://library.wmo.int/records/item/56227-guidance-on-verification-of-operational-seasonal-climate-forecasts>.

**Any written procedure from a regional centre can be added.** One checklist
serves every row that names the same standard.

**A draft checklist exists; the primary documents were not obtained.** The WMO
library did not serve WMO-No. 1246 to an automated request on 6 October 2026.
A WMO Secretariat presentation that summarises it was retrieved, and its
nine-point definition of an objective seasonal forecast is quoted in
`standards/wmo-objective-seasonal-forecasting/practices.md`. The checklist in
that folder turns six of the nine practices into eleven testable steps and
records why the other three, and the multi-model part of a fourth, cannot be
tested on one forecast from one model. The wording of every step is ours.

**Four things remain before the checklist can support a result.** Obtain the
primary documents and keep hashed copies. Replace each practice number with the
clause it comes from. Add any step the primary text requires and the draft
lacks. Have a domain scientist sign the checklist off.

## A spec is certified by five tests

1. **Two independent reference implementations agree, and every declared
   magnitude covers the data.** The first part is already the practice for the
   ten packaged tasks. The second part checks each tolerance's error bound: the
   largest reference value under an accepted reading must not exceed the
   magnitude the bound assumes.
2. **A known-correct solution passes every check.**
3. **Deliberately incorrect solutions are caught by the right check.** The set
   must include at least: a leak (caught by a probe), a cached output (caught
   by a probe), an overclaim on correct numbers (caught by the claim or
   interpretation check), a skipped process step, and a false method pointer
   (both caught by process conformance). Each must fail on its own check and
   pass the checks it does not violate. The existing constructed controls for
   the canonical correlation task follow this pattern for leaks and cached
   inference.
4. **The separability of every accepted–pitfall pair is measured and
   recorded, in tolerances.** For each pair the certification states on how
   many instances the two readings give different numbers on the submitted
   data, on how many more they differ on the controller's changed data, and on
   how many they differ on neither. It also states the smallest separation, as
   a multiple of the tolerance. A pair that coincides on some instances does
   not reject the spec. A pair that is not separable at all is listed as a known
   ambiguity.
5. **Several cheap-model attempts are run, and every unknown answer is ruled
   on.** The spec version is locked only after that.

Human scientific approval is a separate, later gate. Certification says the
spec is internally sound, not that the science is endorsed.

**The judge is certified the same way, by cases with known answers.** See "The
judge has its own control cases" above. Its record is kept apart from the
templates' records, because one judge serves every template.

## Unknown answers change the spec only through versioned adjudication

**An unknown answer is unresolved under the spec version that graded it.** It
is not silently accepted or rejected.

**A ruling creates a new spec version.** The reviewer decides whether the new
convention is accepted or a pitfall, records the reason, and the spec version
number increases.

**A comparison pins one spec version.** Every run in the comparison is graded
under that version. If a ruling arrives mid-comparison, either all runs are
regraded under the new version or none are. The deterministic checks make
regrading cheap.

**Earlier assessments are kept.** Each stays on record with the spec version
and lock fingerprint that produced it, as the current harness already does.

## The same spec applies to every system condition

**Checks do not change with the model, the harness or the substrate.** A system
using the Rhiza weather-skills catalog, the `acmadDL` or `AfricaS2S` libraries,
or the `rx` harness is assessed by the same spec as a system using none of
them. This is what makes the comparison of substrates fair.

**The envelope does not favour hand-written code.** The run command may call a
skill's command-line tool or a library workflow. The agent need not rewrite a
tool in its own code to be assessable.

**Every result carries the system's identity and its substrate use.** The run
record states the model, the harness, the substrate and its hash. It includes
the substrate-use record produced by `weatherbench/substrate_use.py` (pull
request #1): how many commands listed, read or ran substrate files, how many of
those runs failed, and the step at which the substrate was first touched. Use
is reported as a fact about the run; it earns no credit by itself.

**Every result carries its place in an episode sequence.** The run record
states whether the system started fresh or from a parent run, which parent, and
what state was retained. Cost, tokens and time are reported per episode, so
that a later episode on a new location can be compared with the same episode
run from a reset state.

## A second instance is a second episode

**The agent's code is not required to work on another instance.** The first
version required the run command to read the task's parameters from its inputs,
and reran the code on another region or period. A submission that could not
follow failed. That rule fixed how every agent had to structure its code, to
serve a question most runs never ask.

**Reuse is measured where it happens.** A run started with `--parent RUN_ID`
receives the earlier run's submission, code and results, under `/work/prior`.
The agent is told it may use it, adapt it or ignore it. The earlier run may be
another instance of the same task, the Level 1 run of the same instance, or a
run of another task. The system must be the same.

**The comparison is the same instance run fresh.** Cost, tokens, time and
outcome of the second episode are compared with a fresh run of that instance.
The run record states the parent and counts the commands that named the
earlier work.

**One power was given up.** A reading that gives the same results as the
accepted reading on the task's own instance, for any data, is no longer failed
in that episode. An earlier attempt set category boundaries from all years. On
an instance with eight training years that reading and the correct one give
identical categories whatever the observations are, and the changed-instance
rerun had exposed it on other years. Under the present rule the results pass
on that instance with the flag `ambiguous_variant`, and the same reading fails
on an instance where it changes a result.

## Supplied conventions are an experimental condition

**Conventions stay out of the brief.** A task whose brief lists the accepted
conventions tests whether an agent can carry out instructions. A task whose
brief states only the product also tests whether the agent knows, or finds out,
how the data are to be read. The second is the harder and more useful test, so
it is the default.

**A conventions sheet can be supplied, and supplying it is recorded.** A
template may hold a `conventions.md` that states each accepted convention as a
fact about the data or about the brief. It names no pitfall. A run started with
`--supply conventions` places the sheet in the task folder and adds one line to
the brief. The run record lists what was supplied.

**The sheet is one more thing to switch on and off.** It stands beside the
model, the harness and the substrate. The same instance run with and without
the sheet measures how much of a task's difficulty is knowing the conventions.
A "method supplied" condition works the same way.

## Each tolerance is an error bound

**A tolerance answers one question: how far apart can two correct answers be?**
Two implementations of the same calculation differ only by rounding. The
standard bound for a chain of `n` rounded operations on quantities no larger
than `m` is `n * u * m`, where `u` is the unit roundoff: 2⁻²⁴ in float32 and
2⁻⁵³ in float64. Two implementations can each be off by that much, so the
tolerance is `2 * n * u * m`.

**The spec declares `n`, `m` and the precision, and states where they come
from.** Float32 is assumed wherever the source data are float32, because common
tools keep that precision. Whole-number results such as categories must match
exactly.

**The bound is checked against the data, in both directions.**

- Certification fails when a reference value exceeds the declared magnitude.
- Certification reports how many tolerances separate each pitfall from the
  accepted reading. A pitfall separated by thousands of tolerances is caught by
  the numbers. A pitfall separated by less than one cannot be told from
  rounding, and needs a probe.

**The Kenya template shows why the second check matters.** The tolerance on the
regional mean is 0.0088 mm. Four pitfalls differ from the accepted
reading by at least 1,102 tolerances on every instance. The fifth, an
unweighted regional mean, differs by at most 0.62 tolerances on any
instance: the region lies within 6° of the equator, where the area weights are
equal to within 0.6%. The first version used a tolerance of 0.001 mm, chosen
by eye, and so failed answers for differences that float32 rounding can
produce. The submitted numbers cannot establish that pitfall here. The
changed-data probe can: the controller adds rain that grows away from the
equator, and the two readings then differ on 30 of 48 instances. On the
other 18, which span two or three rows next to the equator, the
readings stay within rounding of each other and are recorded as a known
ambiguity.

**The bound is a worst case.** Real float32 arithmetic is usually far closer
than the bound allows. A tolerance set this way gives up some sharpness in
exchange for never failing a correct answer.

## A result reports these things

- **Level 1:** the headline outcome, pass, fail or unresolved, with its computed
  and judged components; the set of convention combinations the answer is
  consistent with; each invariant, probe, claim, interpretation and process
  outcome with its evidence, the part that blocks it where it is blocked, and
  its reason code where it is unresolved; the judge's identifier; cost, time and
  tokens; the spec version.
- **Level 2:** the validity-gate outcome; skill of the optimized forecast
  against each baseline; on process rows, the skill of the conformant forecast
  where it is independently valid; the Level 1 result shown beside it, whatever
  that result is; the feedback queries used.
- **Per run, in every case:** the model, harness and substrate; the
  substrate-use record; the supplements handed to the agent; the parent run,
  the retained state and the use made of the earlier work, if any.
- **Across instances:** counts of pass, fail and unresolved, and mean cost,
  over the same drawn instances for every system compared.
- **Across episodes:** cost, tokens, time and outcome for each episode in a
  sequence, for the retained condition and the reset condition.

## The format changes the first evaluator in six ways

- **The weighted rubric tree becomes a check list.** Today a failed check
  zeroes a rubric leaf worth 20 to 25 points. Under this format each check is
  reported on its own.
- **Per-task evaluator code shrinks to the reference function.** The probes are
  shared. `judge.aggregate()` no longer needs hard-coded task identifiers.
- **The judge stays in every mode, with a narrower job.** Today the judge rates
  whole rubric leaves from 0 to 2, and 25% to 100% of each task's weight waits
  on it. Under this format it decides single obligations and method pointers,
  each with a mandatory quote and three outcomes.
- **The three-outcome rule is kept, not introduced.** The current judge already
  returns null for unknowable ratings, and the current aggregation already
  separates pending from failed. This format extends that rule to every check.
- **Provenance moves from the agent to the controller.** See the envelope
  section.
- **The reference modules are kept.** They already compute from data; they need
  a conventions argument.

## All three modes are implemented, each on one template

**All three modes work end to end, each on one template.** The package
`assessment/` implements the envelope, three-outcome results, controller-held
provenance, the certification tests, and the checks for every mode. How to use
it is in [templates/README.md](../templates/README.md).

- *Product mode:* `templates/kenya-forecast-revision` (row 4 of the task set),
  with variant matching, invariants, two probes and claim checks.
- *Outcome mode with both levels:* `templates/weeks34-rainfall` (row 15), with
  a validity gate, skill scoring, and a development-feedback tool for Level 2.
- *Process mode:* `templates/seasonal-rainfall-calibration` (row 11), with an
  eleven-step checklist drawn from the WMO practices for objective seasonal
  forecasting.

**All three specs pass the four automatic certification tests in the offline
Docker runtime, at their current versions.** The fifth test rests on 4,
3 and 4 attempts by one cheap model under the current contract. No
domain scientist has approved any of them.

- *Kenya forecast revision, version 2.* Two independent reference
  implementations agree to 6e-14 over 64 convention combinations, and the
  first reproduces the earlier repository's answer key. 4 known-correct
  controls pass, among them one with its arrays in another order and one with
  the task parameters written into the code. 11 deliberately incorrect
  controls each produce the outcome built for them.
- *Weeks 3–4 rainfall, version 3.* Two independent implementations of the
  metric and its baselines agree to 1e-14 on eight instances, and the staged
  inputs and baseline scores equal those of the packaged task exactly. 5
  valid controls pass, including a raw-model forecast and a climatology
  forecast. 10 invalid controls each fail on the check built to catch them.
- *Seasonal rainfall calibration, version 3.* Two independent reference
  implementations agree to 3e-12 over 24 convention combinations on six
  instances, and reproduce the packaged task's reference arrays. 4
  conformant controls pass, including a climatological forecast. 10
  non-conformant controls each produce the outcome built for them, including a
  skipped cross-validation, a missing method statement and a false method
  pointer.

**No-model fixture runs exercise the whole path.** A deterministic system
solves an instance inside the tool sandbox, the controller freezes the
submission and writes the provenance record, and the probes rerun the code
offline. A Level 2 fixture also makes three development-score requests through
the feedback tool, each naming a Zarr store that the controller freezes before
scoring it.

**The outcome-mode validity gate has four parts.** It prescribes no method.

1. *Coverage and time alignment.* The forecast must list exactly the required
   issues and cells, each labelled with its own date and cell. Missing cases or
   mislabelled dates fail here.
2. *Units.* A magnitude rule compares the mean forecast with the mean observed
   total in training, and fails a forecast outside one fifth to five times it.
   This catches a 14-day total multiplied by 14 again.
3. *Leakage, part one: the forecast must come from the supplied data.* The
   controller changes the training observations and then the model forecasts.
   A forecast that moves under neither is hard-coded and fails. A climatology
   passes because it moves with the training observations; a raw-model forecast
   passes because it moves with the model forecasts.
4. *Leakage, part two: no information from the future.* The controller changes
   the model forecasts issued after a cut date. Forecasts issued before it must
   not move.

**Skill is reported whenever a forecast covers the required cases.** A forecast
that fails the gate still has its score recorded, with
`skill_valid_for_ranking` set to false.

**Level 2 adds two checks.** The controller's ledger must show no more
development-score requests than the limit. If the agent states a development
score, it must equal the controller's score of the submitted forecast; stating
`null` for "not measured" passes.

**Process mode evaluates each step of the standard from one kind of evidence.**

- *A step that rests on checks* takes the combined outcome of the probes or
  rules it names. Example: "no historical forecast for a year uses that year's
  observation" rests on a probe that changes one year's observation and
  requires that year's cross-validated forecast not to move.
- *A step that rests on results* asks whether the named results agree with the
  reference. It looks only at the conventions that can change those results, so
  a wrong month length fails "model forecast prepared" and leaves "observations
  prepared" passing.
- *A step that rests on a method statement* first checks, by computation, that
  the agent's pointer names a file and symbol present in the submission. A
  missing or false pointer fails: the brief asked for it. A pointer that
  resolves goes to the judge, who decides whether the code there does what the
  statement says.
- *A step only a judge can decide* goes to the judge. It enters
  `judged_outcome` and the headline, and not `computed_outcome`.

**A valid negative result conforms.** A climatological forecast, one third for
each category, passes every computed step.

**One ambiguity was found and closed with a required intermediate product.** A
climatological forecast has a skill score of zero whether or not the category
boundaries leak the held-out year, so the score alone cannot show which was
done. The brief now also asks for the observed category of each year. That
array differs between the two readings, so it settles the question for every
forecast. This is the format's first preference in practice: require the
intermediate product, before relying on a probe or a judge.

**Building it settled eight design points, and a review revised them.** The
first decisions were taken during the build. The owner reviewed all eight on
6 October 2026. The table gives both, and what is now built.

Columns:

- **Point** — the design question.
- **First decision** — what the build did.
- **Decision on review** — what the owner decided.
- **What is built** — the present behaviour.

| Point | First decision | Decision on review | What is built |
| --- | --- | --- | --- |
| 1. What the agent is told about conventions | Convention names are private | Keep them private; make supplied conventions a condition that can be switched off | An optional conventions sheet per template, handed over with `--supply conventions` and recorded with the run |
| 2. How reuse on another instance is tested | The run command must read the task parameters, and the controller reruns it on another instance | Too hard-coded; a later episode gets the old code and decides | No changed-instance rerun. A second episode starts with `--parent` and receives the earlier submission |
| 3. How arrays travel | Nested lists in `answer.json` | Use a modern format for geospatial arrays | A Zarr store, format version 3, with named dimensions and coordinate labels |
| 4. How long the Level 2 brief may be | About 90 added words | Length is not a constraint; one task may start from another's output | No cap on the addition. Level 2 starts from the Level 1 run with `--parent` |
| 5. Whether a judge runs | No judge; judge checks unresolved | Run a judge, of the Opus class | Claude Opus 5.5, pinned, one request per run, exact quotations, twelve control cases |
| 6. What a blocked check returns | Unresolved, reason `not_assessed` | A failed step fails, and what rests on it fails | A blocked check fails and names the part that blocks it. A correct result is not failed for a fault elsewhere |
| 7. How array axes are identified | By the order the brief shows | A labelled format removes the question; state what remains | Arrays are matched by dimension name and label. Briefs state names, dimensions and units |
| 8. Where a tolerance comes from | The data's resolution, by eye | Bound floating-point error; check with data | An error bound declared per result, checked against the data in certification |

**Certification measured how often readings coincide.** On the Kenya template
clipped and unclipped increments give the same totals on all 48 instances of
the submitted data, and differ on all 48 once the controller injects a dip. A
weighted and an unweighted regional mean agree within the tolerance on all 48,
and differ on 30 of 48 on the controller's changed data. The other four
pitfalls give different numbers on every instance. On the seasonal template the
full-sample category boundaries change a result on 4 of 6 instances; on
the two with eight training years they change nothing. Coinciding readings are
common, and the changed-data probe is necessary, not a refinement.

## One cheap model made the first 25 attempts

**This section and the next two record the first contract.** They mention
results in `answer.json`, the changed-instance probe and results grouped by
period. The present format has replaced all three; see "Building it settled
eight design points" above.

**Twenty-one attempts were run with one cheap model.** The model is gpt-6-luna,
driven through the existing Codex adapter on the subscription login, with the
verified command-line version 0.160.0. A typical attempt took one to two
minutes and 45,000 to 195,000 tokens. With four later attempts under spec
version 2, they used about three percentage points of the subscription's
weekly allowance. These are development
attempts: one model, one attempt per cell. They support no ranking.

**Seven attempts covered the three templates on the default runtime image.**

Columns:

- **Template and instance** — the task and the drawn parameters.
- **Level** — 1 is "produce a valid output"; 2 is "optimize it".
- **Computed outcome** — every check a computation decides. Judge checks were
  not run.
- **What the assessment found** — the checks that did not pass, or the skill.

| Template and instance | Level | Computed outcome | What the assessment found |
| --- | --- | --- | --- |
| Kenya revision, service area, weeks 1–2 | 1 | Fail | Named pitfall: each 7-day window is one day early. Every other check passed. |
| Kenya revision, central box, weeks 2–3 | 1 | Pass | — |
| Weeks 3–4 rainfall, final 2018–2021 | 1 | Pass | RMSE 14.233 mm, 0.3% better than climatology |
| Weeks 3–4 rainfall, final 2018–2021 | 2 | Pass | Used 5 of 5 score requests. RMSE 14.056 mm, 1.6% better than climatology. Its stated development score equals the controller's. |
| Weeks 3–4 rainfall, final 2015–2017 | 1 | Pass | RMSE 11.782 mm, 1.8% better than climatology |
| Seasonal calibration, 1993–2004 | 1 | Fail | One result, the forecast totals, has the wrong shape and is unusable. The cross-validation, observed totals, categories and skill score all pass. Both method pointers quote phrases, not code, and are unresolved. |
| Seasonal calibration, 1993–2002 | 1 | Fail | Named pitfall: daily rates were summed without multiplying by the days in each month. The new-year probabilities contain non-finite values. The cross-validation, categories and skill score pass. |

**The first Kenya diagnosis was confirmed by reading the code.** The submitted
script takes the cumulative total at the period start plus six days, minus the
cumulative total one day before the start. That is the seven days ending one
day early, which is exactly the pitfall the assessment named. The same pitfall
appeared in three of the nine Kenya attempts.

**A probe separated two readings on a real attempt.** On that Kenya instance
the weighted and unweighted regional means agree within tolerance, so the
numbers fitted both. The changed-instance probe reran the agent's code on an
instance where they differ, and the code followed the weighted reading.

## The first substrate comparison measured availability, not use

**Fourteen attempts compared three substrate conditions with everything else
fixed.** The model, the adapter and the budgets are identical. The runtime
images are the three matched images of the 1 October pilot: one with no added
substrate, one with the Rhiza Research weather-skills catalog, and one with
the ACCORD libraries (`africas2s`, `acmaddl`, `rosetta`). The wording that
tells the agent about its substrate is the pilot's. Each condition ran two
instances of the Kenya revision and two of the seasonal calibration. One extra
run per template started from the baseline condition's earlier submission, to
compare retained work with a reset.

Columns:

- **Task** — the template.
- **Condition** — the substrate, or "retained" for the run that started from
  earlier work.
- **Passed** — computed outcome over the two instances.
- **Median seconds and tokens** — over the two attempts.
- **Substrate use** — what the monitor recorded.

| Task | Condition | Passed | Median seconds | Median tokens | Substrate use |
| --- | --- | --- | --- | --- | --- |
| Kenya revision | Baseline | 1 of 2 | 61 | 102,726 | — |
| Kenya revision | Rhiza skills | 1 of 2 | 73 | 157,282 | Catalog never named; core library never imported |
| Kenya revision | ACCORD libraries | 2 of 2 | 56 | 154,534 | Notes folder read in both runs; no library imported |
| Kenya revision | Retained (second instance) | 1 of 1 | 159 | 81,904 | — |
| Seasonal calibration | Baseline | 2 of 2 | 199 | 124,988 | — |
| Seasonal calibration | Rhiza skills | 0 of 2 | 42 | 86,144 | Catalog never named; core library never imported |
| Seasonal calibration | ACCORD libraries | 2 of 2 | 161 | 97,440 | Notes folder read in one run; no library imported |
| Seasonal calibration | Retained (second instance) | 1 of 1 | 38 | 85,418 | — |

**No condition used its substrate's code.** Across eight substrate runs the
monitor recorded no import of any substrate library and no command naming the
skills catalog. The ACCORD condition read its notes folder in three of four
runs. This comparison therefore measured the availability of a substrate, not
its use, and the differences between conditions are not evidence about the
substrates. The 1 October pilot recorded the same thing for the skills
catalog.

**The two Kenya failures are the same pitfall again.** Both placed the window
one day early, and both scripts then crashed on the probe instance whose first
period starts on the issue date.

**The two failures in the Rhiza condition are agent errors, ruled on by
review.** One divides by a fixed climatological score that is half its true
value. The other codes near-normal and above-normal as the same category. Each
answer matched no listed reading, so each went to review, and the rulings are
recorded with their evidence in
`templates/seasonal-rainfall-calibration/rulings.yaml`. The rulings were made
by the coding agent from the submitted code and are marked as proposed until a
person confirms them.

**The retained runs were cheaper on one task and slower on the other.** On the
seasonal task the retained run took 38 seconds and 85,418 tokens, against 73
seconds and 100,717 tokens for the reset run on the same instance. On the Kenya
task the retained run passed where the reset run failed, used fewer tokens and
took three times as long. One pair per task shows that the mechanism works; it
does not measure an effect.

## The first attempts exposed eight defects in the controller

**The attempts exposed eight defects in the controller, and all eight are
fixed.** This is what the fifth certification test is for. Before the
fixes, eight of the fourteen comparison runs carried a failure that the
controller had caused; after them, every remaining failure has an agent error
behind it.

1. *The changed-data probe altered the store's format.* It rewrote the Kenya
   stores without their consolidated metadata, so an agent's valid reader
   crashed on the changed inputs and the probe reported a false failure. The
   probe now rewrites only the rainfall values, in place.
2. *One unusable result stopped the whole assessment.* An array with the wrong
   shape left every other check unassessed. The envelope still fails, and
   everything that does not need the unusable result is now assessed.
3. *The delivery contract did not say where the `method` section goes.* The
   agent put it under `claims`. The contract now lists it, and a `method`
   nested under `claims` is read as the same thing.
4. *A method pointer could be satisfied by a phrase.* A script that writes its
   own answer contains every phrase of that answer. A pointer must now be a
   name that appears in the file, or a line range inside it.
5. *Results grouped by period were rejected.* Two attempts gave each period its
   own block where the brief showed arrays over periods. The information is the
   same, so a spec can now declare such a grouping and the controller reads it
   as arrays. Claims given per period are read the same way.
6. *A crash in the runtime was blamed on the method.* The pilot's images crash
   inside a native library when a process that read NetCDF files exits. Four
   runs were first marked as failing every probe. A complete answer written
   before an abnormal exit is now used, and a crash by signal with no answer is
   unresolved with reason `infrastructure`.
7. *An unknown answer had nowhere to go.* A spec can now carry rulings keyed by
   the hash of the answer. A ruling of incorrect turns that answer's unknown
   outcome into a failure, with the reviewer's reason attached.
8. *`instance.json` exposed a parameter the brief does not explain.* The
   seasonal and weeks 3–4 instance files carried an internal cell-selection
   field. Three scripts guessed at its meaning and broke on a probe instance
   that set it. The field is gone in spec version 2 of both templates, and the
   seasonal file now lists its years in full. This changes what agents see, so
   attempts made under version 1 keep their version 1 assessments and are not
   assessed against the new inputs.

**Every run was assessed again after each fix that left its inputs
unchanged.** Each earlier assessment is kept beside the run under the
fingerprint that produced it. The tables above give the outcomes under the
final version 1 assessments.

**Four further attempts were run under spec version 2.** They are the attempts
the fifth certification test counts for the seasonal and weeks 3–4 templates;
`templates/*/certification.json` lists them.

- *Weeks 3–4 rainfall, final 2018–2021:* pass. RMSE 13.998 mm, 2.0% better
  than climatology.
- *Weeks 3–4 rainfall, final 2012–2014 on six cells:* pass. RMSE 10.890 mm,
  2.3% better than climatology. This is an instance that sets the field
  version 1 exposed.
- *Seasonal calibration, 1993–2004:* pass on every computed step.
- *Seasonal calibration, 1993–2000 on the southern rows:* fail, with a named
  pitfall. The category boundaries for each held-out year include that year.

**The last of these is the clearest catch so far.** On that instance the
leaking and the correct boundaries happen to give the same categories and the
same skill score, so the submitted numbers fit both readings. The
changed-instance probe chose an instance where the two differ and reran the
agent's code there; the code followed the leaking reading. The submitted
script confirms it: it computes boundaries from all years for the observed
category, two lines below a comment that says the boundaries exclude the
held-out year. A process step judged on the original numbers alone had passed
this attempt, so the steps now also take account of what the probes establish.

## The judge decided 106 questions on the first 25 attempts

**The judge was run over the recorded assessments, without recomputing them.**
The 25 attempts were made under the first contract, so their computed checks
stand as recorded under the rules then in force. The judge read each frozen
submission and decided the questions those assessments had left open: three
interpretation questions per run, and on the seasonal task up to three process
questions.

**The judge returned a valid verdict on every question.** 106 questions
went out in 25 requests. None came back unresolved, and none was
voided for an inexact quotation. The requests used 165,949 input tokens and
47,172 output tokens, which is $1.99 at list price. They ran on the
subscription login.

Columns:

- **Task** — the template.
- **Attempts** — the number of agent runs.
- **Computed pass** — runs in which every computed check passed.
- **Judged pass** — runs in which every judge question passed.
- **Headline pass** — runs in which every check passed.

| Task | Attempts | Computed pass | Judged pass | Headline pass |
| --- | --- | --- | --- | --- |
| Kenya revision | 9 | 6 | 7 | 6 |
| Weeks 3–4 rainfall | 5 | 5 | 3 | 3 |
| Seasonal calibration | 11 | 6 | 8 | 6 |

**The judge failed 7 questions, in 7 runs.**

- *Report and code disagree, four runs.* One Kenya report says the source is in
  kg m⁻² and its answer says metres. One Kenya report describes subtracting the
  value of "the preceding day", and its code subtracts the value one day before
  the period starts. One weeks 3–4 report says only targets that closed before
  the boundary are used, and its code filters on each target's start date. One
  Level 2 submission states a development score in `answer.json` that its run
  command rewrites as "not measured".
- *Uncertainty not stated in plain language, two runs.* Both seasonal reports
  explain probabilities in terms of calibrated members, residuals and terciles.
- *Calibration code does not do what its entry says, one run.* The regression
  is fitted on the ensemble mean, and the new years are then predicted from the
  sum over members.

**The judge changed the headline of two runs.** Both are weeks 3–4 runs whose
computed checks all pass and whose report contradicts its code or its answer.
The other five failures fell on runs that had already failed a computed check.

**One verdict found a defect the numbers had not isolated.** The run whose new
years use a sum over members had failed for another reason, a wrong skill
score. The probabilities for new years have no reference answer, so only the
judge's reading of the cited code showed the second fault.

**Every failure quotes the passages it rests on.** The quotations are in each
run's `assessment.json`, and the judge's raw replies are in
`controller/judgements/`. The author read the seven failures with their
quotations. Six are plain. The seventh, the "preceding day" wording, rests on
one reading of a sentence that can be read two ways, and falls on a run that
had already failed a computed check. That is one reader, not a validation.

## Eleven attempts were made under the revised contract

**The same cheap model attempted the three templates again.** These are the
attempts the fifth certification test counts. Each delivered a Zarr store, and
the judge ran with each. Eight are plain or sheet-supplied first episodes, and
three started from an earlier submission.

Columns:

- **Task and instance** — the template and the drawn parameters.
- **Condition** — plain; with the conventions sheet; a second episode on
  another instance, started from the plain run's submission; or Level 2,
  started from the Level 1 submission.
- **Headline, Computed, Judged** — the outcome and its two components.
- **Seconds, Tokens** — the agent's time and tokens. The judge is not included.
- **What the assessment found** — the checks that did not pass, or the skill.

| Task and instance | Condition | Headline | Computed | Judged | Seconds | Tokens | What the assessment found |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Kenya revision, central box, weeks 2–3 | Conventions sheet | Pass | Pass | Pass | 22 | 64,251 | — |
| Kenya revision, central box, weeks 2–3 | Plain | Pass | Pass | Pass | 44 | 59,844 | — |
| Kenya revision, service area, weeks 1–2 | Plain | Pass | Pass | Pass | 52 | 107,751 | — |
| Weeks 3–4 rainfall, final 2018–2021 | Plain | Pass | Pass | Pass | 34 | 74,774 | RMSE 13.994 mm, 2.0% better than climatology. |
| Weeks 3–4 rainfall, final 2015–2017 | Plain | Pass | Pass | Pass | 71 | 133,042 | RMSE 11.825 mm, 1.4% better than climatology. |
| Seasonal calibration, 1993–2004 | Plain | Pass | Pass | Pass | 60 | 57,843 | — |
| Seasonal calibration, 1993–2002 | Plain | Fail | Fail | Pass | 62 | 67,952 | Named pitfall: `full_sample`. |
| Seasonal calibration, 1993–2002 | Conventions sheet | Fail | Fail | Pass | 45 | 107,936 | Matches no listed reading; ruled incorrect on review. |
| Kenya revision, north-west box, weeks 3–4 | Second episode | Pass | Pass | Pass | 25 | 89,288 | 4 commands named the earlier work. |
| Seasonal calibration, 1993–2000, southern rows | Second episode | Pass | Pass | Pass | 33 | 121,183 | 3 commands named the earlier work. |
| Weeks 3–4 rainfall, final 2018–2021 | Level 2, from its Level 1 work | Fail | Fail | Fail | 42 | 155,533 | Failed: `claim.development_rmse_mm`. Judge failed: `consistency_across_artifacts`. RMSE 14.015 mm, 1.9% better than climatology. Used 5 of 5 score requests. 3 commands named the earlier work. |

**Three attempts failed, each for a fault in the agent's own work.**

- *Seasonal, plain.* The category boundaries for each held-out year include
  that year. On this instance that changes the categories, so the numbers show
  it and the assessment names the pitfall.
- *Seasonal, with the conventions sheet.* The sheet states the boundary rule,
  and this run follows it. Its skill score is wrong for another reason: the
  observed step is 1 above each category where it should be 1 at or below it.
  The answer matched no listed reading and went to review. Recomputing the
  score from the run's own probabilities with the inverted step reproduces its
  stated −0.807; the correct step gives 0.314. The ruling is recorded as
  proposed.
- *Weeks 3–4, Level 2.* The answer does not state the development score the
  brief asks for, and it describes a ridge penalty of 10 where the code sets
  0.01. Its forecast is valid and its skill is recorded.

**Both second episodes on a new instance passed, and both used the earlier
work.** The seasonal one ran on the eight-year instance, where its results
carry the flag `ambiguous_variant` described under "A second instance is a
second episode".

**Every submission was readable.** No attempt delivered an array on the wrong
dimensions, in the wrong order or with unreadable labels. Under the first
contract three of 25 attempts had a layout problem.

**These attempts support no comparison.** There is one attempt per cell. The
sheet-supplied runs and the second episodes show that the mechanisms work.
They do not measure what a conventions sheet or earlier work is worth.

## These parts are not implemented

- *Only one model has attempted the templates.* The Codex adapters accept only
  command-line version 0.160.0, whose isolation was verified. The default
  install has moved to 0.160.1, so the Codex systems added here name the
  0.160.0 binary, which is still on disk; the version check was not changed. No
  Claude model has run as a solver, and the frontier Codex model was not run
  because no spending or usage limit was agreed.
- *The substrate conditions reuse the pilot's images.* They were not rebuilt on
  the current runtime, and they crash on exit after reading NetCDF files. They
  have not been run under the revised contract.
- *The `rx` harness has no system configuration.*
- *No live data acquisition.* The earlier version of the Kenya task had the
  agent download the forecasts. This version supplies the frozen raw stores,
  for repeatability.
- *The process checklist is a draft.* See "Two WMO documents are the first standards" above.
- *The seasonal template has no Level 2.* A separate optimized submission for a
  process row needs a second, outcome-mode spec on the same data. The skill of
  the conformant forecast is reported, on two years and at most twelve cells,
  which is far too few cases to rank anything.
- *The separate "optimization within the standard" track is not built.*
- *Tables have no delivery format yet.* Parquet and GeoParquet are intended.
  The runtime image holds neither `pyarrow` nor `geopandas`.
- *The earlier 25 attempts are not reassessed under the revised rules.* Their
  agents answered the first contract. Their computed checks stand as recorded,
  with the judge's verdicts added.

## The format has these limits

- **The reference function is still hand-written.** It is the science, and no
  format removes that work.
- **The convention grid must stay small.** The controller computes every
  combination, so about five two-way choices is the practical ceiling. Research
  rows should rely on invariants, probes and skill instead.
- **A numerical match is evidence, not identification.** The format reports
  what an answer is consistent with. Only a probe or a reading of the code
  identifies what the agent actually did.
- **The judge is not validated against a person.** It returned the expected
  verdict on twelve control cases, and six of its seven failures on the first
  attempts are plain on a reading of the quotations. Both checks were made by the author
  of its prompt. Human labels on a fresh set of cases are still missing.
- **The judge is not reproducible to the letter.** The model, the prompt and
  the schema are pinned, and each reply is kept. A second request can still
  word a verdict differently or, on a close case, decide it differently.
- **The judge sends submissions to an outside service.** Each request carries
  the brief, the report, the answer, the submitted code and a summary of the
  arrays to Anthropic.
- **A tolerance from a worst-case bound is looser than real arithmetic.** It
  never fails a correct answer, and it lets through a wrong one whose error is
  smaller than the bound. On the Kenya template that is the unweighted regional
  mean on instances next to the equator.
- **A reading that changes nothing on its own instance is not caught there.**
  This follows from testing reuse by a second episode. A system that runs only
  one episode is never tested on it.
- **Trace and method-statement steps are less exact than probes.** Each
  checklist should push as many steps as possible into required products and
  probes.
- **A probe excludes the dependence it tests, not every leak.** A submission
  can pass the future-target probe and still leak by another route.
- **Pitfall lists are never complete.** New wrong answers arrive as unknown and
  need a ruling.
- **Unresolved outcomes can pile up.** A spec that returns unresolved too often
  is a defective spec, and the unresolved rate should be tracked per template.
- **The format has been tried on three tasks by one cheap model.** Thirty-six
  attempts cannot show how the checks behave across models, or whether the
  tasks separate cheap models from frontier ones.
- **The two sets of attempts were assessed under different rules.** The first
  25 keep the computed checks of the first contract, in which a blocked check
  was unresolved and a missing method entry was unresolved. The later attempts
  use the present rules. Counts from the two sets must not be added.
- **Every controller defect found so far was found by an agent attempt, not by
  a control.** The controls are written by the same hand as the checks. More
  defects of this kind should be expected with each new model and template.
- **The rulings are proposals.** They were made by the coding agent and no
  person has confirmed them.
- **The outcome gate cannot see every leak.** It catches hard-coded forecasts
  and use of later model forecasts. It cannot tell whether a model has
  memorised the public observations and encoded them in a fitted rule that
  still responds to its inputs. Only private or later observations close that
  gap.
- **A noisy method passes the "comes from the data" probe trivially.** Unseeded
  randomness moves the forecast on every run. Such a method fails the replay
  probe instead, so it does not pass the gate.
- **Mode assignments are tentative.** Rows 12, 14, 16, 20 and 25 were assigned
  without discussion.

## Two reviews changed the format

Five points were raised against the first draft on 6 October 2026.

1. **Level 2 eligibility was ambiguous.** The draft said Level 2 allows any
   method but only Level 1 passers rank. The revision makes the levels separate
   submissions with separate gates, and shows the Level 1 result beside the
   Level 2 score without gating it. This answer was confirmed the same day.
2. **Interpretation was under-assessed.** The draft relied on recomputation and
   method statements. The revision adds the interpretation check type, in every
   mode, and states the limit of claim checks.
3. **A match was treated as an identification, and coinciding variants
   rejected the spec.** The revision reports consistent sets, separates
   coinciding variants by probe where possible, reports the ambiguity
   otherwise, and adds deliberately incorrect solutions to certification.
4. **"Yes or no" had no unresolved outcome.** The revision gives every check
   three outcomes with reason codes, and routes unknown conventions through
   versioned adjudication.
5. **Provenance was dropped with the paperwork.** The revision keeps
   provenance, held by the controller instead of the agent.

**Eight design points were reviewed on 6 October 2026, after the build.** The
table under "Building it settled eight design points" gives each decision. In
short:

1. **Conventions stay hidden, and a supplied sheet becomes a condition.** A
   brief that lists the conventions makes the task too easy to compare with a
   research-replication benchmark.
2. **The changed-instance rerun was too hard-coded.** A later episode receives
   the earlier code and decides what to do with it.
3. **JSON was the wrong carrier for arrays.** The format now uses a labelled
   Zarr store, format version 3.
4. **The length of the Level 2 brief is not a constraint.** One task may start
   from the output of another.
5. **The judge must run.** A judge of the Opus class was chosen over a frontier
   model, on cost.
6. **A failed step fails, and so does everything that rests on it.** A blocked
   check is no longer unresolved.
7. **A labelled format removes the axis question.** What a name cannot settle
   is stated in the brief.
8. **A tolerance is a bound on floating-point error, checked against data.**
