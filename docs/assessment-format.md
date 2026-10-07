# A generic assessment format for the 25 task templates

Status: this is the specification of the assessment format. Product mode,
outcome mode with both levels, and process mode are implemented in the
`assessment/` package and certified on three templates. A pinned judge,
Claude Opus 5.5, decides the questions no computation can settle. The process
checklist is a draft from a secondary source and is not signed off by a domain
scientist. The history of the format, with the attempts made while building
it, is in [the changelog](CHANGELOG.md). Measured results are in
[results](results.md). The companion list of templates is
[the proposed starting set](task-set.md).

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

- **Template, instance, brief, Level 1, Level 2.** A template is a
  parameterised task; an instance is one drawn parameter set; the brief is the
  text the agent receives for an instance. Level 1 is "produce a valid
  output". Level 2 is "optimize it", scored as skill on a ranking table (the
  leaderboard). The templates are listed in [the task set](task-set.md).
- **System, harness, tooling, supplement.** A system is a model plus a harness
  plus tooling. The harness is the agent loop that drives the model. Tooling
  is the skills, libraries or earlier work supplied to the agent in its
  runtime image. A supplement is a conventions sheet or method description
  handed in with `--supply`.
- **Attempt, episode.** An attempt is one run of one system on one instance.
  An episode is an attempt started with `--parent`, which receives an earlier
  submission.
- **Check, mode, outcome.** A check is one pass, fail or unresolved decision.
  A mode is the template's kind of assessment: product, process or outcome.
  An outcome is pass, fail or unresolved.
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
  carries its arrays. Every array carries named dimensions, and every dimension
  carries a coordinate array of labels.
- **Probe.** A rerun of the agent's own code on data the controller has
  changed, to observe behaviour instead of reading code.
- **Episode.** One run of one system on one instance. A second episode may be
  given the first episode's submission.
- **Conventions sheet.** An optional page that states a task's accepted
  conventions. Handing it to the agent is a supplement, switched on per run.
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
- **Controller.** The trusted evaluator that launches the agent, holds
  the private references and runs the checks.

## The agent submits a small fixed envelope and is free in everything else

**The envelope has four parts.** A results store, an `answer.json` file, one
command that regenerates the results from the data, and a free-form report.
Language, method, file layout and intermediate steps are not constrained. The
text every agent receives is [`assessment/envelope.md`](../assessment/envelope.md).

**Arrays are submitted in `results.zarr`, a Zarr store of format version 3.**

- Each array is stored under the name the brief gives it, on the dimension
  names the brief gives.
- Each dimension has a coordinate array of the same name that holds its labels.
- The controller matches each array to its own by dimension name and by label.
  The order of the dimensions and the order of the labels are the agent's to
  choose.
- `xarray.Dataset.to_zarr(path, zarr_format=3)` writes exactly this layout.

**The labelled store replaced nested lists in `answer.json`.** One
earlier agent attempt failed because a nested list gave no way to tell which
axis was which. A labelled array removes that question instead of answering it
case by case. What remains open is only what a name can settle, so each brief
states the array names, the dimension names and the unit.

**Tables will be submitted as Parquet, and as GeoParquet where they carry
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
The controller already keeps most of them (`artifacts.json`, the task snapshot,
`logs/events.jsonl`, the lock fingerprint).

## Each template declares one of three modes

Columns:

- **Mode** — the name used in the task set.
- **What Level 1 requires** — what must hold for a pass.
- **How prescriptive** — how much of the method the assessment fixes.
- **Typical templates** — numbered entries of the task set that use the mode.

| Mode | What Level 1 requires | How prescriptive | Typical templates |
| --- | --- | --- | --- |
| Outcome | A valid submission: correct format and units, forecast and target times aligned, complete coverage, and the leakage probes passed | Not at all; any method | 15, 23 |
| Product | The requested quantity, correct under some accepted combination of conventions | The product is fixed; the method is free | 1–9, 16, 24, 25 |
| Process | Everything in product mode, plus conformance to a named standard | The method is fixed by the standard | 10–14, 17–22 |

Interpretation checks (defined below) apply in every mode.

## Level 1 and Level 2 are separate submissions with separate validity checks

**The two levels measure different capabilities, so they take different
submissions.** At Level 1 the agent submits the output the brief asks for; on a
process template that is the standard-conformant forecast. At Level 2 the agent
submits a separate optimized forecast, made by any method.

**The Level 2 submission has its own validity gate, a group of four checks.** It is assessed in outcome
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

**A process template therefore reports three things per system.**

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

**The outcome-mode validity gate is the group of four checks below.** It
prescribes no method.

1. *Coverage and time alignment.* The forecast must list exactly the required
   issues and cells, each labelled with its own date and cell. Missing issues
   or cells, or mislabelled dates, fail here.
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

**Skill is reported whenever a forecast covers the required issues and cells.** A forecast
that fails the gate still has its score recorded, with
`skill_valid_for_ranking` set to false.

**Level 2 adds two checks.** The controller's ledger must show no more
development-score requests than the limit. If the agent states a development
score, it must equal the controller's score of the submitted forecast; stating
`null` for "not measured" passes.

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

## The checks come in ten types

Columns:

- **Check type** — the name used in a spec.
- **Question it answers** — what the controller decides.
- **Decided by** — whether computation or a judge decides it.
- **Modes** — where it is used.

| Check type | Question it answers | Decided by | Modes |
| --- | --- | --- | --- |
| Envelope (`envelope`) | Did the submission arrive in the fixed envelope, with a readable answer? | Computation | All |
| Coverage (`coverage`) | Does the answer list exactly the required issues, cells and results, each labelled? | Computation | All |
| Variant match (`variant`) | Which combinations of conventions are the results consistent with? | Computation | Product, process |
| Invariant (`invariant.*`) | Do the results obey rules any valid answer must obey? | Computation | All |
| Probe (`probe.*`) | Does the agent's code behave correctly on changed inputs? | Computation | All |
| Claim check (`claim.*`) | Do the stated numbers and sample-level conclusions match what the controller recomputes? | Computation | All |
| Interpretation (`interpretation.*`) | Is each stated conclusion supported by the evidence, and do the report, captions, structured answer and code agree? | Judge, on cited evidence | All |
| Process conformance (`process.*`) | Was each step the standard requires actually carried out? | Computation where possible, judge otherwise | Process |
| Feedback limit (`feedback.limit`) | Did the agent stay within the development-score request limit, and does any stated development score equal the controller's? | Computation | Outcome (Level 2) |
| Skill | How good are the forecasts against private observations? Reported at every level whenever coverage passes; counts for ranking only when the computed checks pass. | Computation | Outcome |

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

**Each spec lists interpretation checks.** An interpretation check is one narrow
question about the agent's reasoning. The standing interpretation checks are:

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

**A template adds its own interpretation checks where needed.** The station task, for
example, requires that curator-constructed faults are not described as real
observation outages.

**Each interpretation check is one question, decided on exact quotations.** The judge
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
fixed reply schema. The model, the effort, the prompt, the interpretation checks and the
schema are hashed into a judge identifier that every judgement carries. One
request covers all the questions of one run.

**The judge sees text, never raw arrays.** It is shown the brief, the report,
`answer.json`, the submitted code, and a controller-written summary of each
array: its dimensions, shape, minimum, mean and maximum. It is not shown the
controller's findings, so a failed numerical check cannot be counted twice.

**The judge has its own control cases.** Twelve small submissions, each with one
planted defect or none, are kept in
[`assessment/calibration.py`](../assessment/calibration.py) with the verdict
each must receive. They cover the five standing interpretation checks, the method-statement
question and the required-statement question. The pinned judge returned the
expected verdict, with valid quotations, on 12 of 12. The record is
`assessment/judge-calibration.json`, and a test fails when it was made by
another judge identifier. Twelve cases written by the same author as the prompt
show that the judge can apply the questions. They do not measure its agreement
with a domain scientist.

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
   interpretation check.

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

**The format prefers a required intermediate product to a probe or a judge.**
When two readings give the same final score, the brief asks for the
intermediate array that differs between them, and that array settles the
question for every forecast. Example: a climatological forecast scores zero
whether or not the category boundaries leak the held-out year, so the
seasonal brief also asks for the observed category of each year.

### Skill is reported at every level and ranks Level 2

**The controller scores frozen forecasts against private observations.** The
score is relative to a declared baseline. Any method is acceptable.

**The gate is the validity check on the Level 2 submission itself.** See
"Level 1 and Level 2 are separate submissions" above.

**The budget is fixed.** Compute, tokens and the number of feedback queries are
the same for every system, and the feedback tool
(`assessment/feedback.py`) enforces a query limit.

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
serves every template that names the same standard.

**A draft checklist exists; the primary documents were not obtained.** The WMO
library did not serve WMO-No. 1246 to an automated request.
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
   magnitude covers the data.** The second part checks each tolerance's error bound: the
   largest reference value under an accepted reading must not exceed the
   magnitude the bound assumes.
2. **A known-correct submission passes every check.**
3. **Deliberately incorrect submissions are caught by the right check.** The set
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
and lock fingerprint that produced it, as the controller already does.

## The same spec applies to every system

**Checks do not change with the model, the harness or the tooling.** A system
using the Rhiza weather-skills catalog, the `acmadDL` or `AfricaS2S` libraries,
or the `rx` harness is assessed by the same spec as a system using none of
them. This is what makes the comparison of tooling fair.

**The envelope does not favour hand-written code.** The run command may call a
skill's command-line tool or a library workflow. The agent need not rewrite a
tool in its own code to be assessable.

**Every result carries the system's identity and its tooling use.** The run
record states the model, the harness, the tooling and its hash. It includes
the tooling-use record (the `substrate_record` produced by
`assessment/substrate_use.py`, pull request #1): how many commands listed, read
or ran tooling files, how many of those runs failed, and the step at which the
tooling was first touched. Use
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

## A conventions sheet is a supplement that can be switched on and off

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
model, the harness and the tooling. The same instance run with and without
the sheet measures how much of a task's difficulty is knowing the conventions.
A method-description supplement works the same way.

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
  against each baseline; on process templates, the skill of the conformant forecast
  where it is independently valid; the Level 1 result shown beside it, whatever
  that result is; the feedback queries used.
- **Per run, always:** the model, harness and tooling; the
  tooling-use record; the supplements handed to the agent; the parent run,
  the retained state and the use made of the earlier work, if any.
- **Across instances:** counts of pass, fail and unresolved, and mean cost,
  over the same drawn instances for every system compared.
- **Across episodes:** cost, tokens, time and outcome for each episode in a
  sequence, for the retained run and the reset run.

## These parts are not implemented

- *Only one model has attempted the templates.* The Codex adapters accept only
  command-line version 0.160.0, whose isolation was verified. The default
  install has moved to 0.160.1, so the Codex systems added here name the
  0.160.0 binary, which is still on disk; the version check was not changed. No
  Claude model has run as a solver, and the frontier Codex model was not run
  because no spending or usage limit was agreed.
- *The tooling images are the pilot's images.* They were not rebuilt on
  the current runtime, and they crash on exit after reading NetCDF files. They
  have not been run under the revised contract.
- *The `rx` harness has no system configuration.*
- *No live data acquisition.* The earlier version of the Kenya task had the
  agent download the forecasts. This version supplies the frozen raw stores,
  for repeatability.
- *The process checklist is a draft.* See "Two WMO documents are the first standards" above.
- *The seasonal template has no Level 2.* A separate optimized submission for a
  process template needs a second, outcome-mode spec on the same data. The skill of
  the conformant forecast is reported, on two years and at most twelve cells,
  which is far too few cases to rank anything.
- *The separate "optimization within the standard" track is not built.*
- *Tables have no submission format yet.* Parquet and GeoParquet are intended.
  The runtime image holds neither `pyarrow` nor `geopandas`.
- *The earlier 25 attempts are not reassessed under the revised rules.* Their
  agents answered the first contract. Their computed checks stand as recorded,
  with the judge's verdicts added.

## The format has these limits

- **The reference function is still hand-written.** It is the science, and no
  format removes that work.
- **The convention grid must stay small.** The controller computes every
  combination, so about five two-way choices is the practical ceiling. Research
  templates should rely on invariants, probes and skill instead.
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
- **Mode assignments are tentative.** Task-set entries 12, 14, 16, 20 and 25 were assigned
  without discussion.
