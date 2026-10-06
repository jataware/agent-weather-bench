# Reconstruct training-only multivariate EOF/CCA seasonal forecasting

Reconstruct a bounded operationally useful EOF/CCA forecasting component from the
supplied source pack. Forecast OND rainfall over twelve East African land cells
from antecedent June–August SST at27 native ocean cells. Audit why a deterministic
cross-validation product does not establish independence of a separate full-fit
probability product. Deliver the frozen curator adaptation in `algorithm.md`;
explain where it departs from the supplied CPT/PyCPT/AfricaS2S source conventions.
A supported negative skill result is acceptable. Do not claim exact CPT execution
or historical real-time forecast availability.

Read the actual source code excerpts and `algorithm.md`, supplied alongside
`predictors.nc`, `targets.nc`, `candidates.json` and `source-manifest.json`. Inputs
are already true rainfall totals and raw prior-season SST, so no calendar-rate
conversion remains to implement. Preserve selected native-cell support. No network
or GPU is needed. CPU resources are2 cores and4GB; NumPy/SciPy/xarray are available.
Use any equivalent implementation; loading/controller reference output is forbidden.

Required scientific files:

- `hindcasts.nc`: dimensions year2005–2019, system=[climatology,cca-fixed,cca-nested],
  target exactly as supplied, category=[below,near,above], boundary=[1/3,2/3],
  candidate IDs0–13. Variables prediction(year,system,target),
  probability(year,system,target,category), threshold(year,boundary,target),
  selected_candidate(year), inner_loss(year,candidate), rps(year,system,target),
  rpss(system), full_fit_prediction(year,target),
  full_fit_probability(year,target,category). Predictions and thresholds have units
  mm. Full-fit diagnostic predictions also have units mm.
- `forecast.nc`: prediction(system,year,target),
  probability(system,year,target,category), threshold(boundary,target),
  scalar selected_candidate, inner_loss(candidate), with prediction years2020–2023
  and the same system/category/target order and mm metadata.
- `answer.json`: task=cca-seasonal-reproduction, training_years1993–2019,
  verification_years2005–2019, prediction_years2020–2023 (inclusive endpoints or
  enumerated lists), rainfall_units=mm, rpss mapping by system,
  full_fit_is_cross_validated=false, cpt_binary_executed=false, limitations list.
- `report.txt`: source-grounded distinction between deterministic CV and full-fit
  probability routes; actual adaptation choices, nested selection, working
  uncertainty assumptions, paired outer evidence and limits from15 dependent
  retrospective years. Explain whether increased complexity helped; discuss
  spatial dependence and estimator uncertainty without treating cells as
  independent replications. Compare the full-fit diagnostic to honest outer
  predictions without assigning it out-of-sample skill.
- `outlook.png`: readable forecast/verification summary with units and clear split.
- `provenance.json`: shared contract, accurate supplied-source records and retained
  file hashes; include fold/mode/standardization/weighting/uncertainty parameters.
- `handoff.txt`, `execution.json`, runnable code and fitted state: full replay from
  alternate input paths, plus saved-state inference with no targets or refitting.

Retain scientific outputs and code in the submission root. Both replay and
prediction commands must respect provided output directories. The controller
changes held-out/future targets to check earlier outer fit isolation, then removes
all supplied targets and changes future SST to check real fitted-state inference.
These checks test public scientific requirements; do not hard-code original data.
