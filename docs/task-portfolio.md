# Candidate forecasting research tasks

Discussion draft, 2 October 2026. These twelve candidates span the three requested
sources: existing centre replication work, published outlooks, and literature.
They are four families of three related tasks, not twelve independent samples or
a launched benchmark. Their suggested chains are optional scientific relationships;
each task can appear independently in a benchmark-wide accretion sequence.
Order and retention belong to the experiment, not a required follow-up field in
the task. Each row still needs a reviewed source record, a frozen
instance and a validated reference before it can enter evaluation.

Every task produces code, numerical results, provenance and a short scientific
report. Each sequence task also runs from a fresh workspace in the reset control.
Negative or inconclusive scientific findings can complete a task.

## Family A Seasonal calibration and transfer

Source: [the existing seasonal contract](../archive/pilot-2026-10-01/tasks/seasonal.yaml),
[the executed smoke contract](../archive/pilot-2026-10-01/smoke/task.yaml), and
[the revised protocol](../archive/pilot-2026-10-01/revision/PLAN.txt). This is the most immediately useful
development family. The reference uses a Kenyan study box, not national rainfall.

| Candidate | Agent goal and artifact | Verifiable success | Readiness and research value |
| --- | --- | --- | --- |
| A1 Reproduce the seasonal processing and fit | Aggregate September-issued ECMWF monthly rainfall and CHIRPS to OND on the specified grid; validate a documented calibration within training folds; save development predictions and fitted state | Aggregated inputs agree with the independent reference; development outputs cover the specified years; fold construction prevents leakage; replay regenerates the outputs | Existing inputs and checks support a development fixture. The smoke used 1993–2004 for training and inspected 2005–08 for prediction; do not relabel those years as untouched evaluation |
| A2 Apply the saved forecast workflow | Produce forecasts for a new issue/batch with the training period fixed; provide a record of retained code and model state | Frozen prediction accepts unseen forecast input, returns valid probabilities and rainfall, and loads the saved fit; fit-state hashes and independent execution support the reuse claim | Existing follow-up is a fixture; new batches need audited vintage/system consistency. Tests the simplest form of operational reuse |
| A3 Transfer the calibration workflow | Adapt it to a predeclared neighbouring study box on the same source grid, refit on that box's training data, and compare calibration with raw ensembles and climatology | New spatial support and aggregation are correct; parameters and thresholds use only allowed local training data; private scores are independently computed | Freeze actual bounds and sufficient cases before launch. Tests code and methodological transfer beyond simply reusing one fitted model; a skill loss is an acceptable finding |

A1 permits different sound calibration methods, as the current contract does.
For a strict numerical reproduction variant, name the method and all relevant
choices in a separate task version. Do not require arbitrary predictions to match
one preferred calibration.

## Family B Reconstruct and verify a centre outlook

Sources: [ACMAD replication snapshot](../tasks/acmad-objective/source-material/ACMAD_forecast_replication/README.md.txt) and its
[open questions snapshot](../tasks/acmad-objective/source-material/ACMAD_forecast_replication/OPEN_QUESTIONS.md.txt),
[ICPAC MAM replication snapshot](source-material/icpac-mam-replication-README.txt), and the
[GHACOF73 technical statement](https://icpald.org/wp-content/uploads/2026/05/Technical-Statement.pdf).
The statement describes the seasonal production methodology, while the local
projects contain detailed computational work and recorded assumptions. These
sources are complementary; neither should silently fill every gap in the other.

| Candidate | Agent goal and artifact | Verifiable success | Readiness and research value |
| --- | --- | --- | --- |
| B1 Reproduce a specified objective component | Rebuild a pinned ECMWF/NMME regression or CCA component for one centre, initialization and season from the reviewed method pack; submit probabilities, intermediates and a method comparison | Correct inputs, roster, training period, transforms, mode selection and masks; agreement with an independent implementation within predeclared numerical tolerances | Choose one component and source revision with experts. Packaging centre code yields a CORE-Bench-style reproduction task; withholding its implementation yields a harder reconstruction variant |
| B2 Consolidate the objective outlook | Use component probabilities and the reviewed weighting and mask rules to construct the objective; compare to the published map/product | Categorywise probability combination, masks and spatial alignment match a deterministic reference; explain differences from the publication | A useful first centre task because combination can be checked cheaply. Confirm which publication includes expert consensus adjustments; distinguish objective agreement from consensus agreement |
| B3 Verify the issued forecast and diagnose failures | With the B2 prediction frozen, calculate seasonal verification against the prescribed observation product; compare raw components, objective and climatology; identify where errors were concentrated | The agent's scores and support counts match private calculations; uncertainty uses the specified independent cases; claims match the evidence | Observations may be supplied here because this is diagnosis of an immutable issued forecast. Additional resolved issues are needed for calibration or general skill claims |

The ACMAD work records consequential choices about EOF selection, skill masking,
predictand and probability calibration. It also records numerical differences
between CPT and a reconstructed implementation. Review tolerances against that
evidence; matching a picture or adopting a broad tolerance is insufficient to
establish method fidelity. Freeze actual centre clarifications with the task.

## Family C Test a predictor claim from the literature

Candidate source: Funk and colleagues,
[Tailored Forecasts Can Predict Extreme Climate Informing Proactive Interventions in East Africa](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2023EF003524)
(2023), particularly its WPG/WVG forecast analyses in Figure 2. The local
[teleconnection diagnostic snapshot](../tasks/wvg-definition-audit/source-material/seasonal-hindcasting-gha/scripts/compute_teleconnections.py.txt)
can help curator work, but is not proof of reproducing the published analysis.
This is a proposed task extraction from a real paper; its complete reference has
not been built in this repository.

| Candidate | Agent goal and artifact | Verifiable success | Readiness and research value |
| --- | --- | --- | --- |
| C1 Reproduce one specified predictor result | Extract one WVG index definition and one rainfall relationship from the selected paper sections; rebuild the index and the specified statistic for the original period | Index normalization, boxes, seasons, observational vintage and statistic agree with the reviewed reference; uncertainty and deviations are reported | Experts must pin the exact panel, data and analysis choices. If details cannot be recovered, publish an addendum or defer the task; a guessed implementation is not an oracle |
| C2 Evaluate the claim independently | Freeze the C1 method and predictor definition; assess it on a period or sample genuinely excluded from the source analysis; report skill relative to predeclared baselines | Inputs respect the issue boundary; no region or threshold search uses held-out targets; independent calculation reproduces the statistic and uncertainty | Reserve enough independent cases. The few post-2023 seasons alone may yield an inconclusive result; credit the analysis, without forcing a positive or definitive conclusion |
| C3 Test one justified alternative | Compare the original predictor with a predeclared alternative box or lead formulation, selected using training-only evidence; submit frozen predictions and a comparison report | Nested selection stays inside training; the original and alternative receive matched evaluation; held-out scores are computed independently | Pin a scientifically motivated alternative with domain reviewers. Measures whether an agent can act on a physical hypothesis rather than only rerun code |

A contemporaneous observed SST–rainfall association and a usable long-lead
forecast are different targets. Require the predictor to have been available at
the nominated issue time, or provide its forecast; do not use realized target-season
SST as if it were a known forecast input. The expert addendum should explicitly
resolve this distinction before C1 becomes an executable task.

## Family D Subseasonal products and temperature verification

Source anchor: [the Kenya six-week product task](../archive/pilot-2026-10-01/tasks/kenya.yaml), whose
origin is the weather-skills-bench Kenya case and whose raw archive is
[the Kenya forecast store](https://kenya-forecasts.sheerwater.rhizaresearch.org/files/).
Only the precipitation reference is currently present here. Temperature is an
extension requiring an actual source/product audit; the archive name alone does
not establish that the necessary temperature ensembles and hindcasts exist.

| Candidate | Agent goal and artifact | Verifiable success | Readiness and research value |
| --- | --- | --- | --- |
| D1 Rebuild an archived six-week rainfall outlook | Convert cumulative member precipitation to the six declared seven-day totals; make mean maps and regional median/spread | Lead windows, units, control/member inclusion, weighting and arrays match `kenya_reference`; offline replay passes | The current contract uses 2026-09-27, with 2026-09-20 as a follow-up fixture. On 2 October their six-week targets have not all resolved; this is product processing, not observed skill |
| D2 Build weeks 2 to 6 temperature forecasts | Use an audited ensemble archive and hindcast baseline to produce Celsius temperatures, lead-specific anomalies and ensemble uncertainty for a predeclared region | Actual valid dates, unit conversions, masks and lead-conditioned climatology match independent checks; the forecast artifact is frozen before private scoring | Choose a centre archive and resolved historical issues, pin licences and verify temperature/hindcast coverage. Extends the suite to a second variable and a different anomaly workflow |
| D3 Verify and test a calibration change | Compare the frozen D2 product and one training-only calibration against the nominated observations over multiple resolved issues | Matched forecast/observation support, baseline and score calculations are correct; holdout targets stay outside fitting; report skill and uncertainty by lead | Needs sufficient archived issues and a calibration method supported by source practice or literature. Tests lead transfer, methodology and honest reporting of an unsuccessful change |

D1 and D2 share ensemble/time-handling work but differ in physics and climatology;
that transfer itself is interesting. D2 also needs a standalone reset instance.
For D3, make predictions with private verification, then release the observations
only for a separately frozen diagnostic stage if the task includes agent-led error
analysis.

## Diagnostics and later tasks

Keep [the IOD task](../archive/pilot-2026-10-01/tasks/iod.yaml) as a date/climatology diagnostic pending its
valid-time audit. Its two windows can test exact processing and forecast error,
but cannot establish probabilistic calibration. It is not part of the twelve
candidates above.

Downscaling deserves a later centre-derived task with a reviewed target grid,
fine-scale observations, conservation and masking requirements, and a credible
coarse-to-fine baseline. Do not add a synthetic “downscale to another country” task
before those sources exist. Likewise, source repair tasks from recorded real
workflow failures; controlled bug injection belongs in evaluator validation.

## Admission and diversity

Admit a task only when the source supports its scientific goal, permitted inputs
are accessible and legal to distribute or retrieve, expert ambiguities are
resolved, the independent reference can run, and each required rubric leaf has
evidence. Record task state as candidate, curated, reference validated, expert
reviewed, or frozen. Only frozen instances belong in comparative evaluation.

Select the first curation work across all three sources: the existing seasonal
family, one objective centre component/combination, and one literature claim.
Develop the temperature family while its source audit proceeds. This is a
proposed order based on present evidence, not a decision to exclude any source.

Use region, variable, lead, method step and source type as coverage labels rather
than a full Cartesian product. Macro-average across families before variants.
Reserve entire papers or workflows for a development/evaluation split where
possible. One physical predictor instantiated in ten regions still contributes
one closely related family of challenges.
