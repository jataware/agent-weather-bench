# Roadmap for the agent weather benchmark

Status: draft of 7 October 2026, for discussion. This page tells a new reader what the benchmark is, what is built, what is not built, and what experiments come next. It is short on purpose. [The results so far](results.md) show what the machinery catches, with a one-page figure of how it works and how it scales. [The task set](task-set.md) and [the assessment format](assessment-format.md) give the detail.

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

## A task is checked in one of three ways, and the way follows from the task

- **Product check.** The agent must deliver a named quantity. The controller compares it with a reference answer under every defensible reading of the brief, and names a known pitfall when it finds one. Used for outlooks, indices, verifications and audits.
- **Process check.** The agent must deliver the product and follow a published standard, step by step. The first standard is the WMO guidance on objective seasonal forecasting. Used for forecast production.
- **Outcome check.** The agent makes a forecast, and the controller scores it against withheld observations. Any method is acceptable. The only gate is validity: the right cases, the right units, no information from the future. Used where skill is the point.
- Every template has one of these as its Level 1, and the result is pass, fail or unresolved.
- **A leaderboard run is the same template under the outcome check.** We call it Level 2. The agent makes the forecast as good as it can, inside a fixed budget and a fixed number of score requests, and the result is a skill score. It is a separate submission that may start from the Level 1 one. Thirteen templates have a Level 2, because thirteen make a forecast that observations can score.

## Tasks are templates

- A template is a task with parameters. The region and the time window are parameters, so one template makes many instances.
- Repeats are independent, and private instances cannot be memorised.
- A second instance is a second episode. The agent gets its earlier submission and decides what to reuse. This is how we measure whether work accumulates.

## The set has 25 templates in six families

The family says what the work is. The check follows from it.

- **Outlook products, 6, product check.** Read raw provider forecasts and deliver a rainfall outlook, a heat outlook, the revision between two issues, a forecast of an extreme-event probability at weeks 2–3, and two checks of climate-driver forecasts: the Indian Ocean Dipole and the Madden–Julian Oscillation.
- **Observed indices and verification, 5, product check.** Compute an observed ocean index, verify forecasts against station observations, verify probabilistic forecasts with the standard scores, debug a scorecard with injected faults, and audit a paper against its code.
- **Seasonal forecast production, 6, process check.** Calibrate a seasonal rainfall forecast to the WMO guidance, run the short-rains workflow, reproduce a canonical-correlation forecast, calibrate a monthly cycle, combine probability forecasts, and combine several models with their hindcasts.
- **Subseasonal forecast production, 4, process or outcome check.** Forecast weeks 3–4 rainfall, issue probabilistic weeks 3–4 and 5–6 outlooks, forecast rainy-season onset and dry spells, and forecast week by week as observations arrive.
- **Research claims and consensus, 2, process check.** Test a published predictor claim on held-out years, and beat the regional consensus forecast on backcast skill. These two and the week-by-week forecast are the ones a frontier agent should not simply pass.
- **Downscaling and the diagnostic pack, 2, product check.** Downscale rainfall to a fine grid with conservation, and a pack of ten one-step data operations that counts as one entry.
- [The task set](task-set.md) gives each template its parameters, its check, its leaderboard and its evidence so far.

## The controller checks a delivery in seven ways

- **The delivery is small and fixed.** Arrays go in a labelled Zarr store. Single numbers, choices, claims and method notes go in `answer.json`. One command makes the results again from the data. A short report explains them.
- **Seven kinds of check cover the work.** Variant matching (which readings of the brief fit the numbers), invariants (rules every valid answer obeys), probes (reruns of the agent's code on changed data), claim checks, process conformance, skill scoring, and interpretation.
- **Every check gives pass, fail or unresolved.** Fail means the submission is at fault. Unresolved names a cause outside the submission. The two are never mixed.
- **A judge decides the questions that no computation can settle.** The judge is Claude Opus 5.5. It answers one narrow question at a time and must quote the exact text it relies on. It has twelve control cases with known answers.
- **Each task spec is certified by five tests** before it counts: two independent reference implementations agree; a correct solution passes; wrong solutions fail on the right check; the separability of each pitfall is measured; cheap-model attempts leave no answer unclassified.
- **The controller keeps the provenance.** It records input hashes, source versions, artifact hashes, the tool trace, substrate use, supplied material and the parent episode. The agent writes none of it.

## This is built today

- Three templates run end to end, one per check: the Kenya forecast revision (product), weeks 3–4 rainfall with its leaderboard (outcome), and seasonal rainfall calibration to the WMO guidance (process).
- All three pass the four automatic certification tests in the offline Docker runtime, and the fifth test on 36 attempts by one cheap model.
- The judge has run on all 36 attempts and on its control cases.
- Second episodes, the conventions-sheet condition and the Level 2 feedback tool work in the runner.
- The ten earlier packaged tasks still use the first evaluator, which is locked and unchanged.
- No task has scientific approval. Three rulings on unknown answers wait for confirmation. The WMO checklist is a draft from a secondary source.

## These things are not built yet

Templates

- Convert the Kenya rainfall outlook and the Kenya heat outlook to templates.
- Convert the Indian Ocean Dipole index and the Indian Ocean Dipole forecast check.
- Convert scorecard debugging, station verification and the paper-versus-code audit.
- Convert probability forecast combination, the short-rains workflow, the seasonal CCA reproduction and the monthly cyclic calibration.
- Convert rainfall downscaling and the diagnostic pack.
- Build rainy-season onset and dry spells.
- Build probabilistic forecast verification.
- Build multi-model combination with hindcasts.
- Build the test of a published predictor claim.
- Build "beat the regional consensus forecast".
- Build the probabilistic weeks 3–4 and 5–6 outlook.
- Build weekly forecasting with observation updates.
- Build the Madden–Julian Oscillation forecast check.
- Build the extreme-event probability at weeks 2–3.
- Write a second, independent reference implementation for each new template.
- Write the control solutions, correct and deliberately wrong, for each new template.
- Certify each template and record it.
- Add leaderboards to the process-checked forecast templates that can have one.

Standards

- Obtain WMO-No. 1246, the guidance on objective seasonal forecasting, as a primary document, and keep a hashed copy.
- Obtain the WMO long-range verification standard the same way.
- Replace each practice number in the seasonal checklist with the clause it comes from.
- Add any step the primary text requires that the draft lacks.
- Add one regional-centre forecasting procedure as a second standard.
- Get a domain scientist to sign off each checklist.

Systems

- Write the `rx` harness configuration and adapter.
- Add a Claude solver system, once a spending limit is agreed.
- Add the frontier Codex solver, once a spending limit is agreed.
- Add one or two open-weight model systems.
- Rebuild the three substrate images (none, Rhiza skills, ACCORD libraries) on the current runtime, so they stop crashing on exit.
- Write the "method supplied" supplement for the templates that have a canonical method.
- Write a conventions sheet for each template that has conventions.

Assessment format

- Build the separate "optimization within the standard" track.
- Add Parquet and GeoParquet delivery for tabular results, with `pyarrow` in the runtime image.
- Add live data acquisition for the templates that need it, through the controller's logged acquisition tool.
- Build the reporting layer: run records into comparison tables, episode-sequence tables and leaderboards.
- Rename `mode` and `level` in the code and specs to match the words in this roadmap, if we decide to.

Judge

- Draw about fifty judge questions from real attempts and have a person label them.
- Measure agreement with the labels per question type.
- Add a second judge model and record where the two disagree.
- Write control cases for each new interpretation obligation a template adds.

Approval and retirement

- Confirm or reject the three proposed rulings on unknown answers.
- Write the procedure for confirming a ruling and issuing a spec version.
- Get a domain scientist's review of each certified template.
- Record scientific, scoring and redistribution approval for each data source.
- Choose a repository licence.
- Decide what to do about the reference code in a public repository.
- Migrate the ten packaged tasks and their studies off the first evaluator, then retire it and its lock.

## Eight experiments are planned

Columns: what we change, what we keep the same, and what we measure.

| Experiment | What we change | What we keep the same | What we measure |
| --- | --- | --- | --- |
| 1. Model ladder | Cheap to frontier models | Harness, no substrate, no leaderboard | Pass rate per template, cost, tokens, time |
| 2. Harness | Built-in driver, Codex adapter, `rx` | Model | The same, plus tool calls per task |
| 3. Substrate value | None, Rhiza skills, `acmadDL`, `AfricaS2S` | Model and harness | Pass rate and cost, and the recorded use of the substrate |
| 4. Supplied structure | Nothing, conventions sheet, method supplied | Model, harness, substrate | Where the difficulty is: to know the conventions, or to apply them |
| 5. Accretion | Episode sequences, retained against reset | System | Cost, tokens, time and pass rate of the second and third episode |
| 6. Leaderboard | Any method, inside the budget and feedback limit | Private holdouts | Skill against the raw model and climatology |
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
- **Checks.** Five templates got their kind of check without discussion.

## The near-term order is this

1. Agree the spending limit. Run experiments 1 and 3 on the three certified templates.
2. Convert the next six subseasonal and seasonal templates and certify them.
3. Build the `rx` configuration and the rebuilt substrate images.
4. Get the WMO primary documents and sign off the first checklist.
5. Label fifty judge cases and measure agreement.
6. Run the accretion sequences, then the first full study across all systems.
