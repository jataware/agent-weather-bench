# Repair a short-rains forecast workflow and test its selection procedure

Adapt the frozen East Africa analysis into a reusable September-issue OND rainfall
forecast workflow. The original source is an exploratory research workflow, not a
validated operational forecast system. Resolve its data conventions from the
frozen evidence and implement the revised scientific contract below. A negative
or uncertain skill finding is acceptable. Better skill is not a completion gate.

All required inputs and source excerpts are in `/work/inputs`. Work offline. The
controller retains the 2020–2023 rainfall observations; do not obtain them.
Your 2020–2023 forecasts use a fixed training cutoff of 2019, so all four are
independent retrospective test cases, not a sequence in which targets are released.
No sibling checkout, remote service, CPT binary or forecast library is required.
Python, NumPy, SciPy, xarray, netCDF4 and matplotlib are available.

The original files `starting-bench.py.txt` and `starting-search.py.txt` are source
anchors; adapt their scientific workflow. You may restructure or independently
implement the code. Cite the source and explain consequential changes. The
source files' prose and comments can be wrong; evaluate them against the data
and acquisition implementation. The task is a forecast-method adaptation, not
reproduction of its published leaderboard.

## Revised forecast definition

There are three fixed target regions, ordered `somalia`, `kenya`, `eastern-horn`.
The supplied monthly rainfall series are cosine-weighted means over finite land
cells in the source retrieval boxes. They have already been spatially reduced;
the target is the area-mean October–December total, not a spatially averaged
tercile probability. Preserve every year and region. Recover the correct monthly
totals from `rainfall.nc` using the historical converter and catalogue evidence;
explain why multiplying these particular values by calendar month length is
incorrect. Sum the three monthly totals into `seasonal.nc` for 1993–2019, in mm.
Do not use the original leaderboard's rainfall preprocessing unchanged.

Each hindcast is treated as issued on September 30. Observed SST is available
only through August 31 because of the declared processing latency. September
initialized CanSIPS reforecasts of the coming OND IOD are also permitted. This is
a retrospective reforecast experiment using final observation/reanalysis data;
it does not reconstruct historical release vintages or prove real-time service
performance. The lead time of an observed antecedent and a forecast of a future
index are different. Explain that distinction accurately.

`sst.nc` contains raw monthly box means in Celsius, not anomalies. Use the
supplied retrieval boxes as-is; some include margins around standard named
indices. `forecast-index.nc` contains the raw ensemble/target-season mean western
minus eastern Indian Ocean SST difference, without whole-record anomaly or drift
correction. Its year is the OND target year, initialization month September.

## Prescribed systems and calibration

For each region independently, implement these systems in this order:

1. `climatology`: always `[1/3, 1/3, 1/3]`.
2. `antecedent-iod`: July–August raw observed `iod_w - iod_e`, identity target transform.
3. `forecast-iod`: September initialized OND raw `gcm_iod`, identity target transform.
4. `nested-search`: select one of the 108 candidates in `candidates.json` inside
   each training set using the inner rolling verification specified below.

For a candidate with `gap=g`, `width=w`, average the observed raw SST box means
over the `w` calendar months ending in August minus `g`. For example, gap 0,
width 2 means July–August; gap 2,width 3 means April–June. These windows never
include September or OND. Form `nino34`, `wpac`, `wv` from those means; form `iod`
as raw west minus east. Form `wpg = z(wpac) - z(nino34)` and
`wvg = z(nino34) - z(wv)`, where each component's `z` uses its own mean and sample
standard deviation (ddof=1) on the current fit's training years. Recompute these
constants for every inner and outer fit; the original whole-record standardized
components cannot be reused. No monthly climatological correction is needed for
these fixed same-month windows. Raw-index centering by an OLS intercept is
equivalent to subtracting a training-only constant.

Fit univariate ordinary least squares with an intercept to the transformed
target, using either `identity` or `log1p` as specified by each candidate. For n
training cases, fit mean prediction `mu(x)`, residual variance `s² = SSE/(n-2)`,
and predictive scale
`s * sqrt(1 + 1/n + (x - mean(x_train))² / sum((x_train - mean(x_train))²))`.
Use the Student-t predictive distribution with n−2 degrees of freedom. This
includes observation uncertainty and extrapolation leverage; a normal CDF or a
constant residual scale alone does not implement this contract. Do not clip a
negative predicted mean; compute tercile probabilities from the stated model.

Tercile boundaries use sorted training rainfall totals in mm and CPT's empirical
quantile: `r=n*p+0.5` for p=1/3 and 2/3. With 1-based j=floor(r), interpolate
`a[j] + (r-j)*(a[j+1]-a[j])`; clamp to the first/last value outside the record.
Transform these boundaries with the candidate's target transform before using
the predictive CDF. Keep saved boundary values in rainfall units. Below/normal/
above probabilities are `F(lower)`, `F(upper)-F(lower)`, `1-F(upper)`.

## Experimental separation and verification

Outer hindcasts are one-year expanding-window forecasts for each year 2005–2019:
fit on 1993 through the previous year. For each outer training set, score each
candidate in inner expanding windows: predict every training year starting in
2001, using 1993 through its previous year. Each inner prediction must refit all
learned constants, regression, uncertainty and tercile boundaries. Select the
minimum mean inner RPS; ties within 1e-12 of the minimum use the earliest candidate
ID in `candidates.json`. Refit that winner on the full outer training set before
predicting the outer year. This tests the selection procedure, not the best
configuration chosen after seeing outer outcomes.

For the independent forecasts 2020–2023, repeat selection using training years
1993–2019 and fit once. Save the resulting state. All four predictions use that
same saved fit and thresholds with their own allowed predictor values.

Assign verification category below if y<lower, normal if lower≤y<upper, above
otherwise. RPS is the mean of the squared errors of the first two cumulative
probabilities. Verify every system on identical cases. Regional RPSS is
`1 - sum(RPS_system)/sum(RPS_climatology)` across all outer years; do not average
foldwise RPSS ratios. The climatology RPSS must be zero. Report mean RPS and RPSS,
and paired differences between nested search and both fixed predictors. Provide
an uncertainty assessment suitable for only 15 dependent annual outer cases,
state its assumptions, and avoid interpreting a noisy positive number as proof
that search improves forecasting. The uncertainty method may differ; numerical
agreement is required for the prescribed forecasts and verification arithmetic.
Never claim 2020–2023 observed skill from this workspace.

## Artifacts and executable interface

Write your artifacts under `/work/submission`:

- `seasonal.nc`: `seasonal_total(year,region)` for 1993–2019, units mm.
- `hindcasts.nc`: `probability(system,year,region,tercile)` for 2005–2019;
  `threshold(year,region,boundary)` in mm; `selected_candidate(year,region)`;
  `inner_rps(year,region,candidate)` for all 108 candidates;
  `rps(system,year,region)` and `rpss(system,region)`.
- `forecast.nc`: probabilities for all four systems for 2020–2023;
  `threshold(region,boundary)`; `selected_candidate(region)`;
  `inner_rps(region,candidate)`.
- `answer.json`: `task`, `training_years`, `verification_years`, `prediction_years`,
  `region_order`, `system_order`, `rainfall_units`, `rainfall_recovery_factor`,
  `issue_time`, `observed_sst_cutoff`, `metrics` (per region/per system mean RPS
  and RPSS), `forecast_skill_claim`, `limitations`.
- `model.npz` or `model.json`, executable code, `report.txt`, `outlook.png`,
  `handoff.txt`, `provenance.json`, `execution.json`.

Coordinate order: region and system as above; `tercile=[below,normal,above]`,
`boundary=[lower,upper]`, `candidate=0..107`, increasing integer years. All
probabilities are dimensionless finite numbers in [0,1] summing to one. The
supplied regional data have complete finite support; fail clearly if required
input cases become nonfinite instead of silently changing evaluation support.

Your handoff and execution declaration must give an offline full-replay command
that accepts `--inputs PATH --outputs PATH` and recomputes the results. Also
provide an inference-only command accepting `--model PATH --inputs PATH
--outputs PATH`. It reads the frozen state and predictor files, works when
rainfall observations are absent, and writes `forecast.nc` probabilities and
thresholds without refitting or reselecting. Inference-only output may omit
`inner_rps`. Honor alternate paths and altered predictor values. The controller
will check replay, remove rainfall for saved-state inference, perturb held-out
or future inputs, and run saved inference on changed allowed predictor values.
Historical predictions must not depend on rainfall or SST after their fitting/
issue boundaries, and candidate selection must not depend on outer held-out
targets. Do not hardcode the supplied outputs.

In `execution.json`, declare `replay.argv` with both `{input_dir}` and
`{output_dir}` placeholders, and `predict.argv` with `{input_dir}`,
`{output_dir}` and `{model_path}`. Set the manifest's `model_path` to the relative
saved-model filename. These task-specific input and
directory-output placeholders replace the seasonal-calibration task's single
forecast-file/output-file interface. Retain source inputs under a relative
submission directory and list it in your handoff so replay has all needed data.

Use the common provenance/replay conventions supplied by the benchmark. Discuss
sources and limitations in the report, show the outer score comparison and
uncertainty in a useful figure, and distinguish successful method adaptation from
evidence for an operational skill gain.
