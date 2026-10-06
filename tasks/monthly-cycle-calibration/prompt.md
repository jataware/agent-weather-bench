# Reconstruct cyclic monthly calibration with whole-year validation

Build a reproducible monthly statistical rainfall forecasting experiment from
real CHIRPS regional targets and prior-calendar-month ERA5 SST predictors. Test
whether sharing estimated regression slopes across the seasonal cycle helps or
hurts, while separating forecast validity from positive improvement. The source
paper and AfricaS2S code motivate cyclic sharing, but this is an explicitly
specified METHOD ADAPTATION, not their CanSIPS dynamical-hindcast experiment.

Read `algorithm.md`, `literature-notes.md` and the attributed source excerpt.
Implement the complete fixed procedure. Inputs `predictors.nc` and `targets.nc`
contain31 complete predictor years 1993–2023 and27 training-target years 1993–2019.
All twelve target months are one held-out year block. Predictor values already
use the previous calendar month; January uses previous December. Do not shift
these supplied predictors again or access target-month SST. Retain the region
order exactly: somalia,kenya,eastern-horn. The target totals are already mm;
no calendar-day factor remains to apply. Runtime is2 CPU/4GB, offline, with
NumPy/SciPy/xarray available. No GPU or provider credentials are needed.

Deliver:

- `hindcasts.nc` with year 2005–2019, month 1–12, system=[climatology,
  independent-month,constant-slope,nested-cyclic], target equal supplied regions,
  candidate 0–5. Required variables prediction(year,system,month,target),
  coefficient(year,system,month,target) in mm/degree_Celsius,
  standardized_coefficient(year,system,month,target), selected_candidate(year),
  inner_loss(year,candidate), xmean(year,month), xstd(year,month),
  ymean(year,month,target), ystd(year,month,target),
  squared_error(year,system,month,target), monthly_msss(system,month), msss(system).
  Predictions/ymean/ystd have units mm; xmean/xstd degree_Celsius; squared_error mm2.
  Climatology coefficients are zero. All transforms are training-only.
- `forecast.nc` with year 2020–2023 and the same system/month/target/candidate
  coordinates: prediction(system,year,month,target),
  coefficient(system,month,target), standardized_coefficient(system,month,target),
  scalar selected_candidate and inner_loss(candidate), using the same units.
- `answer.json`: task=monthly-cycle-calibration, training_years1993–2019,
  verification_years2005–2019, prediction_years2020–2023 (inclusive endpoints or
  exact year enumerations), rainfall_units=mm, msss mapping by system,
  dynamical_hindcasts_used=false, full_paper_reproduction=false, limitations list.
- `report.txt`: cite actual sources and explain this task's departures; demonstrate
  Dec/Jan coupling and whole-year exclusions; interpret actual monthly and pooled
  skill without treating36 month-region pairs within a year as independent
  replications. Explain sampling/selection uncertainty and paired year comparison.
  Discuss final-vintage data, prior-month publication assumptions, negative
  precipitation predictions if present and support for gains or losses. Never
  claim improvement on controller-private targets you have not seen.
- `outlook.png`, `provenance.json`, `handoff.txt`, `execution.json`, executable
  code and fitted state. Provenance must identify supplied sources and retained
  hashes plus processing/fold/smoothing parameters. A diagram must distinguish
  standardized versus physical slopes and label the forecast/verification split.

Full replay must honor alternate input/output directories. Saved prediction
must work without any target observations or cached hindcasts, using the original
fitted monthly means/scales/slopes. The controller changes held-out-year targets
and future predictors to test year isolation, then changes final SST to test
real saved-state inference. Requirements and exact array semantics are public;
no arbitrary loading-vector or code-style matches are required.
