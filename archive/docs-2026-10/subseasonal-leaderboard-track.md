# Subseasonal leaderboard task track

A second track assesses whether agents improve forecast performance through bounded experimentation. Give the agent a real forecast dataset, reproducible baseline, score feedback on development cases, and a fixed resource allowance. Freeze its selected code and fitted state before scoring a separate final period. The first development implementation is [subseasonal-optimization](../tasks/subseasonal-optimization/prompt.md); the broader competition variants below remain proposals.

The archived WMO retrieval endpoints were unavailable during the acquisition audit.
The implemented task therefore uses actual CPC precipitation and CFSv2 reforecasts
from SubseasonalClimateUSA: nine southwest US cells, 831 training issues, 147
development issues and 208 final issues. Complete 14-day target windows are purged
across split boundaries. Its fixed metric is pooled cosine-latitude-weighted RMSE
in millimetres, with raw CFSv2 and climatological baselines. This regional metric
is a declared curator adaptation; it is neither WMO probabilistic RPSS nor the
original US anomaly-correlation leaderboard.

The controller now supplies `score_development` with at most five requests,
including malformed submissions. It snapshots and hashes each bounded NetCDF,
returns aggregate development metrics, and retains a feedback ledger outside
solver mounts. Final observations and scores are unavailable during selection.
Independent arithmetic tests and actual offline baseline replay/inference controls
have passed. Human scientific review and agent difficulty measurements remain open.

## Source anchors

The archived [WMO and ECMWF S2S AI Challenge](https://s2s-ai-challenge.github.io/) sought probabilistic temperature and precipitation forecasts for weeks 3–4 and 5–6. Its competition ended; the automated scorer has stopped. The [migrated template](https://github.com/aaronspring/s2s-ai-challenge-template) and [ECMWF data plugin](https://github.com/ecmwf-lab/climetlab-s2s-ai-challenge) provide starting code and data documentation. We would implement a local replay, not enter an active competition.

The [SubseasonalClimateUSA data](https://github.com/microsoft/subseasonal_data) and [forecasting toolkit](https://github.com/microsoft/subseasonal_toolkit) offer a complementary route through documented baselines and adaptive bias correction. The toolkit supplies paper evaluation commands and models suitable for a bounded first experiment. Its reported example runtimes do not establish runtime for our chosen data or environment; benchmark that locally before launch.

The competition sources have been inspected. Data endpoint availability, subset sizes, immutable revisions, complete dependencies and redistribution terms still need an audit. Public historical observations are retrospective evaluation evidence, not a pristine hidden benchmark merely because we withhold them from one agent workspace.

## First example

Proposed objective: improve weeks 3–4 precipitation probabilities relative to a frozen climatology and calibrated dynamical baseline on a declared regional S2S challenge subset. Permit sound bias correction, predictor selection and ensembling. Supply baseline code and source documentation so research time goes into scientifically meaningful improvements. Temperature and weeks 5–6 are later instances of this same family, not four independent research problems.

Start with one forecast source, all predeclared land cells in a manageable region, and multiple complete annual blocks. Select the region for coverage and compute feasibility before exploring comparative skill. Freeze the training, feedback and final periods after inspecting forecast/observation availability. A regional or reduced-data result must be labelled as our benchmark instance; it cannot claim a rank on the original global leaderboard.

A first-pilot allowance could be five feedback submissions and a two-hour CPU training limit, plus a separately recorded agent-token/time allowance. These are proposed limits to revise after measuring baseline runtime. All systems receive the same starting code, data access and feedback policy. Record total experiments and compute, not just the resources consumed by the final successful fit.

## Scoring and feedback

Preserve the source metric's actual aggregation order. The WMO rules calculate temporal mean RPS per grid cell, form skill relative to climatology, clip skill, then spatially weight and combine variable/lead scores. They also specify missing-prediction penalties and a dry precipitation mask. The rules changed during the competition: pin the final scoring code and observation release, and verify independent score fixtures. A familiar metric name alone is not a scoring specification. [Official evaluation and scoring updates](https://s2s-ai-challenge.github.io/#evaluation).

Our development-feedback scorer and final scorer must use the same frozen definitions, coverage and baseline. Neither can silently drop poorly forecast cells or select a favorable subset of dates. Record every submitted prediction hash, feedback response, elapsed time, resource use and model-state hash.

The agent can inspect training targets and obtain bounded development-score feedback. It gets no final target files or final-score feedback while selecting methods. Freeze one chosen submission before final evaluation. Split by complete chronological blocks and remove overlap in target windows across boundaries. Training examples become usable only when their observation windows have resolved; overlapping weekly, fortnightly targets are not independent samples.

Report the development improvement curve and final skill separately, with paired uncertainty that acknowledges serial/spatial dependence. The best development score is an optimization observation, not the final estimate. Public historical data and papers can expose final results through prior knowledge, so report that contamination limitation; fresh operational evaluation would require subsequently resolved issues.

## Relationship to the judge

The controller computes performance and ranks scientifically admissible submissions. The judge checks evidence for information boundaries, experimental choices, source claims and conclusions. Reproduction tasks require method fidelity; leaderboard tasks allow different valid methods and predictions. Numerical agreement with one preferred optimizer would be inappropriate.

Keep scientific validity, reproducibility, source/claim support, forecast skill and search cost visible separately. A valid negative result can complete the scientific workflow while placing poorly on the leaderboard. Invalid leakage cannot become a successful scientific result through a high score.

Before calling the first instance runnable, require a frozen source/data manifest, a baseline that reproduces offline, independently tested metric fixtures, temporal-leakage and coverage tests, a logged feedback limit, and executable saved-state inference. Reuse the existing controller and trace/substrate records where practical; introduce only the feedback and metric hooks this track needs.
