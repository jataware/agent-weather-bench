# Regional rank calibration and conservative spatial detail

This is a bounded adaptation of BCSD, using the supplied AfricaS2S source as a
starting point. It does not reproduce Wood et al.'s hydrological experiment.
Read `instance.json` for the training end and forecast years.

Fine CHIRPS observations are already seasonal totals in mm. Coarse CFSv2
predictors have unresolved physical scale: native metadata says mm/day, but
source magnitudes do not support a confident rate interpretation. Use them as
monotonic predictors. Do not invent a day-count conversion. A positive affine
transform applied consistently to raw training and forecast predictors must
leave calibrated rainfall unchanged.

Each fine pixel spans 0.05 degrees about its centre. Its spherical area is
6371000² × (sin(north) − sin(south)) × (east − west in radians). Four complete
one-degree cells are centred at (1,37), (1,38), (2,37), (2,38), in that order.
Aggregate observations to these cells with fine pixel areas.

Per coarse cell, sort training raw predictors and observed coarse totals
independently and pair their ordered values. Average the paired sorted observed
values within each group of tied raw predictors. Interpolate linearly in raw
predictor coordinates and clamp outside the training range to the observed
endpoints. Fit no parametric tails.

Compute the fine climatology over the fit years and divide each pixel's value
by its own coarse cell's area-weighted fine climatology. Multiply mapped coarse
rainfall by this nonnegative ratio. This conserves the calibrated coarse area
mean, not the raw predictor's unknown physical units.

For each training-year hindcast exclude that entire year from both the rank
mapping and spatial climatology. Later training years may be used: this is
retrospective leave-one-year-out validation, not operational real-time skill.
Forecast the requested years using the full frozen training set. Retain all
fine pixels and all four coarse cells.

In the report explain unresolved source units, endpoint clamping, the symmetric
validation scheme and the distinction between mapped-field conservation and a
physical model moisture budget. Geometry was snapped by at most 3.3e-6 degrees
without changing precipitation values. Sources and processing notes are supplied.
