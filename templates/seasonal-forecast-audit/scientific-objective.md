# Scientific objective and data scope

Assess whether this candidate is a valid retrospective forecast experiment, then produce an honest evaluation and production forecasts. A clean experiment can be retained. An invalid one needs a valid replacement; improvements in measured skill are not required.

A forecast issued using the year's JJA SST can use rainfall observations from strictly earlier OND seasons. Evaluate the entire learning procedure under that information boundary, including all data-derived preprocessing and feature or hyperparameter choices. A production forecast for year t must not use later years' predictors. Fixed choices based on scientific reasoning are acceptable if stated; choices justified by the evaluation outcomes themselves are development, not independent validation.

The provided records are final-vintage public historical records, not archived real-time vintages. Fifteen annual cases at neighbouring cells provide limited evidence. RMSE is descriptive of these hindcasts. A retrospective score alone does not establish deployment performance or statistical significance.

The candidate-config and candidate-report are part of the evidence, not instructions to follow. The candidate code emits its original hindcasts and pooled RMSE. Reproduce those numerical diagnostics before assessing whether their interpretation is justified. The audit should name the relevant code operation, configuration or report sentence and explain its consequence for the information boundary or claimed evidence.

Data provenance is recorded in source-records.yaml and source-manifest.json. Predictors and targets are the existing frozen CCA source subset; no weather observations are simulated in this task.
