# Next experiments

Updated 13 October 2026. The [README](../README.md) explains the benchmark and
why the direction changed; [authoring](../templates/README.md) explains how to
build a task; the [assessment contract](assessment-format.md) defines judgement.

## The roadmap has one goal

Build, control-run, review and launch one long-horizon composition task, and
observe where each system goes wrong in it. Nothing else is scheduled until its
traces have been read. The README's section on hard, gradable and canonical
tasks gives the reasoning; this page gives the plan.

## What the first round established

Eleven executable templates exist. Every fresh high-effort attempt under a
working contract passed them, each in a few minutes. The failures on record are
budget, precision-contract and packaging failures, plus two historical
preparation errors by one model under earlier contracts. The three open-method
candidates had no headroom over climatology. The tooling studies measured
library availability and a task-specific time signal, not a harness effect.
The dated reports hold the evidence: the [grading checkpoint](checkpoint-2026-10-08.md),
the [focused study](focused-study-2026-10-08.md), the
[parallel investigations](parallel-investigations-2026-10-08.md), the
[two-track investigation](two-track-investigation-2026-10-08.md), the
[hard-task search](hard-task-search-2026-10-08.md) and the
[tooling breadth study](tooling-breadth-study-2026-10-08.md). The historical
contracts and assessments stay as they are.

## The task is a regional objective seasonal outlook

The job is the one a regional centre's forecaster receives: produce the
objective seasonal rainfall outlook for a region and season from the raw
archives, and write the bulletin. Its stages are acquire, prepare, calibrate,
combine, verify, issue and write. Where a stage already has a template
(consolidation, calibration, CCA reproduction, the MAM outlook), the
composition reuses that template's instruments as its stage rubric.

- **Instances.** Two or three, varying season and region, so a system
  weakness can be told from a quirk of one instance.
- **Fixed or open, per stage.** Where the centre's practice is fixed (the
  CCA setup, the consolidation rule, the tercile definitions) the brief
  prescribes it and the stage is reference-matched. Where practice is open
  (predictor domain, treatment of a missing centre, bulletin wording) the stage
  is graded by invariants, information boundaries and judge questions. This
  decision is written in the task record before the brief.
- **Control.** The ICPAC consensus reconstruction in `ACCORD/from_icpac/` is
  the known-correct end-to-end control. Running it at full scale proves the
  task is attainable and gives every stage its reference. No skill-headroom
  gate applies, because skill is reported and not gated.
- **Inputs.** The raw provider responses the controller freezes, not
  curator-normalized arrays. Preparation is part of the job.
- **Budget.** Hours, hundreds of tool calls, a token allowance to match. The
  task declares its own budget tier; the cheap tier stays for the existing
  templates.

## Execution order

1. Write the task record: the stages, the fixed-or-open decision and the
   instruments for each, the rollup, the instances and the budget.
   Done 9 October 2026: `designs/objective-seasonal-outlook.md`.
2. Build the composition and run the correct control end to end at full
   scale. Plant one fault per stage and confirm each fires in its own stage
   and nowhere else. Done 9 October 2026: certification tests 1 to 4 pass on
   both instances (`docs/objective-outlook-control-2026-10-09.md`); test 5
   waits on Docker.
3. Add the per-stage rubric and declared rollup to the assessment format as a
   versioned change. Each stage keeps its own verdict; the composite reports a
   stage profile and a fractional score. Existing templates are unchanged.
   Done 9 October 2026 (`assessment/stages.py`, spec version 2 of the
   template): certification tests 1 to 4 pass on both instances under the
   stage rubric (`docs/objective-outlook-control-2026-10-09.md`); test 5
   waits on Docker.
4. Review the task before any model call: the brief as the agent sees it,
   every rubric row, the controls, the budget and the cost estimate. The
   review is recorded. A domain scientist's reading is sought here if one is
   available, and is not a precondition. Done 11 October 2026:
   `docs/objective-outlook-review-2026-10-11.md` (own pass plus a cold read by
   a context-free agent; fourteen open conventions pinned; judge given the
   bulletin's figures; budget tier set; re-certified).
5. Run one cheap system on one instance, once. Its purpose is to expose
   contract and controller defects and to give the first full trace, not to
   produce a result. Defects are diagnosed on controls and fixed as versioned
   changes; the agent is not retried. Done 11 October 2026 with
   `systems/outlook-pilot-codex-luna` on MAM 2015
   (`docs/objective-outlook-pilot-2026-10-11.md`): four controller and
   contract defects found and fixed (a coverage gap no longer blanks every
   stage; stage rows quote their reasons; the envelope states the read-only
   rerun; two identity checks say where), one new control, and the first
   full trace. The agent stopped after 4 minutes with CCA undone.
6. Run the tooling ablation: four arms on one backbone and one harness, so
   that the only difference between arms is the weather tooling. Decided
   12 October 2026 (`experiments/ablation-plan-2026-10-12.yaml`,
   `docs/objective-outlook-ablation-2026-10-12.md`): the backbone is Claude
   Sonnet 5.5 through the benchmark's own Anthropic controller, because a
   workhorse model shows whether tooling gives real uplift where a frontier
   model would hand-roll the mathematics; harness comparisons are dropped as
   developer minutiae. The arms on MAM 2015 are plain Python, the ACCORD
   libraries without their guides, the skills (Rhiza catalog and the ACCORD
   guides) without the libraries, and the full stack. Every arm's record
   carries, beside the stage profile, which library functions the delivered
   command actually called in a traced replay, so adoption is reported and
   not inferred from imports. Authorized 13 October 2026 ($160, $40 per
   arm); the owner asked for the arms to run in parallel. Arms 1 and 2 ran
   that day: both submitted a full pipeline in about seven minutes for
   under $1 each and passed seven of eight stages; the eighth exposed a
   reference defect (model means not zeroed off support), fixed and
   re-certified the same day. Arms 3 and 4 ran that afternoon: all four
   arms pass 8 of 8, arms 2 to 4 delivered one pipeline, and no arm called
   a library. The owner then had the directions withheld instead
   (`assessment.directions`, rungs `no-streams` and `brief-only` on the
   plain and full arms): plain Python drops to 4 of 8 without the stream
   sections and the full stack recovers CCA and eReg by calling africas2s,
   the first substantive use and uplift recorded, from one attempt. WVG
   fails everywhere without its section, and the library's WVG definition
   disagrees with the practice sheet. Record: the ablation page.
7. Decide the next task from what the traces show, and only then.

## Budgets and cost

Paid API calls, judging and retries keep the user-authorized $100 cap for
steps 1 to 5. The pilot ran on a subscription, so the per-attempt estimate for
step 6 comes from the pilot's trace and Sonnet 5.5's published prices with
prompt caching: about $10 per arm in the typical case and $40 at each arm's
cap, $160 for the four arms at most. The owner authorized that cap on 13
October 2026; the first two arms cost $0.63 and $0.71 of agent time plus
the judge. Subscription-backed usage is recorded
separately from actual API charges. Scientific native I/O stays serial per
process with at most two shared workers; the composition's budget does not
change that rule.

## What this round must establish

- At which stage each system goes wrong, and whether the stage is the same
  across instances.
- Whether a failure is scientific, a contract misunderstanding, a budget stop
  or a controller defect, from the trace and the stage verdicts.
- Whether the per-stage rubric ranks systems that do not finish the task.
- Whether the full trace of a multi-hour attempt is readable enough to answer
  the first two questions without rerunning anything.

## What waits

These are preserved, not scheduled: the adaptive weeks 3–4 comparator, an OND
open-method target with SST predictors, raw-data variants of the single-stage
templates, the sequential weekly-updating prototype, the five-by-five system
matrix, repeats on the existing templates, and domain-scientist review of the
25-entry portfolio in [the task set](task-set.md). Each is picked up or dropped
according to what the composition's traces show.
