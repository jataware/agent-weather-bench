Repair seasonal precipitation calibration and conserve mapped rainfall

Use the supplied AfricaS2S BCSD implementation as an implementation starting point
and the cited Wood et al.(2004) method as scientific motivation. Reconstruct the
following predeclared regional adaptation, not the original hydrological experiment.
The source data are real February-initialized CFSv2 MAM coarse predictors and fine
CHIRPS MAM observations over four inland Kenya cells. Native source codes/headers
and processing notes are supplied. Diagnose the limitations before interpreting skill.

Inputs under /work/submission/inputs:
- coarse-forecast.nc: raw_predictor(year,coarse_cell), years1993–2016. Four nominal
  one-degree cells centered(lat,lon)=(1,37),(1,38),(2,37),(2,38), in that order.
- fine-training.nc: observed seasonal_total(year,lat,lon) in mm, MAM1993–2008 only;
  native CHIRPS monthly totals were recovered from a documented legacy divide30
  conversion and summed over March/April/May. They are already correct totals.
- geometry.nc: nominal .05degree pixel centers lat.525..2.475, lon36.525..38.475.
  Coordinates were snapped from native floating encodings by at most3.3e-6degrees;
  numeric source precipitation values were unchanged.
- AfricaS2S source implementation, original CPT header and legacy conversion code.

Important source anomaly: both the original CFSv2 CPT header and cached NetCDF
label predictors mm/day, but local magnitudes16–300 are incompatible with confidently
interpreting typical values as a MAM daily rate. Their true physical scale remains
UNRESOLVED. Do not invent a ×92day correction. Here raw values are only a monotonic
calibration predictor; calibrated outputs acquire physical mm from observed targets.
Explain this choice and its limitation. A unit conversion applied consistently to
both training and prediction must not change this method under a positive AFFINE
transformation a*x+b. This does not establish the source's correct physical units.

Implement exactly:
1. Fine-pixel area is R²*(sin(north)-sin(south))*(east-west in radians), R=6371000m;
   each nominal pixel extends .025degrees about its center. Aggregate observed
   seasonal totals by these areas separately within each complete one-degree cell.
2. Fit years1993–2008. Sort raw coarse predictors and observed coarse seasonal
   totals independently per cell. Pair their ordered values; interpolate linearly
   in raw-predictor coordinates. If raw ties occur, average the paired sorted
   observed values in the tied group. Clamp outside the training range to the
   corresponding observed endpoint; do not extrapolate or fit a parametric tail.
3. Compute each fine pixel's mean observed seasonal total across fit years.
   Divide it by its own coarse cell's area-weighted mean of that fine climatology.
   Multiply each mapped coarse prediction by this nonnegative within-cell ratio.
   The coarse mean of the downscaled field must equal the MAPPED coarse value;
   this is conservation of the calibrated field, not preservation of raw unknown
   CFSv2 units, nor conservation of the original model's moisture budget.
4. Produce2009–2016 forecast.nc using the one frozen1993–2008 state. Produce
   hindcasts.nc for each1993–2008 year, leaving that entire year out of BOTH
   distribution mapping and spatial climatology. This is retrospective symmetric
   leave-one-year-out validation; later training years are permitted, and it must
   not be described as historical real-time forecasting.

forecast.nc requires rainfall_mm(year,lat,lon), mapped_coarse_mm(year,coarse_cell),
area_m2(lat,lon), coarse_cell_id(lat,lon), exact public coordinate order, mm rainfall
units and m2 area units. hindcasts.nc requires rainfall_mm and mapped_coarse_mm
with the same dimensions, training years and physical units. Preserve all support;
negative values or NaNs are invalid, and simple clipping of an additive field
must not silently create mass. Tail clamping is prescribed and must be discussed.

Retain executable code and fitted model.json, plus execution.json for offline
replay and saved-state inference; see replay-contract.md. Report what changed
from the supplied interpolation/additive-detail code, numerical invariants,
training/hindcast boundaries, unresolved unit metadata, snapping/geometry choices,
coarse and fine skill limitations, and the difference from Wood et al.'s study.
Negative or unmeasured skill must be reported honestly. Final fine observations
are private and historical public source records, not a pristine scientific holdout.

answer.json fields: task="conservative-downscaling",
raw_unit_status="unresolved_source_scale", training_years=[1993,2008],
prediction_years=[2009,2016], conservation_definition (mapped coarse area means),
limitations (nonempty list). Also provide report.txt, handoff.txt, provenance.json
following the shared contract. Cite the supplied source IDs and actual processing.
