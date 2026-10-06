# Scientific and scoring review

This package is unapproved for public release. It freezes a real workflow and
source data, and separates source behavior from curator experimental choices.

Review whether the historical conversion evidence adequately establishes the
rainfall recovery factor, whether the declared conservative issue-time inputs
are defensible, and whether the different regional retrieval-box definitions
and final data vintages are stated clearly. The forecast-index source lost raw
member/lead detail, so this task audits downstream use of the frozen reduced
index; it does not score reconstructing acquisition or ensemble-member handling.

The Student-t OLS predictive model is prescribed for a reproducible controlled
comparison. It is not asserted to be optimal for skewed rainfall. Check that the
identity/log1p candidate alternatives, nested rolling verification and uncertainty
interpretation assess substantive weather-forecasting reasoning. No skill gain
is required. A positive or negative result can complete the task.

Numerical tolerance: probability/loss/skill absolute 2e-7 plus relative 1e-7;
rainfall/threshold absolute 1e-5 mm plus relative 1e-7; candidate IDs and coordinates
exact. The independent implementations differ by less than 4e-15 in probabilities
and less than 2e-13 mm. Tolerances allow ordinary output precision, not alternate
method choices.

Every hidden test follows a public invariant: units/support; candidate/fit/fold
semantics; fixed production fit; common-support verification; alternate-path
full replay; target/future perturbation invariance; saved inference with no target
data and changed allowed predictors. The scientific interpretation remains an
expert judgment. Code/state review is needed to establish saved-fit provenance.

Difficulty is not yet empirically established. A bounded independent frontier
attempt must be reported with limits, artifacts and calibrated assessment; a
budget stop is not evidence that the science is intrinsically beyond a model.
