# Short-rains workflow development evidence

`short-rains-workflow`, development-0.1, is a runnable internal task with frozen
real East Africa source series, public code/literature excerpts, an independent
controller reference, static scientific checks and executable perturbation
checks. Task/source/input bytes were frozen before launching frontier attempts.
No model attempt was used to choose the prompt, reference or counterfactuals.
Scientific, scoring and redistribution approval remain pending.

The source is `v4zeek` at `e364ce0ed6cb210b0872c4e35d76ddb329b6dfa5`. Its monthly
CHIRPS fixture lost attributes after an older acquisition converter divided
monthly totals by a flat 30. Its target builder later multiplied calendar month
lengths. The task supplies both historical converter/catalogue evidence and
the original pipeline, making the consequential unit repair recoverable.
Current acmadDL preserves native monthly totals; silently mixing current
documentation with the historical fixture would give the wrong repair.

The revised task forecasts three fixed regional OND totals from September issue
inputs. It compares climatology, an observed July–August IOD antecedent, a
September initialized CanSIPS forecast of OND IOD, and a nested selection
procedure over 108 source-inspired observed predictors/target transforms. It
requires train-only component standardization, CPT empirical boundaries,
Student-t OLS predictive uncertainty including leverage, inner/outer expanding
windows, common-case RPS and pooled RPSS, and saved-state inference. Source
box means and regional means were frozen after independent spatial-reduction
checking; no heavyweight acquisition is required at solve time. The flat
agent-input directory is about 130 KB.

The independent reference uses explicit centered-covariance OLS. The audit uses
a centered design matrix, least squares, matrix leverage, quantiles interpolated
on empirical probability positions, direct cumulative category targets and a
different feature implementation. They agree on all 45 outer candidate IDs,
all three production IDs, every inner score for all 108 candidates, all
probabilities, boundaries and verification fields. Maximum probability
difference is below 4e-15. Source regional reductions agree below 2e-13 in their
scaled monthly units. Numeric tolerances were set before model attempts.

The reference itself supplies a scientifically valid negative comparison:
search has positive outer RPSS against climatology but loses to forecast IOD in
all three regions. Outer scores are evidence about this short retrospective
record, not proof of operational superiority. Only 15 outer cases and one
forecast model/index are available; 2020–2023 targets are withheld from the
agent and fit, but the original researchers already used these historical data.
They are independent retrospective targets, not pristine unknown observations.

Controller validation used the pinned offline Docker image
`sha256:14ded77c764dccdcaeef07f91c549709b4ff3549d0c30f5dc780e4376347917a`:

| Internal case | Static scientific arrays | Original replay | Historical fold perturbation | Changed-predictor saved inference |
| --- | --- | --- | --- | --- |
| Reference execution example | Pass | Pass | Pass, maximum probability difference 4.4e-16 | Pass, maximum difference 1.8e-15 |
| Constructed outer-target leakage | Pass | Pass | Fail, difference 0.000358525 | Pass |
| Constructed cached inference | Pass | Pass | Pass | Fail, difference 0.566699 |

The two contrasts are deliberately constructed evaluator tests, not observed
agent failures or evidence of defects in a natural solver. The leakage contrast
adds a whole-record target-derived correction anchored to retained original
observations; the cached-inference contrast returns the original forecast
artifact. Both show why exact original arrays alone cannot establish a valid
workflow. The controller changes the 2011 held-out target and all later targets,
and unavailable SST from September 2011 onward, then checks probabilities,
thresholds, selection and inner scores through the 2011 issue. It excludes
verification loss for the modified targets from that invariant. Saved inference
removes rainfall/seasonal artifacts and changes allowed future predictors.

Raw validation evidence is under `var/calibration/short-rains-baseline`,
`short-rains-outer-target-leak` and `short-rains-cached-inference`, each with
`controller-validation-docker.json`. The reference execution example does not
constitute a full expert-approved submission: its report explicitly leaves a
substantive uncertainty interpretation for review. Eight fast contrast tests in
`tests/test_short_rains_workflow.py` pass.

Scientific interpretation and code/state provenance still need expert review.
Passing black-box probes is behavioral evidence, not proof that every retained
state value came from its declared fit. Runtime unavailability leaves execution
unresolved and is not scored as a scientific failure. Forecast skill is reported
separately and is never a completion gate.

Empirical frontier difficulty remains to be established by the root-controlled
attempts. Report exact model, limits, execution/trace evidence and observed
failures. A budget stop alone does not establish inability, and one success or
failure does not justify claims of general frontier capability.
