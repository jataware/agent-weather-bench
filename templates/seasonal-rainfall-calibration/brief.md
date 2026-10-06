# Calibrate a seasonal rainfall forecast to the WMO guidance

`/work/inputs` holds ECMWF forecasts issued each September for October–December rainfall over a box in Kenya (`forecast-training.nc`: monthly rates by ensemble member, {training_span}), CHIRPS observed monthly rainfall for the same seasons (`observations-training.nc`), and the model's seasonal totals for {new_span} (`forecast-new.nc`).

Produce a calibrated tercile-probability forecast for {new_span} that conforms to `guidance.md`. Return these on the forecast grid. Their dimensions are `year` (the training years), `new_year`, `category` (0 below, 1 near, 2 above normal), `latitude` and `longitude`:

- `forecast_mean_mm` and `observed_total_mm`, on `year`, `latitude`, `longitude`: ensemble-mean forecast and observed seasonal totals;
- `hindcast_probability`, on `year`, `category`, `latitude`, `longitude`: cross-validated probabilities of each category;
- `observed_category`, on `year`, `latitude`, `longitude`: the observed category of each year;
- `forecast_probability`, on `new_year`, `category`, `latitude`, `longitude`;
- `hindcast_rpss`, a single number: the skill score of the cross-validated probabilities.

In the `method` section, give entries `calibration` and `cross_validation`.
