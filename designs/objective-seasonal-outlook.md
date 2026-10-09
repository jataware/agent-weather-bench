# Task record: the objective seasonal outlook

Status: design record, 9 October 2026. No template, control run, model attempt
or format change exists yet. This record fixes the decisions the brief, the
spec and the grader are built from. The [roadmap](../docs/roadmap.md) gives the
order of work; the [README](../README.md) gives the reasoning.

## The job

Produce the objective seasonal rainfall outlook for the Greater Horn of Africa
for one season, issued in one month, following the regional centre's
three-stream practice, and write the bulletin. The centre is ICPAC; the
practice is the GHACOF objective forecast: the equal-weight average of a
canonical correlation analysis forecast (CCA), a per-cell ensemble regression
forecast (eReg) and a logistic regression of tercile occurrence on a
sea-surface-temperature index (WVG).

The agent receives raw provider responses from a frozen source service, a
method document that names the centre's practice in words, a target-grid file,
and the submission envelope. It does not receive reference outputs,
verification observations for the forecast season, code, equations, worked
examples or the stage structure of the rubric.

## Three constraints bind every stage

1. **Specify the what, never the how.** The contract pins interface schemas:
   group names, array names, dimensions, coordinates, grid, units and tercile
   definitions. It never gives code, step-by-step algorithms or prepared
   arrays. Cleaning, calendar reconciliation, regridding, solver choice and
   code architecture are the agent's.
2. **The grader never crashes on agent output.** Every submitted group passes
   a schema check before any reference runs. A downstream local verdict whose
   upstream group failed its schema returns `unresolved:
   invalid_upstream_contract`, naming the group and quoting the first error.
3. **Runtime references are pure Python.** NumPy, SciPy and xarray only,
   inside the controller image. CPT.x and R appear once, offline, to validate
   the pure-Python references on the control; that validation is stored with
   the control and is not a runtime dependency.

## The common frame is pinned once

- `lat`, `lon`: the target grid, supplied to the agent as `target-grid.nc`
  in the input directory, holding the exact `lat` and `lon` coordinate
  values, their bounds and the grid's spacing as attributes. The values come
  from the control run: the CHIRPS Greater Horn of Africa grid coarsened to
  the centre's working resolution. The brief points to this file by name and
  the schema check compares coordinates to it exactly.
- `year`: integer hindcast years, the training period named in the method
  document and fixed by the frozen snapshot.
- `category`: integers 0 below, 1 near, 2 above normal.
- `model`: integer index into the centre list in the method document, in
  that order.
- `stream`: 0 CCA, 1 eReg, 2 WVG.
- Units: seasonal totals in `mm`; probabilities in [0, 1], summing to 1
  across `category` on supported cells; support counts as integers.
- Unsupported cells hold numeric zero in every probability array and zero in
  the matching `support` or `available_*` array. Required arrays contain no
  NaN. Dimension order is free; the controller aligns by label. Zarr 2 or 3,
  consolidated or not, are all accepted.
- Tercile definition: thresholds per cell at the one-third and two-thirds
  quantiles of the training-year observations. The quantile interpolation
  rule is an enumerated convention (stage 2).

## The eight stages

Each stage lists what the agent must produce, what is pinned, what is not
prescribed, the instrument that grades it, and how the local verdict is formed.

### Stage 1, acquire

- **Produce:** the model hindcasts and the forecast issuance for every listed
  centre, the observations, and the SST field for the index, retrieved from
  the frozen source service.
- **Pinned:** `acquire/manifest.json` listing each product used with its
  catalogue id and hash.
- **Not prescribed:** which files, which paths, how to verify.
- **Instrument:** coverage against the required product set. The evidence is
  the controller's own request log, not the manifest. The fresh-snapshot
  rerun probe applies: the submitted command must retrieve again when the
  controller runs it against a fresh copy of the snapshot.
- **Local verdict:** none; first stage.

### Stage 2, prepare

- **Produce:** seasonal totals in mm, observations and each centre on the
  target grid, tercile thresholds and observed categories from the training
  years, and the SST index series.
- **Pinned arrays, group `prepare`:**
  `observed_mm(year,lat,lon)`, `model_hindcast_mean_mm(model,year,lat,lon)`,
  `model_forecast_mean_mm(model,lat,lon)`, `tercile_lower_mm(lat,lon)`,
  `tercile_upper_mm(lat,lon)`, `observed_category(year,lat,lon)`,
  `sst_index(year)`, scalar `sst_index_forecast`.
- **Not prescribed:** unit conversion, calendar handling, regridding
  implementation, member handling.
- **Instrument:** reference match with enumerated conventions.
  - Observation regridding: area-conservative accepted, bilinear accepted,
    nearest-neighbour a named pitfall.
  - Month lengths: actual days accepted, thirty days a pitfall.
  - Rate conversion: omitted conversion a pitfall.
  - Quantile rule: linear interpolation accepted in its two common
    definitions; the control fixes the exact pair.
  - Tolerances are error bounds from the declared operation chains, as in
    the existing calibration spec.
- **Local verdict:** none; upstream is raw data.

### Stage 3, WVG

- **Produce:** per-cell logistic regression of below-normal occurrence on the
  SST index, cross-validated, giving tercile probabilities for the hindcast
  years and the forecast.
- **Pinned arrays, group `wvg`:**
  `hindcast_probability(year,category,lat,lon)`,
  `forecast_probability(category,lat,lon)`, `support(lat,lon)`.
- **Not prescribed:** solver, convergence settings. The method document
  states the centre's rule for the near-normal and above-normal categories in
  words.
- **Instrument:** reference match. Unregularised logistic maximum likelihood
  has a unique optimum, so the bound is the control's measured solver spread,
  not a float bound. Simplex invariant. Held-out-year isolation probe.
- **Local verdict:** reference recomputed from the agent's `prepare` group.

### Stage 4, eReg

- **Produce:** per-cell linear regression of observed seasonal rainfall on
  each centre's ensemble mean, Gaussian predictive distribution, leave-one-out
  hindcasts, tercile probabilities per centre and averaged across centres.
- **Pinned arrays, group `ereg`:**
  `model_hindcast_probability(model,year,category,lat,lon)`,
  `hindcast_probability(year,category,lat,lon)`,
  `forecast_probability(category,lat,lon)`, `fitted_mean_mm(year,lat,lon)`.
- **Not prescribed:** code.
- **Convention, decided:** the predictive variance rule. Prediction-error
  variance (residual variance scaled by the leverage term) and residual-only
  spread are both accepted. The variant matcher names which reading the agent
  used. Neither is a pitfall.
- **Instrument:** reference match with that convention; held-out-year probe;
  simplex invariant.
- **Local verdict:** from the agent's `prepare` group.

### Stage 5, CCA

- **Produce:** canonical correlation analysis of the SST predictor field on
  the rainfall field with the centre's cross-validated mode selection, giving
  tercile probabilities.
- **Pinned arrays, group `cca`:**
  `hindcast_probability(year,category,lat,lon)`,
  `forecast_probability(category,lat,lon)`, `hindcast_mean_mm(year,lat,lon)`,
  scalar `modes_selected`.
- **Not prescribed:** engine, EOF truncation implementation, transform.
- **Why the gate is method-blind:** PyCPT and the pure-Python CCA disagree
  by several percentage points on the same data, so no bound from the control
  separates a valid alternative engine from an error.
- **Gate, decided:** simplex invariant; outer-year isolation probe; spatial
  correlation of each category's probability map with the reference above
  0.85; cross-validated RPSS no worse than the reference's by a margin
  measured from the engine spread in the control run.
- **Advisory:** reference match within the measured engine spread, reported
  and not gating.
- **Local verdict:** the gate recomputed on the agent's `prepare` group.

### Stage 6, combine

- **Produce:** the equal-weight mean of the available streams per cell.
- **Pinned arrays, group `combine`:**
  `hindcast_probability(year,category,lat,lon)`,
  `forecast_probability(category,lat,lon)`, `available_streams(lat,lon)`.
- **Instrument:** exact reference match within a float bound.
- **Local verdict:** from the agent's `wvg`, `ereg` and `cca` groups, exact.
  An agent with one wrong stream and a correct combine is locally correct
  here.

### Stage 7, verify

- **Produce:** cross-validated ranked probability score (RPS) and skill score
  (RPSS) for each stream and the objective, against equal-thirds climatology
  on the same observed categories.
- **Pinned arrays, group `verify`:** `stream_rps(stream,lat,lon)`,
  `stream_rpss(stream)`, `objective_rps(lat,lon)`, scalar `objective_rpss`.
- **Instrument:** reference match recomputed from the agent's own
  probabilities and categories. Absolute and local verdicts coincide by
  construction. Claims check: every skill number stated in the bulletin
  equals the corresponding array value.

### Stage 8, issue and write

- **Produce:** the issued forecast probabilities, the dominant-category map
  and the bulletin as `report.md`.
- **Pinned arrays, group `issue`:** `forecast_probability(category,lat,lon)`
  identical to `combine/forecast_probability`;
  `dominant_category(lat,lon)`.
- **Instrument:** simplex and identity invariants; judge questions owned by
  this task: the bulletin states uncertainty in plain language; every number
  it states appears in the submitted arrays; it makes no claim beyond the
  hindcast period and region. Withheld-season skill is reported as a number
  and never gates.

## Verdicts and rollup

1. The controller validates every group against its schema: names,
   dimensions, coordinate values against `target-grid.nc` and the declared
   years, dtype, finiteness, support masks.
2. A group that fails is `schema: fail` for its stage, with the first error
   quoted.
3. For each stage in order, the absolute verdict runs on controller inputs if
   the stage's own group passed its schema; otherwise it is `fail: schema`.
4. The local verdict runs if the stage's group and every upstream group it
   reads passed their schemas; otherwise it is `unresolved:
   invalid_upstream_contract`, naming the upstream group.
5. The rollup reports eight rows with both verdicts and their evidence, the
   fraction of absolutely passed stages under declared weights (equal by
   default), and completion as "every gating stage passed". Ranking uses the
   fraction first and withheld-season skill second, among attempts whose
   issued probabilities satisfy the invariants.

This rollup is a versioned change to the assessment format. Existing
templates are unchanged.

## Instances

Two, on one frozen snapshot:

| Instance | Season | Issue month | Forecast year |
| --- | --- | --- | --- |
| `gha--mam` | March–May, the long rains | February | retrospective, observations withheld |
| `gha--ond` | October–December, the short rains | August | retrospective, observations withheld |

The forecast year is a year inside the snapshot whose observations the
controller withholds. The hindcast years are the remaining training period.
The same year is used for both instances.

## Source route

The source service freezes the NMME suite through the IRI data library:
hindcasts and forecast issuance for each centre in the method document's
list, the observations, and the SST field for the WVG index. This is the
route the reconstruction has running for a genuine multi-model suite. The
C3S route is not used: its forecast issuance currently returns only ECMWF.

## The control and the references

- The control is the ICPAC reconstruction at
  `from_icpac/ghacof/frameworks/` (download, WVG, eReg, CCA, combine,
  analyze), run once on the frozen snapshot per instance. Its outputs become
  the reference arrays for every stage, plus the measured solver spread
  (stage 3) and engine spread (stage 5).
- The runtime references are pure Python: the deepscale WVG and eReg
  implementations, the pure-Python eigenvalue CCA, and the existing
  consolidation, scoring and regridding references.
- The one-time validation stores, per instance: deepscale WVG against the R
  WVG; pure-Python CCA against PyCPT; the resulting spreads. These files are
  evidence, not dependencies.
- Planted faults, one per stage, each confirmed to fire in its own stage and
  nowhere else: a wrong product fetched; thirty-day months; a held-out year
  used in the WVG fit; a regression fitted on all years; future years in the
  CCA training; unequal stream weights; a skill score against the wrong
  climatology; a bulletin number absent from the arrays.

## Budget

A tier above the existing templates, declared in the spec: hours of wall
time, hundreds of tool calls, a token allowance to match, with cost recorded
per attempt. The exact values are set after the control run shows the
control's own runtime at full scale. Scientific native I/O stays serial per
process with at most two shared workers.

## What the control run fixes

These values are not decided here; the control run writes them into the spec:

- The target grid's bounds, spacing and coordinate values.
- The hindcast years and the withheld forecast year.
- The centre list and its order.
- The quantile interpolation pair.
- The WVG solver spread bound.
- The CCA engine spread, and from it the RPSS margin.
- Every error bound's operation count and magnitude.
- The budget tier.

## Order of work

1. This record (done).
2. Freeze the snapshot; run the control per instance; store references,
   spreads and the one-time validations; plant and confirm the eight faults.
3. Add the per-stage rubric, the schema check, the two verdicts and the
   rollup to the assessment format as a versioned change.
4. Write the brief, the method document, `target-grid.nc` and the spec.
5. Review the brief as the agent sees it, every rubric row, the controls,
   the budget and the cost estimate. Record the review.
6. One cheap attempt on one instance, once. Read its profile and trace. Fix
   defects on controls as versioned changes; no retry.
7. The matrix: several backbones and harnesses on both instances, tooling
   fixed, one attempt each, two concurrent, traces read stage by stage.

## Step 2 record: what the control build changed

Recorded 9 October 2026 while building the snapshot and the control. Each item is a
departure from the design above, with its reason.

- **The source snapshot is acmadDL's delivery, not raw IRI responses.** A first attempt
  pulled raw NMME trees from the IRI Data Library at the predictor domain and was stopped:
  hundreds of megabytes per model, over the internet, before any control could run.
  The snapshot now holds what `acmaddl.fetch` returns for each product (one to four
  megabytes per model and season) plus NetCDF conversions of the acmadDL raw cache for
  CHIRPS 0.05-degree monthly and ERSST v5, both already on disk. No raw IRI download
  remains. Total snapshot about 280 MB, most of it CHIRPS.
- **The genuine data trap is the units, not the trees.** acmadDL already unites CFSv2's
  hindcast and realtime trees, so stitching is not the agent's job. But acmadDL delivers
  CFSv2 as season totals in mm (its `season_total_conversion`) while the other three
  centres arrive as mean rates in mm/day, with different coordinate dtypes. The practice
  document says "in the units each file declares" and nothing more.
- **The CCA predictor is the model rainfall field, not SST.** ICPAC's CPT configuration
  regresses observed rainfall on the model's rainfall field; the design text said SST and
  was wrong. The predictor domain is the served model box (13S–23N, 21–52E at one degree).
- **The target grid is 58 by 62 cells at 0.5 degrees, 12.75S–15.75N and 21.25–51.75E**, the
  part of the Greater Horn covered by the locally cached 0.05-degree CHIRPS; 2627 cells are
  supported (land with complete observations). This is a regional window, not the full
  ICPAC domain.
- **Stage groups are name prefixes in one Zarr store** (`prepare_`, `wvg_`, `ereg_`,
  `cca_`, `combine_`, `verify_`, `issue_`), because the controller reads one labelled store.
  The per-stage rubric of step 3 maps prefixes to stages.
- **The local verdicts exist today as invariants.** `equal_stream_combination`,
  `score_identity` and `issue_identity` recompute combine, verify and issue from the
  submission's own upstream arrays; `cca_agreement` is the method-blind CCA gate
  (correlation floor 0.85, RPSS margin provisional at 0.05 until the engine spread is
  measured). The absolute verdict for prepare, WVG and eReg is the reference match.
  The two-verdict rollup and the `invalid_upstream_contract` state are step 3.
- **The box mean is fixed as the plain mean of ocean cells**, not an open convention, so the
  reference table has 36 combinations instead of 72. The ERSST and CFSv2 boxes contain land.
- **The WVG forecast-year index is standardized against CFSv2's own hindcast climatology**,
  as the design said; the training index uses the observed target-season SST.
- **Mode selection in CCA is not nested.** The modes are chosen once per model by
  leave-one-year-out correlation over the training years, then the hindcasts use those modes;
  this matches CPT's practice and keeps the stage at a few seconds (one SVD pair per fold
  serves all 120 candidates).
- **Both instances withhold 2015** and train on 1993–2016 without it; the hindcast
  cross-validated RPSS on MAM is near zero for every stream (about 0.02 for the objective),
  which is expected for the long rains and is reported, not gated.
- **Eight planted faults** map to the stages: wrong initialization (acquire), thirty-day
  months (prepare), a leaking WVG fit, an uncross-validated eReg, CCA trained on the held-out
  year, unequal stream weights, a wrong climatology in the score, and issued probabilities
  that do not match the objective. The bulletin-number fault of the design is left to the
  judge because it is not computable.

- **The CCA gate is set from the measured engine spread, and the 0.85 floor fell.** africaS2S's
  CPT-parity CCA on the same prepared arrays (its window-5 cross-validation and Kendall-tau
  mode selection, with and without the empirical transform) correlates with the reference CCA
  at 0.64–0.90 per category on the MAM hindcasts, 0.75–0.91 on OND, and 0.70–0.98 on the
  forecasts, and its cross-validated RPSS is up to 0.061 (MAM) and 0.067 (OND) below the
  reference's. A genuine alternative engine must
  pass the gate, so the correlation floor is 0.6 and the RPSS margin 0.08
  (`var/validation/objective-seasonal-outlook/cca-engine-spread-mam.json`). This supersedes
  the 0.85 decided before the measurement; it is the measurement the record called for.
- **CCA mode selection is nested after all.** With selection on all years the correct control
  failed the held-out-year probe, because a year's observation enters its own hindcast through
  the selection and the pooled residual variance. The reference now selects modes and takes
  the variance inside each fold; the cost is twenty seconds per instance.
- **The WVG bound is 2.2e-5**, from a measured maximum solver gap of 5.0e-6 against scipy.
- **The tercile category carries a 1e-6 mm margin at the boundary.** The first
  certification run failed test 1 on MAM under bilinear regridding: in desert cells at
  the northern edge, CHIRPS repeats one seasonal total across up to thirteen training
  years, the one-third quantile lands exactly on that value, and two correct linear
  interpolation formulas differ by one unit in the last place. A strict "below the
  boundary" then flips thirteen labels and moves the WVG forecast by 0.32 at the cell.
  The census (`var/validation/objective-seasonal-outlook/tie-census.json`) counts 2 to 35
  such cells per instance and reading; the ties come from identical input years, so the
  set is fixed per reading and does not depend on the agent's code. The practice
  document and the brief now say: a total within one millionth of a millimetre of a
  boundary is near normal. Both references apply it; the stored references were rebuilt.
- **A result that matches no listed reading is `unresolved` on the variant match, not
  `fail`.** The matcher can only say which reading a result matches; a leak or a wrong
  initialization matches none, and the changed-data probe inherits that. The control
  expectations say so: the leak faults are caught by the held-out-year probe, the wrong
  initialization by the CCA agreement invariant, and both leave the variant match and
  the changed-data probe unresolved. The step-3 rubric must make this explicit: an
  unresolved absolute verdict with a failed local verdict is a failed stage.
- **The unequal-weights fault verifies its own combination.** As first planted it left
  the verify arrays from the equal-weight combination, so the score-identity invariant
  failed as well; an agent that weights unequally would verify what it combined. The
  control now recomputes its verification, and only the combination rule breaks.
