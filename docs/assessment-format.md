# Assessment contract

This page specifies the instruments and recorded evidence. Start with the
[authoring guide](../templates/README.md) to exercise a control, or inspect a
concrete contract with `python -m assessment rubric TEMPLATE`.

## Task and submission

One attempt is one system on one parameterized task instance. The brief names
the results, dimensions, units, claims and any required scientific explanation.
The shared [envelope](../assessment/envelope.md) requires `results.zarr`,
`answer.json`, executable code with a regeneration command, and nonempty
`report.md`. Reruns must regenerate the numerical results and structured answer.
The controller records provenance; the agent does not write administrative proof.

`question` identifies the job as `compute_quantity`, `follow_standard`, or
`produce_forecast`. It does not silently select checks. `reference_match`
explicitly selects numerical reference matching; all other instruments are
selected by their declarations. `mode` remains a compatibility label for old
contracts. A single task may combine reference results and free forecast arrays.
Results marked `free: true` are excluded from reference matching.

## Check states and result policy

Every check returns `pass`, `fail`, or `unresolved`. A demonstrated submission
defect fails. If that defect blocks another required check, the dependent check
also fails and names `blocked_by`. Controller infrastructure, an unknown answer,
an ambiguous requirement, or an unavailable/invalid judge leaves a check
unresolved with a reason code. Unresolved is never counted as failure.

Combination is strict: any failure fails the gate; otherwise any unresolved
check leaves the gate unresolved; otherwise it passes.

`assessment_policy.completion` and `.ranking` explicitly select required check
IDs or patterns. Unmatched patterns are rejected. Both gates require `envelope`.
Every assessed row records `required_for` and its implementation. Checks outside
both gates are supplementary. The rubric includes each actual judge question;
templates may own wording in `judge_questions`, or explicitly reuse a shared
question by name. Required process statements remain gating judge checks.

| Result | Meaning |
| --- | --- |
| `outcome` | Completion under the declared required checks |
| `ranking_outcome` | The declared eligibility gate |
| `advisory_outcome` | Supplementary checks, shown independently |
| `all_checks_outcome` | Strict combination of every check, for auditing |
| `computed_outcome` / `judged_outcome` | Components grouped by decision mechanism; these do not override policy |
| `skill` | Numerical scores and baselines, independently of pass/fail |
| `skill_valid_for_ranking` | Ranking gate passed and the task permits ranking |

`skill.ranking_enabled: false` makes a small-sample score informative only. With
no explicit policy, historical contracts retain their old all-checks completion
and computed-check ranking semantics. New policy is a versioned contract change.
Required unrun judges leave completion unresolved. Supplementary unrun judges
remain visible without blocking it. Plain `assess` does not invoke a judge;
`assess --judge` and `run` do. `run --no-judge` retains the open questions.

## Instruments

| Declaration | Instrument | Decision evidence |
| --- | --- | --- |
| `results` and envelope | Delivery and coverage | Readable labelled arrays, required coordinates, command and report |
| `reference_match`, `conventions` | Reference match | Accepted readings and named pitfalls within error bounds |
| `invariants` | Rules any valid answer obeys | Scientific functions in `INVARIANTS` |
| `probes` | Replay, data response and isolation | Reruns of the submitted command after declared input changes |
| `claims` | Stated conclusion | The submission's numbers or controller metric |
| `process` | Required practice | Existing checks, reference quantities, method pointer or judge question |
| `interpretation`, `judge_questions` | Prose review | Exact quoted evidence under the template's question |
| `skill` | Forecast quality | Withheld observations and declared baselines |

A coverage gap is scoped: a coordinate that is missing or does not list exactly
the required values takes down the results laid out on it, and every check that
needs one of them fails "with the coverage", naming the result and the gap.
Everything else is assessed on its merits. Only when no array survives does the
whole assessment stop at the coverage check.

A rerun is a counterfactual test on the same instance. It does not require a
program to generalize to a new task instance. A later attempt may explicitly
retain earlier work through `--parent`; call this a retained-work attempt rather
than using “episode” for both any run and the retention condition.

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
is gone. Retaining work between attempts is an explicit `--parent` condition.

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

### Optional prose reviews ask one narrow question

**A spec may list interpretation checks.** An interpretation check is one narrow
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
array: its dimensions, shape, minimum, mean and maximum. A template may add
lines to that summary through an optional `judge_summary(results, params)`
hook, for the figures its prose is judged against: the objective outlook adds
the area share of each dominant category, the mean, minimum and maximum issued
probability per category over the supported window, and the hindcast skill
scores, so "every number the bulletin states appears in the arrays or follows
from them" is decidable from what the judge sees. It is not shown the
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
practice number it comes from. It will cite the clause once the primary
document is obtained.

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
   step requires, under the same quote rule and three outcomes as an
   interpretation check.

**A missing method entry fails; an unclear step is unresolved.** The brief
asks for each method entry by name. An entry that is absent, or whose pointer
names no place in the submission, is the submission's omission and fails. A
step also fails when the cited code does something the step forbids, or when
a probe shows the step was not done. A step that can be read two ways is
unresolved.

**Scientific reasoning is also tested through decision points.** An instance is
built so that the standard demands a judgement whose result is visible in the
output. Examples: a region where the model has no skill, where the forecast
should revert to climatological probabilities; a hindcast with fewer ensemble
members than the real-time forecast, which changes how calibration must be
done. Two existing tasks already work this way: the station with no valid
midnight reports, and the rainfall predictor whose units cannot be resolved.

**Each standard step is evaluated from one kind of evidence.**

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
  `judged_outcome`; its declared policy determines whether it gates completion.
  It does not enter `computed_outcome`.

**A valid negative result conforms.** A climatological forecast, one third for
each category, passes every computed step.

**The format prefers a required intermediate product to a probe or a judge.**
When two readings give the same final score, the brief asks for the
intermediate array that differs between them, and that array settles the
question for every forecast. Example: a climatological forecast scores zero
whether or not the category boundaries leak the held-out year, so the
seasonal brief also asks for the observed category of each year.

### Stages give a long-horizon composition one verdict per part

**A template may declare `stages`: an ordered list of the parts of the job,
each owning a group of results.** Every stage receives up to two verdicts and
one row, `stage.<id>`, in the rubric. Completion and ranking gates select the
stage rows through the ordinary policy, so a long composition is scored part
by part rather than as one match.

- *Schema.* The stage's own results must be readable, finite and of the
  declared shape. A stage whose results are unusable fails, with the first
  problem quoted; its verdicts are not attempted. A coordinate that does not
  list the required cases takes down only the results laid out on it, so a
  stage that owns none of them keeps its verdicts.
- *Absolute verdict.* Is the product right, judged from the controller's own
  inputs? It rests either on a reference match of the stage's results, which
  looks only at the conventions that can change them and, where the
  changed-data probe ran, requires those results to follow the data under a
  reading consistent with the submitted ones; or on named checks computed on
  the controller's inputs, such as a method-blind gate.
- *Local verdict.* Was the stage done right given the submission's own
  upstream products? It rests on named checks that recompute the stage from
  the arrays the submission handed itself, and on probe parts. When an
  upstream stage failed its schema the local verdict is
  `unresolved: invalid_upstream_contract`: the question cannot be asked of
  broken inputs, and that is not this stage's fault. The absolute verdict
  still runs.
- *Stage verdict.* The strict combination of the verdicts declared. An
  absolute verdict left unresolved because the results match no listed
  reading, with a local verdict that fails, fails the stage: this is how a
  leak in one stream is attributed to that stream and to nothing else.
- *Rollup.* `stages` lists every stage with its schema, absolute, local and
  stage states; `stage_score` gives the count and the weighted fraction of
  passed stages (weights default to one) and names the failed and unresolved
  stages. Unresolved stages never count as passed and never as failed.

**A probe may be judged per part.** An invariance probe declares `parts`, one
projection of the results per part, and the one rerun yields
`probe.<name>.<part>` rows beside the whole-submission row. A stage names the
part that belongs to it.

**Review questions a stage lists are informational.** The stage row records
them; the judge rows keep their own place in the policy.

The whole-submission variant match, the changed-data probe and the claims
remain in the record as evidence. A template with stages ordinarily leaves them
supplementary, since every stage already carries its own match.

### Skill is reported at every level and can rank a declared optimization submission

**The controller scores frozen forecasts against private observations.** The
score is relative to a declared baseline. Any method is acceptable.

**The gate is the validity check on the Level 2 submission itself.** See
"Level 1 and Level 2 are separate submissions" above.

**The budget is fixed.** Compute, tokens and the number of feedback queries are
the same for every system, and the feedback tool
(`assessment/feedback.py`) enforces a query limit.

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


## Authoring validation and comparison lock

`assess --control correct` is available before certification. The automatic
validation record reports independent numerical agreement, computed checks on
correct controls, planted-fault detection, and measured pitfall separability.
Independent agreement uses each array's declared error bound, not a universal
absolute threshold that mixes probabilities, millimetres and square metres.

`review_status` separates automatic checks, trial-attempt review and scientific
approval. The fifth test records at least two real attempts under the current
fingerprint and any open unknown answers. Neither an automatic pass nor a
classified trial is scientific approval. `certified` stays false pending that
approval. Required prose checks on controls must also pass before describing a
control as a complete passing solution.

The controller fingerprints scientific hooks, source records, briefs, policies,
questions and deciding modules. Version scientific or verdict-policy changes;
keep earlier assessments and compare systems under one frozen contract. The
runtime, adapter and provenance protocol are in [runtime.md](runtime.md).

## Practical limits

Reference matching grows with the convention grid. Kenya currently evaluates
64 readings, of which two are accepted; the rubric exposes both counts. This is
an explicit review and execution burden, not a hard five-choice format limit.
Retain combinations needed to expose scientific interactions; do not remove
pitfalls merely to reduce the count.

Pitfall lists are incomplete. A novel numerical answer can remain unresolved
until reviewed; it must not become an agent failure by default. Rerun probes
establish only the properties of the perturbations exercised. Withheld
historical observations remain public records and may appear in model training.
The draft WMO checklist and every task still require domain-scientist review.
