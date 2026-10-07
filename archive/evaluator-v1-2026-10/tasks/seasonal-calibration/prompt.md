# Validate and save a seasonal rainfall calibration

A forecaster needs a reusable calibration for September-issued October–December
rainfall in a Kenyan study box: south −3, north 1, west 36, east 39. Build and
validate a documented calibration using the supplied monthly inputs, then save
the fitted workflow so it can predict new forecast inputs without refitting.

Start with `source-plan.json`, which identifies the sources, training years,
region and forecast request. Acquire ECMWF system 51 monthly precipitation for
September initializations, lead months 2, 3 and 4, all returned hindcast members,
and 1993–2004, plus native CHIRPS v3 final monthly totals for those OND seasons.
Use the experiment's permitted provider access or frozen raw-response replay.
Normalized training arrays are not supplied in the acquisition task. Retain the
source bytes or sufficient native subsets for an offline replay, and record the
requests, retrievals and any cache use. A command-line downloader or skill is
equally valid as custom code.

Read the returned units before conversion. The inherited ECMWF provider response
used metres per second: convert that rate to mm/day by multiplying by 86,400,000;
an already normalized mm/day response needs no such conversion. Native CHIRPS
monthly totals are in mm. Preserve native centres when extracting CHIRPS subsets;
do not replace them with a precomputed regional mean. Preserve the forecast grid
listed in the source plan and its member identities.

These are retrospective development products, not reconstructed data vintages
available in each historical year. Data access is restricted to the declared
products and training observation years; never retrieve the 2005–06 verification
observations. A source change or service failure is recorded as an infrastructure
issue rather than silently changing the task or substituting normalized fixtures.

Convert each rate to its month's rainfall total using the actual month length,
then sum OND. Aggregate CHIRPS within each one-degree forecast cell using
cosine-latitude weights. Include native cell centres in `[centre−0.5, centre+0.5)`
on each axis, renormalize valid weights, and require at least 90 percent valid
area in every monthly cell. Preserve the forecast grid and member identities.

Fit any explicitly documented sound calibration using training data only. Produce
below/near/above probabilities and a nonnegative rainfall estimate. Tercile
thresholds are linear observed quantiles at 1/3 and 2/3; equality belongs to the
middle category. Validate by leaving out each training year in turn. Fit learned
preprocessing, thresholds, calibration and any tuning without that year's data.
Explain your fold construction, compare development results with an explicit
climatological baseline, and show a reliability diagnostic with sample counts.

Deliver:

- `training.nc`: `forecast(year,member,lat,lon)` and `observed(year,lat,lon)`, both in mm.
- `development.nc`: `probability(year,tercile,lat,lon)` with labels `below,near,above`, and `rainfall_mm(year,lat,lon)` with mm units, covering all 1993–2004 years.
- `answer.json`: nonempty `method`, a `development_validation` object with defined metrics and baseline, and `limitations`.
- `provenance.json`: follow the shared provenance contract; record source requests, retained-file hashes, units, grid/mask rules and fold definitions, including the training years excluded in each fold. Retain fold-specific thresholds or enough intermediate evidence to verify them.
- `report.txt`, a labelled `outlook.png`, and `handoff.txt` explaining the workflow, retained state, validation and limitations. This box is not a national Kenya average.
- `execution.json` and all required retained data/workflow/fit artifacts: declare offline replay and prediction commands following the shared replay contract. Prediction reads a new `forecast(year,member,lat,lon)` in mm and writes the same schema as `development.nc`, loading saved fitted state without refitting. No language or script filename is prescribed.

The provenance and replay contracts are supplied with the task brief. File
presence, schemas, source coverage and the information boundary are basic validity
requirements. The rubric scores acquisition, preparation, calibration,
development verification, interpretation and workflow reuse as six outcomes.

The evaluator will supply a forecast-only 2005–06 batch to the frozen prediction
workflow; verification observations are never agent inputs. Those years were
previously inspected during pilot development, so their scores cannot establish
untouched evaluation or reliable calibration. Do not claim unseen private skill.
A negative development result can complete the task when the work is correct.

All deliverables go in the submission directory. Runtime and attempt budget are
supplied by the experiment. General or domain tools depend on the assigned
substrate; the task does not require a particular library.
