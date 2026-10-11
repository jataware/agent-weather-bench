# The changelog records how the assessment format and the controller changed

This file holds the dated history of the assessment format (the rules in
[assessment-format.md](assessment-format.md)) and of the controller (the
trusted evaluator in `assessment/`). It keeps the numbers that explain a
decision. Measured results live in [results.md](results.md) and are not
repeated here. Terms: a *template* is a parameterised task; an *instance* is
one drawn parameter set; an *attempt* is one run of one system on one
instance; a *check* is one pass, fail or unresolved decision; a *convention*
is an axis on which a method may be read two ways, a *reading* is a value on
it and a *pitfall* is a wrong reading; *tooling* is the skills, libraries,
conventions sheet or earlier work supplied to the agent.

## 2026-10-09: per-stage verdicts for a long-horizon composition

- Added `stages` to the contract (`assessment/stages.py`, a deciding module):
  an ordered list of the parts of a job, each owning a group of results, with
  an absolute verdict (right, from the controller's inputs) and a local verdict
  (right, given the submission's own upstream arrays). A stage whose results
  are unusable fails its schema; a downstream local verdict is then
  `unresolved: invalid_upstream_contract`, a new reason code. The record gains
  `stages` (the profile) and `stage_score` (count and weighted fraction of
  passed stages). The stage absolute verdict on results reuses the process
  step's reference agreement and adds a per-stage changed-data test from the
  one changed-data rerun. Invariance probes may declare `parts`, judged per
  part from the same rerun. Templates without `stages` are unchanged in
  behaviour; every fingerprint changes because a deciding module was added,
  and the five certified templates were re-certified.
- The objective seasonal outlook template (spec version 2) declares its eight
  stages, three local-verdict invariants that recompute WVG, eReg and the CCA
  gate from the submission's own prepare arrays, and per-stream parts of the
  held-out-year probe. Its completion policy now gates on the stage rows and
  the two whole-submission invariants; the whole-submission match, probes and
  claims are evidence. The first certification showed why: a leak in one
  stream left the whole-submission match unresolved (no listed reading fits)
  while the probe failed, and the record could not say which stream.
- The same template's first certification also failed on tercile-boundary
  ties: CHIRPS repeats one seasonal total across up to thirteen years in dry
  cells, the quantile lands on that value, and two correct interpolation
  formulas differ by one unit in the last place. The brief now gives the
  category rule a 1e-6 mm margin; 2 to 35 cells per instance and reading are
  affected.

## 2026-10-08: inspectable rubrics and a bounded grading checkpoint

- Reject malformed task briefs before runtime launch or run creation. A new
  consolidation brief exposed unescaped example braces before inference;
  its failed authoring record is retained separately from the actual model
  attempt. Added a launch regression and rendered all ten templates across
  their instance, level and supplement variants.
- Added a free-design MAM synthesis template and a lean objective-consolidation
  template. The former failed its attainable-baseline gate before inference;
  Luna passed the latter. A separate guided-tool efficiency phase produced
  one valid Luna completion versus an incomplete Python attempt. See the
  dated two-track report for resources and limitations. No scientific approval
  or hard-model boundary is implied.

- MAM outlook v2 preserves source dtype in changed-data and held-out probes.
  The first guided efficiency pair exposed a precision change falsely attributed
  to held-out observation leakage. Regression controls distinguish this from the
  submissions' real float32 accumulation error. Archived v1 files reproduce its
  fingerprint; original verdicts remain unchanged. Scientific calculations and
  error bounds are unchanged. Efficiency interventions and difficulty candidates
  are recorded in separate bounded studies.

- Added parallel grader, delivery-ingestion and forecast-audit investigations.
  Forty equivalent storage/layout variants pass; scientific faults are rejected.
  New tasks preserve real-data lineage and accept scientifically valid repairs.
  General dependency versions match across the three new tooling conditions.
  Five bounded attempts completed, all passing; neither tooling benefit nor a
  hard capability boundary was demonstrated. Full suite: 140 passing tests.
- Audit controls exposed cached-output and score-rounding loopholes. Optional
  response projections/groups now check each forecast deliverable; audit claims
  use recomputed scores. Annual and production information-boundary probes cover
  localized future-data use. Controller revisions preserve historical verdicts.
- Optional scratch-state links are recorded and omitted without being followed;
  they no longer discard a valid submission. A threaded HDF5 validation crash
  was diagnosed and validation switched to separate Python processes. Neither
  incident prompted an agent retry.

- Completed the six-attempt checkpoint and six focused follow-ups, with two
  concurrent attempts and explicit pauses for evaluator diagnosis. CCA passed
  on both Astra and Luna. Reports separate controller stop status, completion,
  supplementary reviews and actual tool use.
- Downscaling v2 corrects a pixel-area roundoff bound discovered in both agent
  attempts. Original unresolved verdicts remain; separate symmetric frozen
  reassessments pass. Added an equivalent-edge control and wrong-radius
  regression. Full suite: 125 passing tests.
- Repaired a reproduced cfgrib/pyproj import-order abort in derived matched
  images while retaining NetCDF4. Added Docker-only native/I/O and weather-tool
  diagnostics, current-library commit/wheel provenance and visible remaining
  token/tool budgets. Fixed Rhiza's optional-Zarr-metadata reader in a further
  derived image, preserving the original diagnostics and historical attempts.
  Six Rhiza and two acmadDL direct functional cases pass. These checks establish
  tool functionality, independently of agent performance.

- Added `rubric` and `assess --control`, with one row per instrument and saved
  assessments plus readable reviews. Each task declares its primary question,
  explicit reference instrument, completion/ranking gates and owned judge text.
  Generic prose reviews are supplementary in the pilot; required scientific
  process reviews remain gates. Missing or empty reports fail the envelope.
- Versioned Kenya to v3, calibration to v4 and weeks 3–4 to v4. Existing runs
  remain evidence for their historical contracts. Automatic validation, trial
  review and pending scientific approval have separate recorded statuses.
- Added real-data CCA reproduction and conservative rainfall downscaling,
  each with a separate scientific implementation, four candidate instances,
  changed-input and leakage probes, planted faults and hash-checked restoration.
- Replaced a regression test that deliberately sent SIGSEGV to host Python with
  a simulated executor record. The old test triggered macOS crash notifications;
  it was not evidence of a Docker scientific-library crash during this checkpoint.
- Limited the initial experiment to three templates × Python/Rhiza on one
  backbone, with two concurrent attempts and inspection between pairs. Added
  bounded configurations and a frozen experiment plan. Larger comparisons wait
  for the checkpoint review.

## 2026-10-07: the first evaluator was archived and the controller became standalone

- Generation 1 (ten task packages, the rubric evaluator and the locked Sonnet
  judge) moved to `archive/evaluator-v1-2026-10/`. Its judge lock covered the
  moved paths and is no longer verified.
- `assessment/` now holds the sandbox, the adapters, storage, the system
  definitions and the tooling-use monitor. The three templates were
  re-certified in Docker and their fourteen runs reassessed.
- The format document was cut to a specification. Its history moved here.

## 2026-10-06: eleven attempts were made under the revised contract

- The same cheap model (gpt-6-luna through the Codex harness, command-line
  version 0.160.0) attempted the three templates again. These are the attempts
  the fifth certification test counts: 4 on Kenya forecast revision, 3 on
  weeks 3–4 rainfall and 4 on seasonal rainfall calibration.
- Eight were plain or sheet-supplied first episodes and three started from an
  earlier submission with `--parent`. Every attempt submitted a Zarr store and
  the judge ran with each.
- Three attempts failed, each for a fault in the agent's own work: a seasonal
  run whose category boundaries include the held-out year (the named pitfall);
  a seasonal run with the conventions sheet whose observed step is inverted,
  which matched no listed reading and went to review (stated skill −0.807,
  correct step 0.314, ruling recorded as proposed); and a weeks 3–4 Level 2 run
  that stated no development score and described a ridge penalty of 10 where
  the code set 0.01.
- Both second episodes on a new instance passed and used the earlier work.
- Every submission was readable. Under the first contract three of 25 attempts
  had an array layout problem.
- These attempts support no comparison: there is one attempt per cell.

## 2026-10-06: the judge decided 106 questions on the first 25 attempts

- The judge (Claude Opus 5.5, pinned) ran over the recorded assessments without
  recomputing them: three interpretation questions per run, and up to three
  process questions on the seasonal template.
- 106 questions went out in 25 requests. None came back unresolved and none
  was voided for an inexact quotation. The requests used 165,949 input tokens
  and 47,172 output tokens, $1.99 at list price.
- The judge failed 7 questions in 7 runs and changed the headline of two
  weeks 3–4 runs. One verdict found a defect the numbers had not isolated.
  Every failure quotes the passages it rests on.
- In two earlier station studies the same judge form agreed with
  agent-reviewed references on 28 of 28 cases, with one parent submission and
  no human labels.

## 2026-10-06: the first attempts exposed eight defects in the controller, all fixed

- Before the fixes, eight of the fourteen tooling-comparison runs carried a
  failure the controller had caused. After them every remaining failure has an
  agent error behind it. This is what the fifth certification test is for.
- The eight defects: the changed-data probe altered the store's format; one
  unusable result stopped the whole assessment; the submission contract did not
  say where the `method` section goes; a method pointer could be satisfied by a
  phrase; results grouped by period were rejected; a crash in the runtime was
  blamed on the method; an unknown answer had nowhere to go; `instance.json`
  exposed a parameter the brief does not explain.
- Every run was assessed again after each fix that left its inputs unchanged.
  Four further attempts ran under spec version 2.

## 2026-10-06: two reviews revised the format

- Five points against the first draft: Level 2 eligibility was ambiguous
  (levels became separate submissions with separate checks, and the Level 1
  result is shown beside the Level 2 score, not used to hide it);
  interpretation was under-assessed (a judge on cited evidence was added to
  every mode); a match was treated as an identification (coinciding readings
  now go to a changed-data probe); "yes or no" had no unresolved outcome (every
  check now has three outcomes); provenance was dropped with the paperwork
  (the controller now records it).
- Eight design points reviewed after the build, with what is now built:
  1. Convention names stay private; a conventions sheet is an optional
     supplement handed over with `--supply conventions` and recorded with the
     run.
  2. No changed-instance rerun; a second episode starts with `--parent` and
     receives the earlier submission.
  3. Arrays travel as a Zarr store, format version 3, with named dimensions
     and coordinate labels, instead of nested lists in `answer.json`. One
     earlier attempt failed because a nested list gave no way to tell which
     axis was which.
  4. The Level 2 brief has no length cap; Level 2 starts from the Level 1 run.
  5. A judge runs: Claude Opus 5.5, pinned, one request per run, exact
     quotations, twelve control cases.
  6. A blocked check fails and names the part that blocks it, instead of
     returning unresolved with reason `not_assessed`.
  7. Arrays are matched by dimension name and label; briefs state names,
     dimensions and units.
  8. A tolerance is a bound on floating-point error, declared per result and
     checked against the data in certification.
- Certification measured how often readings coincide. On the Kenya template
  clipped and unclipped increments give the same totals on all 48 instances and
  differ on all 48 once the controller injects a dip; weighted and unweighted
  regional means agree on all 48 and differ on 30 of 48 under changed data. On
  the seasonal template full-sample category boundaries change a result on 4 of
  6 instances. The changed-data probe is therefore necessary.
- One ambiguity was closed with a required intermediate product: the seasonal
  brief now asks for the observed category of each year.

## 2026-10-05: the first tooling comparison measured availability, not use

- Fourteen attempts compared three tooling images with everything else
  fixed: no added tooling, the Rhiza Research weather-skills catalog, and the
  ACCORD libraries. The images were the three matched images of the 1 October
  pilot. Each image ran two Kenya revision instances and two seasonal
  calibration instances.
- No run used its tooling's code. The two Kenya failures were the same
  window pitfall. The two failures with the Rhiza image were agent errors.
- Retained runs were cheaper on one template and slower on the other.

## 2026-10-04: one cheap model made the first 25 attempts

- Twenty-one attempts ran with gpt-6-luna through the Codex harness, then four
  more under spec version 2. A typical attempt took one to two minutes and
  45,000 to 195,000 tokens; all 25 used about three percentage points of the
  subscription's weekly allowance.
- Seven attempts covered the three templates on the default runtime image. A
  probe separated two readings on a real Kenya attempt, and reading the code
  confirmed the diagnosis.
- These attempts answered the first contract (results in `answer.json`, a
  changed-instance probe, results grouped by period). They are not reassessed
  under the revised rules; their computed checks stand as recorded, with the
  judge's verdicts added.

## 2026-10-03: the format replaced the first evaluator in six ways

1. The weighted rubric tree became a check list; each check is reported on
   its own instead of zeroing a rubric leaf worth 20 to 25 points.
2. Per-template evaluator code shrank to the reference function; probes are
   shared.
3. The judge stays in every mode with a narrower job: single checks and method
   pointers, each with a mandatory quote and three outcomes.
4. The three-outcome rule was kept, not introduced, and extended to every
   check.
5. Provenance moved from the agent to the controller.
6. The reference modules were kept, with a conventions argument.
