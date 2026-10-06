# A generic assessment format for the 25 task templates

Status: proposal agreed in outline on 6 October 2026 and revised the same day
after a five-point review (see "What the review changed" at the end). Nothing
here is implemented. The current evaluator (`weatherbench/evaluation.py`,
`weatherbench/judge.py`, the per-task `rubric.yaml` files) is unchanged. The
companion list of tasks is [the proposed starting set](task-set.md).

## The question, stated twice

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

## Terms used in this document

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
- **Probe.** A rerun of the agent's own code on inputs the controller has
  changed, to observe behaviour instead of reading code.
- **Decision point.** A feature deliberately present in an instance where the
  standard requires a judgement, and where the right judgement shows in the
  output.
- **Standard.** A published document that defines correct practice. The first
  two are named in "The first standards" below.
- **Judge.** A language model that answers one narrow question about cited
  evidence. It returns pass, fail or unresolved, and must quote the exact text
  it relies on.
- **Pass, fail, unresolved.** The three outcomes of every check. *Fail* means a
  demonstrated defect. *Unresolved* means the evidence does not decide the
  question. The two are never merged.
- **Controller.** The trusted benchmark harness that launches the agent, holds
  the private references and runs the checks.

## The agent delivers a small fixed envelope and is free in everything else

**The envelope has three required parts.** An `answer.json` file, one command
that regenerates the results from the inputs, and a free-form report. Language,
method, file layout and intermediate steps are not constrained.

**`answer.json` has four sections.**

- `results` — the named quantities the brief asks for, as numbers, arrays or
  pointers to files.
- `choices` — the conventions the agent used, taken from the list in the spec,
  with free text allowed for a choice the spec does not list.
- `claims` — the agent's conclusions as structured statements with the value
  true, false or inconclusive, such as "the nested search beats the fixed
  predictor".
- `method` — required only in process mode. One entry per step of the standard:
  what was done, and a pointer to the file and function that did it.

**The run command is what makes probes possible.** The controller substitutes
an input directory and an output directory and runs the command offline.

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

**Fail is reserved for a demonstrated defect.** A wrong number, a leak shown by
a probe, a claim contradicted by recomputation, or a quoted passage that
contradicts the standard.

**Unresolved covers everything the evidence does not decide.** Each unresolved
outcome carries a reason code:

- `missing_evidence` — the artifact needed to decide is absent or truncated.
- `ambiguous_clause` — the standard or the brief can be read two ways.
- `invalid_citation` — the judge's quote does not appear in the cited file, so
  its verdict is discarded.
- `ambiguous_variant` — the numbers are consistent with both an accepted
  convention and a pitfall, and no probe separates them.
- `unknown_answer` — the numbers match no listed combination.
- `infrastructure` — the controller could not run the check.

**Level 1 is pass only when every required check passes.** It is fail when any
check fails, and unresolved otherwise. Unresolved runs are reported in their
own column and are never counted as failures.

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
- Accepted and pitfall combinations together: the controller runs a targeted
  probe that separates them, such as rerunning the agent's code on an input
  with an injected negative increment. If no probe separates them, product
  mode passes with an `ambiguous_variant` flag, because the delivered product
  is correct for this instance. Process mode returns unresolved, because the
  method is what is being assessed.
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

**Probes observe behaviour.** Three shapes already exist in this repository and
cover most needs:

1. *Replay.* The command regenerates the submitted results from the original
   inputs.
2. *Perturb and recompute.* The controller changes an input; the results must
   change to match an independent recomputation, or must stay unchanged where
   the change lies in the future of a forecast.
3. *Remove targets and infer.* The controller deletes the observations; the
   saved fit must still produce forecasts.

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

**Each obligation is judged on its own, with exact quotes.** The judge returns
pass, fail or unresolved. A fail must quote both the claim and the evidence
that contradicts it. A quote that does not appear in the cited file voids the
verdict and yields `invalid_citation`.

**This is the form used in the two station studies of 6 October.** A judge and
the agent-reviewed references agreed on 28 of 28 cases, including cases where a
caption contradicted a correct report and where a bootstrap never recomputed
its statistic. Those studies used one parent submission and no human labels.
They show the form is workable; they do not show the judge is accurate. In the
second study the judge's first response failed exact-quote validation in two of
ten cases, which is why the `invalid_citation` outcome exists.

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

**A missing pointer or an unclear clause is unresolved, not a failure.** A step
fails only when the cited code demonstrably does something the clause forbids,
or a probe shows the step was not done.

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

## An example spec for a product-mode task

This is illustrative. The field names are not final.

```yaml
template: kenya-forecast-revision
spec_version: 1
mode: product
params: [issue_current, issue_previous, rectangle]
results:
  regional_change_mm: {tolerance: 1e-4}
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
separating_probes:
  rainfall_semantics: inject_nonmonotone_cumulative
invariants: [change_equals_current_minus_previous]
probes: [replay, perturb_and_recompute]
interpretation: [consistency_across_artifacts, source_attribution]
```

## An example of the extra block for a process-mode task

This is illustrative. The steps are a sketch from memory of the standard and
have not been extracted from its text.

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

## The first standards

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

**The checklists do not exist yet.** The identities of the documents were
confirmed by a web search on 6 October 2026. Neither document is in the
workspace, and no clause has been extracted. The first step is to freeze a copy
of each document in the repository, extract the steps with clause numbers, and
have a domain reviewer sign off the result.

## A spec is certified by five tests

1. **Two independent reference implementations agree.** This is already the
   practice for the ten packaged tasks.
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
   recorded.** For each pair the certification states one of: separated by the
   numbers on typical instances; separated only by a named probe; or not
   separable. A pair that coincides on some instances does not reject the spec.
   A pair that is not separable at all is listed as a known ambiguity.
5. **Several cheap-model attempts are run, and every unknown answer is ruled
   on.** The spec version is locked only after that.

Human scientific approval is a separate, later gate. Certification says the
spec is internally sound, not that the science is endorsed.

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

## What a result looks like

- **Level 1:** pass, fail or unresolved; the set of convention combinations the
  answer is consistent with; each invariant, probe, claim, interpretation and
  process outcome with its evidence and, where unresolved, its reason code;
  cost, time and tokens; the spec version.
- **Level 2:** the validity-gate outcome; skill of the optimized forecast
  against each baseline; on process rows, the skill of the conformant forecast
  where it is independently valid; the Level 1 result shown beside it, whatever
  that result is; the feedback queries used.
- **Per run, in every case:** the model, harness and substrate; the
  substrate-use record; the parent run and retained state, if any.
- **Across instances:** counts of pass, fail and unresolved, and mean cost,
  over the same drawn instances for every system compared.
- **Across episodes:** cost, tokens, time and outcome for each episode in a
  sequence, for the retained condition and the reset condition.

## How this changes the current implementation

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

## Limits of this proposal

- **The reference function is still hand-written.** It is the science, and no
  format removes that work.
- **The convention grid must stay small.** The controller computes every
  combination, so about five two-way choices is the practical ceiling. Research
  rows should rely on invariants, probes and skill instead.
- **A numerical match is evidence, not identification.** The format reports
  what an answer is consistent with. Only a probe or a reading of the code
  identifies what the agent actually did.
- **The judge is still unvalidated.** Narrow questions and quote checks reduce
  its room for error. They do not replace human labels on a fresh set of cases.
- **Trace and method-statement steps are less exact than probes.** Each
  checklist should push as many steps as possible into required products and
  probes.
- **A probe excludes the dependence it tests, not every leak.** A submission
  can pass the future-target probe and still leak by another route.
- **Pitfall lists are never complete.** New wrong answers arrive as unknown and
  need a ruling.
- **Unresolved outcomes can pile up.** A spec that returns unresolved too often
  is a defective spec, and the unresolved rate should be tracked per template.
- **The format has not been tried on any task.** The recommended first trial is
  the Kenya forecast revision task (row 4), followed by one process row.
- **Mode assignments are tentative.** Rows 12, 14, 16, 20 and 25 were assigned
  without discussion.

## What the review changed

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
