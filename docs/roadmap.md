# Roadmap for the agent weather benchmark

Status: draft of 7 October 2026, for discussion. This page tells a new reader what the benchmark is, what is built, what is not built, and what experiments come next. It is short on purpose. [The task set](task-set.md) and [the assessment format](assessment-format.md) give the detail.

## The benchmark asks one question

- Under what conditions can we hand a forecaster's task to an AI agent system and get back the right result?
- "A forecaster's task" is one of the canonical workflows of subseasonal-to-seasonal forecasting: literature and method research, data acquisition and preparation, calibration and model combination, downscaling, verification, and the issue of a seasonal or subseasonal outlook with its uncertainty.
- "The right result" is a product that an independent check confirms, made by a method the task permits, with conclusions the evidence supports.
- "Conditions" are the model, the harness, the substrate and the supplied structure, defined next, together with the budget of time and tokens.
- The benchmark measures, for each condition, the pass rate, the cost, the time, and the point at which an expert must step in.

## A system under evaluation has four parts

- **The model.** The language model, from small open-weight models to frontier models.
- **The harness.** The agent loop that drives the model. Examples: the built-in driver, the Codex adapter, the `rx` research harness.
- **The substrate.** The tools and knowledge in the agent's workspace. Examples: the Rhiza weather-skills catalog, the `acmadDL` data library, the `AfricaS2S` library.
- **The supplied structure.** Material added to one run: a sheet of conventions, a description of the method, or the agent's own earlier submission.
- We change one part at a time and keep the other three the same. That is how we measure the value of each part.

## A task is a forecasting job with a checkable result

- A task gives the agent a short brief, a folder of data, and a fixed budget of time and tokens.
- The brief states the product: the arrays, the numbers and the conclusions the agent must deliver. It does not state the method.
- The agent works in a sandbox with no network. It writes code, runs it, and delivers its results, its report and the command that makes the results again.
- The controller then checks the delivery. The controller is the trusted program that runs the agent, holds the private reference answers and runs the checks.
- Each task has a reference answer or a set of withheld observations, so the checks are exact. Each task also has known wrong methods, called pitfalls, so a wrong answer gets a name.

## Tasks come in three modes

- **Outcome mode.** The agent makes a forecast. The controller scores it against withheld observations. Any method is acceptable. The only gate is validity: correct cases, correct units, no information from the future.
- **Product mode.** The agent must deliver a named quantity. The controller accepts any defensible reading of the brief and names a known pitfall when it finds one.
- **Process mode.** The agent must deliver the product and follow a published standard, step by step. The first standard is the WMO guidance on objective seasonal forecasting.

## Tasks have two levels

- **Level 1** asks for a valid output. The result is pass, fail or unresolved.
- **Level 2** asks the agent to make the output as good as it can. The result is a skill score on a leaderboard. Level 2 is a separate submission with its own validity gate.
- A Level 2 run can start from the Level 1 submission.

## Tasks are templates

- A template is a task with parameters. The region and the time window are parameters, so one template makes many instances.
- Repeats are independent, and private instances cannot be memorised.
- The set has 25 templates: 16 come from two earlier repositories and 9 are new. [The task set](task-set.md) lists them.
- A second instance is a second episode. The agent gets its earlier submission and decides what to reuse. This is how we measure whether work accumulates.

## The assessment is exact where it can be, and narrow where it must judge

- **The delivery is small and fixed.** Arrays go in a labelled Zarr store. Single numbers, choices, claims and method notes go in `answer.json`. One command makes the results again from the data. A short report explains them.
- **Seven check types cover the work.** Variant matching (which readings of the brief fit the numbers), invariants (rules every valid answer obeys), probes (reruns of the agent's code on changed data), claim checks, process conformance, skill scoring, and interpretation.
- **Every check gives pass, fail or unresolved.** Fail means the submission is at fault. Unresolved names a cause outside the submission. The two are never mixed.
- **A judge decides the questions that no computation can settle.** The judge is Claude Opus 5.5. It answers one narrow question at a time and must quote the exact text it relies on. It has twelve control cases with known answers.
- **Each task spec is certified by five tests** before it counts: two independent reference implementations agree; a correct solution passes; wrong solutions fail on the right check; the separability of each pitfall is measured; cheap-model attempts leave no answer unclassified.
- **The controller keeps the provenance.** It records input hashes, source versions, artifact hashes, the tool trace, substrate use, supplied material and the parent episode. The agent writes none of it.

## This is built today

- Three templates run end to end, one per mode: the Kenya forecast revision (product), weeks 3–4 rainfall with both levels (outcome), and seasonal rainfall calibration to the WMO guidance (process).
- All three pass the four automatic certification tests in the offline Docker runtime, and the fifth test on 36 attempts by one cheap model.
- The judge has run on all 36 attempts and on its control cases.
- Second episodes, the conventions-sheet condition and the Level 2 feedback tool work in the runner.
- The ten earlier packaged tasks still use the first evaluator, which is locked and unchanged.
- No task has scientific approval. Three rulings on unknown answers wait for confirmation. The WMO checklist is a draft from a secondary source.

## Six things are not built yet

1. **The other 22 templates.** Convert the 13 remaining existing tasks and build the 9 new ones. Do the subseasonal and seasonal rows first. Each template needs a reference function, a second implementation, controls and certification.
2. **The standards.** Get the WMO documents as primary sources. Replace each practice number with its clause. Add a regional-centre procedure. Get each checklist signed off.
3. **The systems.** An `rx` harness configuration. Claude and frontier Codex solvers, once a spending limit is agreed. Open-weight models. The three substrate images rebuilt on the current runtime. A "method supplied" condition.
4. **The missing parts of the format.** Level 2 for process rows. A separate "optimization within the standard" track. Parquet delivery for tables. Live data acquisition where a task needs it. A reporting layer that turns run records into tables and leaderboards.
5. **Validation of the judge.** About fifty questions from real attempts, labelled by a person. Agreement measured per question type. A second judge model for disagreement checks.
6. **Approval and retirement.** Domain-scientist review of each template and checklist. A procedure to confirm rulings. Migration of the ten packaged tasks off the first evaluator.

## Eight experiments are planned

Columns: what we change, what we keep the same, and what we measure.

| Experiment | What we change | What we keep the same | What we measure |
| --- | --- | --- | --- |
| 1. Model ladder | Cheap to frontier models | Harness, no substrate, Level 1 | Pass rate per template, cost, tokens, time |
| 2. Harness | Built-in driver, Codex adapter, `rx` | Model | The same, plus tool calls per task |
| 3. Substrate value | None, Rhiza skills, `acmadDL`, `AfricaS2S` | Model and harness | Pass rate and cost, and the recorded use of the substrate |
| 4. Supplied structure | Nothing, conventions sheet, method supplied | Model, harness, substrate | Where the difficulty is: to know the conventions, or to apply them |
| 5. Accretion | Episode sequences, retained against reset | System | Cost, tokens, time and pass rate of the second and third episode |
| 6. Level 2 leaderboard | Any method, inside the budget and feedback limit | Private holdouts | Skill against the raw model and climatology |
| 7. Judge validation | Judge model | Labelled cases | Agreement with human labels per question type |
| 8. Spec robustness | New models and templates | The checks | Unknown answers, unresolved outcomes and controller defects per template |

- Experiments 1 and 3 can start on the three certified templates as soon as a spending limit is set.
- Experiment 5 needs a sequence of instances per template, for example Ethiopia, then Kenya, then Nigeria, with the retained and the reset arm run side by side.
- Experiment 8 is continuous. Each new model attempt also tests the controller. The first 25 attempts found eight controller defects.

## Five decisions are open

- **Spending.** No usage limit is agreed for frontier or Claude solvers. The judge runs on the subscription login at about eight cents of list price per run.
- **Exposure.** The repository is public, and the branch holds the reference functions and the control solutions. Private instances protect against memorisation. The reference code does not.
- **Data.** Scientific, scoring and redistribution approvals are false for every packaged task. Most Level 2 holdouts are public history, not untouched observations.
- **Standards.** Which regional-centre procedures to add, and who signs the checklists off.
- **Modes.** Five rows of the task set got a mode without discussion.

## The near-term order is this

1. Agree the spending limit. Run experiments 1 and 3 on the three certified templates.
2. Convert the next six subseasonal and seasonal templates and certify them.
3. Build the `rx` configuration and the rebuilt substrate images.
4. Get the WMO primary documents and sign off the first checklist.
5. Label fifty judge cases and measure agreement.
6. Run the accretion sequences, then the first full study across all systems.
