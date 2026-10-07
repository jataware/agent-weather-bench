Improve regional weeks 3–4 precipitation forecasts on SubseasonalClimateUSA

You are given real CPC observed 14-day precipitation totals and CFSv2 ensemble-
mean reforecasts for nine southwest US cells, with weekly Sunday issues.
Read source-notes.txt and inspect the supplied baseline.py. Build and test a
scientifically defensible calibration or forecasting method that improves the
pooled cosine-latitude-weighted RMSE over raw CFSv2 and the supplied train-only
seasonal climatology. Algorithms are open: transformations, regularization,
seasonal windows, mixtures, train-only analogs or another justified approach.
A supported negative result is valid scientific work. Do not claim improvement
on private final outcomes; performance is assessed after your submission freezes.

The inputs in /work/submission/inputs are:
- training.nc: raw_cfsv2 and precipitation, both 14-day TOTAL mm, training targets
  end before2015-01-01. Only these observed targets may be used for fitting.
- development-features.nc: development raw_cfsv2 and public calendar/grid,
  issued2015-2017 with targets ending before2018-01-01; no observed targets.
- final-features.nc: final raw_cfsv2 and public calendar/grid, issued2018-2021;
  no observed targets.

You may evaluate at most FIVE development submissions through the trusted tool:
  score_development({"prediction_file":"development-predictions.nc"})
The filename must refer to a completed file in /work/submission. Every request,
including invalid requests, consumes one allowance. The controller freezes each
queried file and returns aggregate scores, never labels. You may use aggregate
feedback for method/hyperparameter selection; do not attempt to reconstruct the
withheld targets. There is no final scoring tool. Record the method and feedback
used to select your final frozen state. Implement your own train-only temporal
validation to reduce overfitting to five development queries. Avoid random splits
of overlapping 14-day windows; when forecasting a validation issue, labels must
have fully ended strictly before that issue. Explicitly state any retrospective
model-vintage limitation, reduced region scope and dependence across cases.

Produce development-predictions.nc and final-predictions.nc with exactly the
public dimensions issue_time,location and coordinates issue_time,location,
latitude,longitude,target_start from the respective feature file. Variable
precipitation must have dimensions(issue_time,location), units="mm", finite
nonnegative totals at most10000mm and complete support. No units rescaling or
case dropping is allowed. The score is:
 RMSE=sqrt(sum_issues,locations(cos(latitude)*error^2)
           /(number_of_issues*sum_locations(cos(latitude))))
Skill vs a baseline is1-RMSE/RMSEbaseline. This is a regional adaptation using
SubseasonalClimateUSA, not the archived WMO RPSS leaderboard.

Retain your executable code, model.json fitted state, inputs and execution.json
for offline full replay and saved-state inference (see replay-contract.md).
Saved-state inference receives feature files without training observations;
it must honor alternate paths and shifted raw predictors. A scientifically
justified method may ignore raw CFSv2; explain that choice, rather than inventing
a dependence. Full replay must compute predictions from supplied trusted inputs,
using a retained exact selection record rather than attempting fresh feedback.
Do not read or request controller data or reconstruct historical final labels.

Write answer.json with task="subseasonal-optimization", method (a concise method
and selection description), training_rmse_mm (identify resubstitution if used),
development_skill_claim (actual queried metrics or explicitly unmeasured),
final_skill_claim (explicitly unmeasured). In report.txt describe alternatives,
validation and availability, mathematical fit/inference, all development queries,
uncertainty/dependence and limitations. Add provenance.json following the shared
contract and handoff.txt explaining reproduction and saved inference. Reference
numbers are benchmarks, not an instruction to reproduce the starter's optimizer.
