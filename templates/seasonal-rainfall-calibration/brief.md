# Calibrate a seasonal rainfall forecast to the WMO guidance

`/work/inputs` holds ECMWF forecasts issued each September for October–December rainfall over a box in Kenya (`forecast-training.nc`: monthly rates by ensemble member, {training_span}), CHIRPS observed monthly rainfall for the same seasons (`observations-training.nc`), and the model's seasonal totals for {new_span} (`forecast-new.nc`).

Produce a calibrated tercile-probability forecast for {new_span} that conforms to `guidance.md`. Return, on the forecast grid:

- `forecast_mean_mm` and `observed_total_mm`: ensemble-mean forecast and observed seasonal totals, `[year][latitude][longitude]`;
- `hindcast_probability`: cross-validated probabilities of below-, near- and above-normal rainfall, `[year][category][latitude][longitude]`;
- `observed_category`: the observed category of each year (0 below, 1 near, 2 above), `[year][latitude][longitude]`;
- `hindcast_rpss`: the skill score of those probabilities;
- `forecast_probability`: `[new_year][category][latitude][longitude]`;
- `year`, `new_year`, `latitude`, `longitude`: the order of your arrays.

In the `method` section, give entries `calibration` and `cross_validation`.
