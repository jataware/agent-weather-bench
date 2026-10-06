# WeatherBench verification review

This development task uses real public WeatherBench2 temperature fields with a
pinned upstream scorer snapshot. It tests valid-time matching, case aggregation,
regional weighting, common support, metric diagnosis and reusable verification.
The erroneous scorecard and availability outages are explicit curator controls,
not historical claims. No forecast training or model quality improvement is
required. Human scientific, scoring and redistribution approval are pending.

Before release, Zeek should inspect the source data/license records, independent
reference audit, positive and consequential negative controls, actual solver
attempt, trace evidence and proposed expert judgments. In particular, check that
undefined climatology ACC is handled honestly, corrected intermediate mistakes
are not penalized as final errors, and uncertainty claims respect short seasonal
coverage and dependence. A high score alone does not reproduce the paper or
prove a frontier capability ceiling. The counterfactual execution probe tests
input sensitivity, not holdout weather skill.
