# Roadmap

Status: draft of 7 October 2026, for discussion. This page tells a new reader what the benchmark is, what is built, what is not built, and what experiments come next. It is short on purpose. [The results so far](results.md) show what the machinery catches, with a one-page figure of how it works and how it scales. [The task set](task-set.md) and [the assessment format](assessment-format.md) give the detail.

![A task and its tooling go into a sandbox with an agent; the controller inspects what comes out](figures/overview.png)

## The question

- With which model, harness, tooling and supplements can we hand a forecaster's task to an AI agent system and get back the right result?
- "A forecaster's task" is one of the canonical workflows of subseasonal-to-seasonal forecasting: literature and method research, data acquisition and preparation, calibration and model combination, downscaling, verification, and the issue of a seasonal or subseasonal outlook with its uncertainty.
- "The right result" is a product that an independent check confirms, made by a method the task permits, with conclusions the evidence supports.
- The system is the model, the harness and the tooling, defined next; the supplements and the budget of time and tokens are set per run. A system is a model plus a harness plus tooling, together with the budget of time and tokens.
- The benchmark measures, for each system and each set of supplements, the pass rate, the cost, the time, and the point at which an expert must step in.

## The system under evaluation

- **The model.** The language model, from small open-weight models to frontier models.
- **The harness.** The agent loop that drives the model. Examples: the built-in driver, Codex, the `rx` research harness. The controller (the trusted evaluator, defined below) is not a harness.
- **The tooling.** The skills, libraries and knowledge in the agent's workspace. Examples: the Rhiza weather-skills catalog, the `acmadDL` data library, the `AfricaS2S` library.
- **The supplements.** Material added to one run with `--supply` or `--parent`: a sheet of conventions, a description of the method, or the agent's own earlier submission.
- We change one part at a time and keep the other three the same. That is how we measure the value of each part.

## Tasks

- A task gives the agent a short brief, a folder of data, and a fixed budget of time and tokens.
- The brief states the product: the arrays, the numbers and the conclusions the agent must submit. It does not state the method.
- The agent works in a sandbox with no network. It writes code, runs it, and submits its results, its report and the command that makes the results again.
- The controller then checks the submission. The controller is the trusted program that runs the agent, holds the private reference answers and runs the checks.
- Each task has a reference answer or a set of withheld observations, so the checks are exact. Each task also has known wrong methods, called pitfalls, so a wrong answer gets a name.

## Modes and levels

- **Product mode.** The agent must submit a named quantity. The controller compares it with a reference answer under every defensible reading of the brief, and names a known pitfall when it finds one. Used for outlooks, indices, verifications and audits.
- **Process mode.** The agent must submit the product and follow a published standard, step by step. The first standard is the WMO guidance on objective seasonal forecasting. Used for forecast production.
- **Outcome mode.** The agent makes a forecast, and the controller scores it against withheld observations. Any method is acceptable. The only requirement is validity: the right issues and cells, the right units, no information from the future. Used where skill is the point.
- Every template has one of these modes as its Level 1, and the result is pass, fail or unresolved.
- **A Level 2 run is the same template in outcome mode, ranked on a leaderboard.** We call it Level 2. The agent makes the forecast as good as it can, inside a fixed budget and a fixed number of score requests, and the result is a skill score. It is a separate submission that may start from the Level 1 one. Thirteen templates have a Level 2, because thirteen make a forecast that observations can score.

## Templates, instances and episodes

- A template is a task with parameters. The region and the time window are parameters, so one template makes many instances.
- Repeats are independent, and private instances cannot be memorised.
- A second instance is a second episode. The agent gets its earlier submission and decides what to reuse. This is how we measure whether work accumulates.

## The template set

The family says what the work is. The check follows from it.

- **Outlook products, 6, product mode.** Read raw provider forecasts and produce a rainfall outlook, a heat outlook, the revision between two issues, a forecast of an extreme-event probability at weeks 2–3, and two checks of climate-driver forecasts: the Indian Ocean Dipole and the Madden–Julian Oscillation.
- **Observed indices and verification, 5, product mode except one.** Compute an observed ocean index, verify forecasts against station observations, verify probabilistic forecasts with the standard scores (template 18, the one process-mode entry of this family), debug a scorecard with injected faults, and audit a paper against its code.
- **Seasonal forecast production, 6, process mode.** Calibrate a seasonal rainfall forecast to the WMO guidance, run the short-rains workflow, reproduce a canonical-correlation forecast, calibrate a monthly cycle, combine probability forecasts, and combine several models with their hindcasts.
- **Subseasonal forecast production, 4, process or outcome mode.** Forecast weeks 3–4 rainfall, issue probabilistic weeks 3–4 and 5–6 outlooks, forecast rainy-season onset and dry spells, and forecast week by week as observations arrive.
- **Research claims and consensus, 2, process mode.** Test a published predictor claim on held-out years, and beat the regional consensus forecast on backcast skill. The consensus forecast (template 21) and the week-by-week forecast (template 23) are the two frontier-hard templates, the ones a frontier agent should not simply pass.
- **Downscaling and the diagnostic pack, 2, product mode.** Downscale rainfall to a fine grid with conservation, and a pack of ten one-step data operations that counts as one entry.
- [The task set](task-set.md) gives each template its parameters, its check, its leaderboard and its evidence so far.

## The checks

- **The submission is small and fixed.** Arrays go in a labelled Zarr store. Single numbers, choices, claims and method notes go in `answer.json`. One command makes the results again from the data. A short report explains them.
- **Ten check types cover the work.** Envelope and coverage (the submission is readable and complete), variant matching (which readings of the brief fit the numbers), invariants (rules every valid answer obeys), probes (reruns of the agent's code on changed data), claim checks, process conformance, the Level 2 feedback limit, skill scoring, and interpretation.
- **Every check gives pass, fail or unresolved.** Fail means the submission is at fault. Unresolved names a cause outside the submission. The two are never mixed.
- **A judge decides the questions that no computation can settle.** The judge is Claude Opus 5.5. It answers one narrow question at a time and must quote the exact text it relies on. It has twelve control cases with known answers.
- **Each task spec is certified by five tests** before it counts: two independent reference implementations agree; a correct submission passes; wrong submissions fail on the right check; the separability of each pitfall is measured; cheap-model attempts leave no answer unclassified.
- **The controller keeps the provenance.** It records input hashes, source versions, artifact hashes, the tool trace, tooling use, supplements and the parent episode. The agent writes none of it.

## Built components

- Three templates run end to end, one per check: the Kenya forecast revision (product), weeks 3–4 rainfall with its leaderboard (outcome), and seasonal rainfall calibration to the WMO guidance (process).
- All three pass the four automatic certification tests in the offline Docker runtime, and the fifth test on the attempts assessed under the current fingerprint by one cheap model: 4 on the Kenya forecast revision, 3 on weeks 3–4 rainfall and 4 on seasonal calibration. The 25 earlier attempts were assessed under the first submission contract.
- The judge has run on all 36 attempts and on its control cases.
- Second episodes, the conventions-sheet supplement and the Level 2 feedback tool work in the runner.
- The first evaluator (generation 1, ten task packages) is archived under `archive/evaluator-v1-2026-10/` and no longer verified.
- No task has scientific approval. Three rulings on unknown answers wait for confirmation. The WMO checklist is a draft from a secondary source.

## Work remaining

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
- Write the control submissions, correct and deliberately wrong, for each new template.
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
- Rebuild the three tooling images that exist (no tooling, the Rhiza skills catalog, the ACCORD libraries) on the current runtime, so they stop crashing on exit. The conventions sheet is not an image: it is a supplement handed in with `--supply conventions`.
- Write the "method supplied" supplement for the templates that have a canonical method.
- Write a conventions sheet for each template that has conventions.

Assessment format

- Build the separate "optimization within the standard" track.
- Add Parquet and GeoParquet submission of tabular results, with `pyarrow` in the runtime image.
- Add live data acquisition for the templates that need it, through the controller's logged acquisition tool.
- Build the reporting layer: run records into comparison tables, episode-sequence tables and leaderboards.
- Rename `mode` and `level` in the code and specs to match the words in this roadmap, if we decide to.

Judge

- Draw about fifty judge questions from real attempts and have a person label them.
- Measure agreement with the labels per question type.
- Add a second judge model and record where the two disagree.
- Write control cases for each new interpretation check a template adds.

Approval and retirement

- Confirm or reject the three proposed rulings on unknown answers.
- Write the procedure for confirming a ruling and issuing a spec version.
- Get a domain scientist's review of each certified template.
- Record scientific, scoring and redistribution approval for each data source.
- Choose a repository licence.
- Decide what to do about the reference code in a public repository.
- Port the still-useful archived task packages to templates.

## Planned experiments

Columns: what we change, what we keep the same, and what we measure.

| Experiment | What we change | What we keep the same | What we measure |
| --- | --- | --- | --- |
| 1. Model ladder | Cheap to frontier models | Harness, no tooling, no Level 2 | Pass rate per template, cost, tokens, time |
| 2. Harness | Built-in driver, Codex, `rx` | Model | The same, plus tool calls per task |
| 3. Tooling value | None, Rhiza skills, `acmadDL`, `AfricaS2S` | Model and harness | Pass rate and cost, and the recorded use of the tooling |
| 4. Supplements | Nothing, conventions sheet, method description | Model, harness, tooling | Where the difficulty is: to know the conventions, or to apply them |
| 5. Accretion | Episode sequences, retained against reset | System | Cost, tokens, time and pass rate of the second and third episode |
| 6. Leaderboard | Any method, inside the budget and feedback limit | Private holdouts | Skill against the raw model and climatology |
| 7. Judge validation | Judge model | Labelled cases | Agreement with human labels per question type |
| 8. Spec robustness | New models and templates | The checks | Unknown answers, unresolved outcomes and controller defects per template |

- Experiments 1 and 3 can start on the three certified templates as soon as a spending limit is set.
- Experiment 5 needs a sequence of instances per template, for example Ethiopia, then Kenya, then Nigeria, with the retained and the reset arm run side by side.
- Experiment 8 is continuous. Each new model attempt also tests the controller. The first 25 attempts found eight controller defects.

## Open decisions

- **Spending.** No usage limit is agreed for frontier or Claude solvers. The judge runs on the subscription login at about eight cents of list price per run.
- **Exposure.** The repository is public, and the branch holds the reference functions and the control submissions. Private instances protect against memorisation. The reference code does not.
- **Data.** Scientific, scoring and redistribution approvals are false for every template. Most Level 2 holdouts are public history, not untouched observations.
- **Standards.** Which regional-centre procedures to add, and who signs the checklists off.
- **Checks.** Five templates got their kind of check without discussion.

## Order of work

1. Agree the spending limit. Run experiments 1 and 3 on the three certified templates.
2. Convert the next six subseasonal and seasonal templates and certify them.
3. Build the `rx` configuration and the rebuilt tooling images.
4. Get the WMO primary documents and sign off the first checklist.
5. Label fifty judge cases and measure agreement.
6. Run the accretion sequences, then the first full study across all systems.
