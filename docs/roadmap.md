# Roadmap for the agent weather benchmark

Status: draft of 7 October 2026, for discussion. It summarises the system as built, what is still to build, and the experiments the benchmark exists to run. Detail lives in [the task set](task-set.md) and [the assessment format](assessment-format.md).

## The benchmark compares whole forecasting systems, not models alone

- **The question.** Which agent systems can do operational weather and climate forecasting work, at what cost, and how much do the pieces around the model help: the harness, the supplied tools and knowledge, and earlier work.
- **A system is four things switched independently.** The language model; the harness that drives it (the built-in driver, the Codex adapter, the `rx` research harness); the substrate it is given (the Rhiza weather-skills catalog, the `acmadDL` data library, the `AfricaS2S` library); and the supplied structure (a conventions sheet, a method description, an earlier submission).
- **The tasks are templates.** Each task takes a region and a time window as parameters, so one template yields many instances, repeats are independent, and private instances cannot be memorised. The set has 25 templates, 16 drawn from the two earlier repositories and 9 new ones.
- **Every task declares one of three modes.** *Outcome* mode scores a forecast against withheld observations and prescribes no method. *Product* mode requires a named quantity, correct under any defensible reading of the brief. *Process* mode adds conformance to a published standard, step by step; the first standard is the WMO guidance on objective seasonal forecasting.
- **Every task has two levels.** Level 1 is "produce a valid output". Level 2 is "optimize it", scored on a leaderboard, as a separate submission with its own validity gate.

## The assessment is exact where it can be and narrow where it must judge

- **The agent delivers a small fixed envelope and is free in everything else.** Arrays go in a labelled Zarr store; single numbers, choices, claims and method entries go in `answer.json`; one command regenerates the results from the data; a short report explains them. Language, method and file layout are not constrained.
- **Seven check types cover the work.** Variant matching (which readings of the brief the numbers fit); invariants (rules any valid answer obeys); probes (reruns of the agent's own code on changed data); claim checks; process conformance against a standard's checklist; skill scoring; and interpretation, decided by a judge.
- **Every check returns pass, fail or unresolved, never merged.** Fail means the submission is at fault. Unresolved names a cause outside the submission, with a reason code. A wrong reading that the brief left open is accepted; a known pitfall is named.
- **The judge is pinned and narrow.** Claude Opus 5.5 answers one question at a time on exact quotations, with no tools. It has twelve control cases with known answers.
- **Each spec is certified by five tests.** Two independent reference implementations agree; a known-correct solution passes; deliberately incorrect solutions are caught by the right check; the separability of every accepted-versus-pitfall pair is measured; and cheap-model attempts leave no answer unclassified. Human scientific approval is a separate gate.
- **The controller keeps the provenance.** Input hashes, source versions, artifact hashes, the tool trace, substrate use (the monitor from pull request #1, extended to library imports), supplements handed over, and the parent episode.

## Three templates are built and certified; the rest of the system is in place

- Product, outcome and process mode each run end to end on one template: the Kenya forecast revision, weeks 3–4 rainfall with both levels, and seasonal rainfall calibration to the WMO guidance.
- All three pass the four automatic certification tests in the offline Docker runtime, and the fifth on 36 attempts by one cheap model (gpt-6-luna).
- The judge has run on all 36 attempts and on its control cases.
- Second episodes, the conventions-sheet condition and Level 2 feedback all work in the runner.
- The ten earlier packaged tasks are still assessed by the first evaluator, which is locked and unchanged.
- No task is approved by a domain scientist, three rulings on unknown answers await confirmation, and the WMO checklist is a draft from a secondary source.

## Six things remain to be built

1. **The other 22 templates.** Convert the 13 remaining existing tasks and build the 9 new ones, in the order the experiments need them: the subseasonal and seasonal rows first, the diagnostic pack last. Each needs a reference function, a second implementation, controls and certification.
2. **The standards.** Obtain WMO-No. 1246 and the long-range verification standard as primary documents, replace practice numbers with clauses, add a regional-centre procedure, and get each checklist signed off.
3. **The systems.** An `rx` harness configuration; Claude and frontier Codex solver systems, once a spending limit is agreed; open-weight models; the three substrate images rebuilt on the current runtime; a "method supplied" condition beside the conventions sheet.
4. **The missing pieces of the format.** Level 2 for process rows and the separate "optimization within the standard" track; Parquet delivery for tables; live data acquisition for the rows that need it; a reporting layer that turns run records into comparison tables and leaderboards.
5. **Validation of the judge.** A human-labelled set of about fifty questions drawn from real attempts, agreement measured per obligation, and a second judge model for disagreement checks.
6. **Approval and retirement.** A domain-scientist review of each template and checklist; a workflow for confirming rulings; migration of the ten packaged tasks and their studies off the first evaluator.

## Eight experiments are planned

Columns: what varies, what is held fixed, and what is measured.

| Experiment | What varies | What is fixed | What is measured |
| --- | --- | --- | --- |
| 1. Model ladder | Cheap to frontier models | Harness, no substrate, Level 1 | Pass rate per template, cost, tokens, time |
| 2. Harness | Built-in driver, Codex adapter, `rx` | Model | Same, plus tool calls per task |
| 3. Substrate value | None, Rhiza skills, `acmadDL`, `AfricaS2S` | Model and harness | Pass rate and cost; recorded use of the substrate, not just availability |
| 4. Supplied structure | Nothing, conventions sheet, method supplied | Model, harness, substrate | Where the difficulty lies: knowing the conventions or carrying them out |
| 5. Accretion | Episode sequences, retained against reset | System | Cost, tokens, time and pass rate of the second and third episode |
| 6. Level 2 leaderboard | Any method, within the budget and feedback limit | Private holdouts | Skill against the raw model and climatology; "within the standard" reported apart |
| 7. Judge validation | Judge model | Labelled cases | Agreement with human labels per obligation |
| 8. Spec robustness | New models and templates | The checks | Unknown-answer rate, unresolved rate and controller defects found per template |

- Experiments 1 and 3 can start as soon as a spending limit is set, on the three certified templates.
- Experiment 5 needs a sequence of instances per template, such as Ethiopia, then Kenya, then Nigeria, with the retained and reset arms run side by side.
- Experiment 8 is continuous: every new model attempt is also a test of the controller, and the first 25 attempts found eight controller defects.

## Five decisions are open

- **Spending.** No usage limit is agreed for frontier or Claude solvers. The judge runs on the subscription login at about eight cents of list price per run.
- **Exposure.** The repository is public and the branch holds the reference functions and control solutions. Private instances protect against memorisation; the reference code does not.
- **Data.** Scientific, scoring and redistribution approvals are false for every packaged task, and most Level 2 holdouts are public history, not untouched observations.
- **Standards.** Which regional-centre procedures to add, and who signs the checklists off.
- **Modes.** Five rows of the task set were assigned a mode without discussion.

## The near-term order is this

1. Agree the spending limit and run experiments 1 and 3 on the three certified templates.
2. Convert the next six subseasonal and seasonal templates and certify them.
3. Build the `rx` configuration and the rebuilt substrate images.
4. Obtain the WMO primary documents and sign off the first checklist.
5. Label fifty judge cases and measure agreement.
6. Run the accretion sequences, then the first full study across all systems.
