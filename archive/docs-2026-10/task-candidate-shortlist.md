# Source grounded task shortlist

Source audit, 5 October 2026. These nine proposed additions complement the four
current task packages. They are **candidates, not nine registered or validated
tasks**. The competition entries belong to a shared optimization family; their
variable and lead variants must remain visible as related instances. The aim is
10–15 useful examples with explicit readiness, rather than a claim of 10–15
independent scientific benchmarks.

Start with a regional historical subseasonal competition replay, a CPT/CCA
reproduction, and a WeatherBench 2 verification reconstruction. Prepare the
rainy-season onset task as the scientific stretch. Each adds a different outcome:
iterative improvement, substantial method reconstruction, trustworthy comparison,
and a probabilistic event with a genuine possibility of non-occurrence.

## What was actually inspected

- The current task prompts, portfolio and evaluation plan were read. The existing
  tasks cover probability combination, WVG definition, a seasonal calibration
  workflow, and the nested short-rains workflow. The earlier twelve-row portfolio
  contains candidate families and variants, not twelve completed task packages.
- AfricaS2S was read locally at revision
  `4f8526a32232f9c9af400a01e5a6f103a865c735`: its README, CPT parity/reproduction
  scripts, onset example and BCSD implementation. The public repository address
  is [ACMAD-Niamey/africas2s](https://github.com/ACMAD-Niamey/africas2s).
  Browser retrieval of that repository did not succeed, so this is an inspected
  local revision, not a newly verified remote HEAD.
- The ICPAC replication README and output metadata were inspected at local
  revision `ebfc55272670f61d47a910220056b05aac66c667`, remote
  [accord-research/icpac-mam-replication](https://github.com/accord-research/icpac-mam-replication).
  Its method-fidelity statements remain the repository authors' claims; they were
  not independently reproduced during this shortlist audit.
- Three real local NetCDF files were opened for metadata: monthly CHIRPS
  1981–2020 with dimensions `T=480, Y=77, X=66` and `mm/month`; January 2026
  ECMWF precipitation with `lead=6, ens=51, lat=77, lon=66` and `mm/day`; and a
  bundled PyCPT MAM map with three percentage variables on a `140×128` grid.
  These establish that useful local artifacts exist. They do not establish
  complete hindcast coverage, licenses, value fidelity or daily data availability.
- Public primary paper, author repository and official benchmark pages below
  were opened or retrieved through primary publisher search results. Except for
  the local revisions above, **repository revisions are not pinned yet**.
  Public dataset files were not downloaded or opened during this audit.

No new inference calls, credentials, task registrations or controller changes
were used. All compute figures below are **packaging estimates for deliberately
small subsets**, excluding downloads and agent deliberation; none is a measured
task runtime. Retrospective public targets may have been seen by models or used
in research. A controller-private copy makes final feedback private, not the
underlying historical data pristine.

## Nine candidates

### 1 Subseasonal competition leaderboard replay

**Sources.** The official [2021 S2S AI Challenge](https://s2s-ai-challenge.github.io/),
[challenge template](https://github.com/aaronspring/s2s-ai-challenge-template),
[ECMWF data plugin](https://github.com/ecmwf-lab/climetlab-s2s-ai-challenge), and
[challenge paper](https://journals.ametsoc.org/view/journals/bams/103/12/BAMS-D-22-0046.1.xml)
provide an archived competition with probabilistic forecasts and ranked
probability skill score. This is a historical replay, not entry into an active
competition. See the proposed [leaderboard track](subseasonal-leaderboard-track.md).

**Bounded objective.** Improve a pinned calibrated-ECMWF or climatological baseline
on one regional temperature or precipitation instance at weeks 3–4, with a fixed
search budget. Deliver final tercile probabilities, fit state, executable
inference and an experiment ledger. Add temperature/precipitation and weeks 5–6
instances only after the first reference passes; these are variants of one track.

**Data and compute.** Public source records exist; actual file retrieval,
corrected observation version, grid support and training availability still need
inspection. Estimate 5–30 CPU minutes per simple regional candidate, 2–8 GB RAM;
full global training is outside this initial scope.

**Evaluation and trap.** Independently implement the official score and compare
against the pinned source scorer. Expose a development leaderboard with a
predeclared number of submissions; score a frozen final artifact once on a
controller-private period. Verify issue-time availability, fold-local thresholds
and inference without targets. The main failure is optimizing feedback or leaked
observations rather than forecast generalization. Record every feedback exposure,
submission, compute limit and intervention.

**Readiness and overlap.** High source readiness, data/reference pending. This
adds adaptive experimentation beyond the prescribed short-rains candidate search.
Paper/official leaderboard results cannot be claimed from a smaller regional replay.

### 2 Reconstruct the CPT CCA forecasting component

**Sources.** The official [PyCPT documentation](https://iri-pycpt.github.io/),
[PyCPT code](https://github.com/iri-pycpt/pycpt), and
[seasonal configuration guide](https://github.com/iri-pycpt/PyCPT2-Seasonal-Forecast-User-Guide/blob/main/configuration.md)
define a real seasonal forecasting workflow. Local AfricaS2S
`scripts/benchmark_pycpt.py` and `scripts/reproduce.py` contain detailed
implementation and comparison records at the inspected revision above.

**Bounded objective.** Reconstruct one pinned East African MAM CCA component from
the method/source pack: training preprocessing, mode selection, deterministic
cross-validation, production probabilities and a saved fit. Explain which source
outputs are genuinely cross-validated. Do not require reproducing the entire
three-component centre outlook.

**Data and compute.** Existing monthly observations and output maps are real;
the exact predictor hindcast cube and CPT binary/configuration need freezing.
Estimate 5–30 CPU minutes for 25–30 years on a small grid; CPT setup is separate.

**Evaluation and trap.** Compare predictions and intermediate invariants against
a pinned CPT execution plus an independently checked mathematical implementation.
Allow sign flips and rotations in equivalent EOF bases rather than matching
loadings elementwise. Use held-out-target perturbations to test fold isolation.
The local parity script warns that a PyCPT probabilistic hindcast route fits
all years even when its deterministic predictions are cross-validated. Numerical
source fidelity must not become an unsupported claim of out-of-sample skill.

**Readiness and overlap.** Highest local readiness, subject to fixture/binary
audit. Distinct from ACMAD combination and scalar short-rains OLS: this tests
multivariate spatial dimension reduction, uncertainty and source/code fidelity.

### 3 Seasonal cycle smoothed calibration

**Sources.** Kharin et al. (2017),
[A Postprocessing Method for Seasonal Forecasts Using Temporally and Spatially Smoothed Statistics](https://doi.org/10.1175/MWR-D-16-0337.1),
studies sharing calibration information across seasons. AfricaS2S has
`src/africas2s/methods/smoothed_regression.py` and runnable demonstrations at the
inspected revision. The publisher source was retrieved in primary search;
direct opening was blocked. A full method extract still needs preservation.

**Bounded objective.** Reproduce temporal smoothing of regression coefficients
on a small twelve-season hindcast cube, comparing independent-season, cyclic
smoothed and constant coefficients under nested year validation. Produce saved
forecast inference and report when smoothing hurts as well as helps.

**Data and compute.** Current seasonal-task inputs contain only the nominated
season, so they are insufficient. Need real all-season hindcasts and observations
with unambiguous rolling-window definitions. Estimate 2–20 CPU minutes, 2–4 GB.

**Evaluation and trap.** Independently check fitted coefficients, cyclic boundary
behavior and folds; score saved predictions against climatology and independent
season fits. Verify all seasons of a held-out year are excluded before coefficient
smoothing and hyperparameter choice. Otherwise year leakage masquerades as the
benefit of statistical sharing.

**Readiness and overlap.** Local code available, new data needed. Same broad
seasonal family, substantially different sampling/regularization question.
This is a method-level reproduction on new data, not replication of the paper's
complete CanSIPS experiment or published numerical gains.

### 4 Audit and repair a precipitation downscaling workflow

**Sources.** Wood et al. (2004),
[Hydrologic Implications of Dynamical and Statistical Approaches to Downscaling Climate Model Outputs](https://doi.org/10.1023/B:CLIM.0000013685.99609.9e),
anchors BCSD. Its publisher abstract was accessible; the full paper was not.
The local AfricaS2S `src/africas2s/methods/bcsd.py` was inspected. It currently
interpolates observations to the coarse grid and adds fine climatological detail;
that implementation is not an independent oracle for conservation or exact paper fidelity.

**Bounded objective.** Assess and repair a specified seasonal precipitation
downscaler so that its fitted spatial detail uses training-only observations,
rainfall stays nonnegative, and coarse-cell area totals satisfy an explicit
task contract. Compare against simple interpolation and a climatological baseline.

**Data and compute.** Need paired real coarse hindcasts and fine monthly CHIRPS
on a bounded domain, with cell bounds and masks. The inspected 0.5° CHIRPS cache
is not the required fine target. Estimate 5–20 CPU minutes, 2–8 GB.

**Evaluation and trap.** Independent conservative aggregation and distribution
checks, holdout perturbations, final inference and matched skill comparisons.
The trap is attractive fine-scale maps that introduce negative rainfall or create
water, or evaluate on the climatology used to construct the maps.

**Readiness and overlap.** Data and full method extract pending. A forecast
downscaling extension motivated by the paper, explicitly not a reproduction of
its climate-change/hydrology experiment. Adds spatial support and physical
constraints absent from current tasks.

### 5 Probabilistic rainy season onset with failed seasons

**Sources.** Scheuerer et al. (2024),
[Probabilistic rainy season onset prediction over the greater horn of Africa](https://doi.org/10.1007/s00382-023-07085-y),
has accessible daily threshold correction, onset probability and ensemble-size
verification methods. AfricaS2S `examples/onset_gha_mam.py` provides a local
starting point, but its convenience defaults are not proof of paper equivalence.

**Bounded objective.** Reconstruct one OND regional onset experiment: correct
daily and three-day thresholds within training folds, reject false starts,
retain probability of failed onset, and compare a model ensemble with climatology.
Include ordinary and fair Brier scoring to examine member-count effects.

**Data and compute.** Need daily hindcast members plus daily CHIRPS, including
the post-search days required to resolve false starts. Neither was opened here.
Freeze a few locations or a 10×10 grid first. Estimate 10–60 CPU minutes, 2–8 GB.

**Evaluation and trap.** Independent event-state implementation with boundary
cases, dates and missing-data states; score the frozen predicted distribution.
The paper uses strict threshold wording that differs from some library defaults,
so pin equality, dry-run length and lookahead semantics explicitly. Conditioning
on seasons that started silently removes drought failures; dropping such members
overstates onset probability. Larger ensembles can improve ordinary scores
without demonstrating a better individual forecasting system.

**Readiness and overlap.** Strong full-method source, daily-data acquisition
pending. Recommended stretch task. This adds event/non-event uncertainty and
daily temporal structure, not another seasonal-total regression.

### 6 Climb a SubseasonalClimateUSA baseline leaderboard

**Sources.** Mouatadid et al. (2023),
[Adaptive bias correction for improved subseasonal forecasting](https://doi.org/10.1038/s41467-023-38874-y),
[SubseasonalClimateUSA paper](https://arxiv.org/abs/2109.10399),
[toolkit](https://github.com/microsoft/subseasonal_toolkit) and
[dataset description](https://github.com/microsoft/subseasonal_data/blob/main/DATA.md).
The ABC paper evaluates mean per-date uncentered spatial anomaly correlation,
with a fixed 1981–2010 climatology. These are different metric conventions from
the S2S AI Challenge's probabilistic RPSS.

**Bounded objective.** Improve a pinned raw CFSv2 or Dynamical++ baseline on one
temperature weeks 3–4 instance, with bounded model and window search. Deliver
the best development submission and one frozen final predictor. Precipitation
and weeks 5–6 are later instances in this optimization track, not new independent
paper reproductions.

**Data and compute.** Author code and download interface exist, but remote files
were not opened. Audit training-label release lag and freeze the data dependency
graph before launch. Estimate 10–60 CPU minutes for a regional/restricted-year
search. The repository's reported seven-minute raw demo is a source claim for
its own machine and task, not our measured optimization runtime.

**Evaluation and trap.** Independently verify per-date skill, fixed climatology,
date averaging, common support and zero-norm behavior against source code. Use
development feedback with an iteration cap and a private final chronological
period. Recent observations must be available at issue time; a training example
whose two-week target has not yet ended cannot be used. Do not replace uncentered
spatial correlation with centered correlation or pool all dates into one score.

**Readiness and overlap.** Source-ready, actual data retrieval/version pending.
Related to candidate 1 as a competition optimization family; useful as a second
protocol, but launch one track first. The original
[Forecast Rodeo II leaderboard](https://www.drought.gov/forecast-rodeo-ii-leaderboard)
is historical context, not a currently active submission endpoint.

### 7 Rebuild a WeatherBench 2 comparison from archived forecasts

**Sources.** [WeatherBench 2 paper](https://arxiv.org/abs/2308.15560),
[code](https://github.com/google-research/weatherbench2) and the official
[evaluation quickstart](https://weatherbench2.readthedocs.io/en/latest/evaluation.html)
provide forecast, ERA5 and climatology Zarr addresses, including 64×32 data.

**Bounded objective.** Reproduce RMSE and anomaly-correlation curves for two
precomputed forecasts and one surface variable over fixed dates/leads. Investigate
a nominated ranking discrepancy and generate an independently reproducible scorecard.
This avoids GPU inference while retaining a real scientific comparison.

**Data and compute.** Exact HRES/ERA5/climatology paths are documented publicly;
they were not accessed as arrays here. Choose a second baseline whose matching
resolution and coverage are actually available. Freeze a 100–500 MB subset;
estimate 2–10 CPU minutes and 1–4 GB after acquisition.

**Evaluation and trap.** Independent small-array formulas and source scorer,
valid-time alignment, latitude weighting, missing-support denominators and
climatology checks. Perturb one valid date and one coordinate ordering. The
trap is model-dependent support or incorrect forecast-time matching that
creates an apparent ranking gain. ERA5 is a reanalysis verification target,
not direct station truth.

**Readiness and overlap.** Highest public data/source readiness; retrieval and
second-baseline audit pending. This is scientific verification and diagnosis,
distinct from producing the original model forecasts or training a weather model.

### 8 Fit a precipitation predictive distribution with dry-day mass

**Sources.** Scheuerer and Hamill (2015),
[Statistical Postprocessing of Ensemble Precipitation Forecasts by Fitting Censored, Shifted Gamma Distributions](https://doi.org/10.1175/MWR-D-15-0061.1),
is available through the primary [NOAA repository](https://repository.library.noaa.gov/view/noaa/14608),
including its full PDF. An executable author-code revision was not verified.

**Bounded objective.** Implement the specified censored shifted-gamma model for
one small ensemble reforecast domain, fit on a chronological training block,
and produce probabilities of no rain and threshold exceedance on final dates.
Compare against the raw ensemble and climatology using independently computed
CRPS and Brier scores. Include constraints, convergence diagnostics and inference.

**Data and compute.** Need real daily GEFS reforecast/observation pairs and any
additional predictors required by the selected model equations. Current monthly
seasonal fixtures cannot substitute. Estimate 10–60 CPU minutes for 5–20
locations; real archive availability and exact units remain blockers.

**Evaluation and trap.** Independent CDF/integration checks, dry-mass and tail
probabilities, proper-score verification and withheld-date perturbation. The
trap is treating zero rain as a continuous gamma observation or obtaining
nonphysical parameters through an unconstrained optimization that still reports
convergence. Calibration correctness and forecast improvement are separate outcomes.

**Readiness and overlap.** Full paper source available, data and code pin pending.
Adds distribution fitting and numerical optimization rather than a new spelling
of the current tercile OLS task; lower overnight readiness than candidates 1, 2, 7.

### 9 Verify forecasts against stations with matched coverage

**Sources.** [WeatherReal paper](https://arxiv.org/abs/2409.09371) and
[official repository](https://github.com/microsoft/WeatherReal-Benchmark)
provide station-based evaluation code. Its public ISD product is a 2023 NetCDF
distributed through Git LFS; Synoptic data requires contacting its provider and
is excluded from autonomous initial packaging.

**Bounded objective.** Reconstruct a temperature comparison for two supplied
gridded forecasts at fixed stations and leads. Diagnose how interpolation,
station masks and unequal availability alter the published-style ranking,
then issue a comparison on explicitly matched support.

**Data and compute.** ISD data availability is documented but not downloaded;
matching forecast cubes must be located and frozen. Select 50–200 stations and
one month first. Estimate 2–15 CPU minutes, 1–4 GB after acquisition.

**Evaluation and trap.** Independent station interpolation and units/valid-time
checks; recalculate both coverage and RMSE, with private missingness and station
ordering perturbations. The trap is comparing model-dependent station samples,
or treating station pressure as sea-level pressure. Sparse regional station
coverage should constrain the claim rather than invite fabricated evidence.

**Readiness and overlap.** Public source ready, forecast-data pairing pending.
Related to candidate 7's verification family, but observation representativeness
and station support create a different scientific question. A small subset
cannot reproduce the official global leaderboard.

## Packaging order and acceptance gates

The three highest-readiness choices are **1 competition replay, 2 CCA component,
and 7 WeatherBench 2 verification**. This prioritization is a judgement about
source/code access, not a claim their fixtures are already ready. Onset is the
stretch choice because its scientific contract is explicit and its mistakes
would be consequential; freeze daily data before spending on solvers.

For each promoted task, require a source/revision record, redistributable real
fixture, frozen issue/split contract, independent reference, correct alternative,
one plausible scientific defect and one replay/inference defect. Require a cheap
baseline execution before any agent trial. Preserve paper ambiguities in a
curator addendum rather than letting the judge invent their resolution.

For leaderboard tasks, freeze a maximum of five development submissions per
attempt and one final scoring call as an initial design proposal. A final score
can be lower than the baseline without invalidating the workflow; scientific
validity, operational completion and improvement are separate reported outcomes.
Reserve a final chronological block with an exclusion gap at least as long as
the target window. Hide its labels and aggregate feedback from the solver, but
record that its public historical source may be contaminated.

Four existing packages plus these nine candidates yield thirteen **proposed
examples**. Promoting four competition variants instead of one would create
sixteen instances, so retain 10–15 based on coverage and calibration readiness,
not by automatically counting every variable/lead combination. Keep related
instances grouped in reporting and avoid presenting their results as independent
replications.
