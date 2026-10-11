# Retrieve and issue a calibrated MAM rainfall outlook

Issue a March–May {forecast_year} rainfall outlook for the Kenya interior service window specified in `instance.json`. Train on {training_start}–{training_end}. This small shared land grid is not a national forecast. Use all four centres: ECMWF, CMCC, UKMO and Météo-France, retaining their different ensemble sizes when preparing each centre.

You have a source service, not prepared analysis arrays. Read `acquisition.json` in the input directory, retrieve its catalogue over HTTP, inspect its metadata, and download the monthly forecasts/hindcasts and CHIRPS monthly rainfall you need. Verify catalogue hashes. The service contains frozen, curator-serialized native-schema source responses; it is not the live CDS or CHIRPS API. There are no provider credentials or general internet access. Observations for the forecast season are withheld. The input directory is only descriptors and instance parameters. Retrieve the source data again when the controller runs your command on a fresh source snapshot; submission caches must not override that snapshot.

Prepare float64 seasonal totals in mm. Select March, April and May by their valid calendar month, using each source's initialization and lead metadata. Native forecast monthly means are in metres per second: multiply by 1000, 86400 and the actual days in each month, then sum the months. Average members equally within each centre. CHIRPS values are monthly mm totals; sum the same three months. Bilinearly interpolate each seasonal field to the exact `target_latitude` and `target_longitude` centres, with no extrapolation or missing-value imputation. These target cells have complete finite source support. Use only the stated training years.

For each centre and target cell, fit observed seasonal rainfall to that centre's ensemble mean by ordinary least squares with an intercept. Use default-Wilks Gaussian ensemble regression: residual variance is SSE/(n−2), predictive mean is the fitted mean, and predictive variance is residual variance times `1 + 1/n + (x_forecast − x_mean)^2 / Sxx`, floored at 1e−12 mm². Do not clip fitted means. Observational tercile thresholds are linearly interpolated sample quantiles at 1/3 and 2/3. Convert the Gaussian CDF at these thresholds into below/normal/above probabilities. Equalities in observed categories belong to normal.

For historical forecasts, hold out one year at a time, refitting both regression and thresholds without that year's observation. For {forecast_year}, fit on all training years and apply to that year's centre ensemble mean. Combine the calibrated probabilities with equal weight per centre. AfricaS2S's supported `ereg` method with default `variance="wilks"` can implement this recipe; an independent implementation is equally acceptable.

Deliver `results.zarr` with these coordinates: `model` = 0,1,2,3 in the centre order above; `year` = training years; `new_year` = forecast years; `tercile` = 0,1,2 for below,normal,above; and `lat`, `lon` = target centres. Array and coordinate ordering is free.

Required arrays:

- `train_model_mean_mm(model,year,lat,lon)`, `train_observed_mm(year,lat,lon)`, `new_model_mean_mm(model,new_year,lat,lon)`.
- `model_hindcast_probability(model,year,tercile,lat,lon)` and `model_forecast_probability(model,new_year,tercile,lat,lon)`.
- `hindcast_probability(year,tercile,lat,lon)` and `forecast_probability(new_year,tercile,lat,lon)` for the combined forecast.
- `observed_category(year,lat,lon)` using each historical fold's thresholds.
- Scalars `cv_rps`, `cv_rps_climatology`, `cv_rpss`. RPS is the sum, across the three ordered categories, of squared differences of cumulative forecast and observed probabilities. Average uniformly over historical years and target cells. The baseline is equal-thirds probabilities using exactly the same observed categories; RPSS = 1 − RPS/baseline RPS.

In `answer.json`, state `claims.cv_skill` as a one-entry list: `["positive"]` or `["nonpositive"]` according to the sign of `cv_rpss`. Give the rerunnable command and the other envelope fields. In `report.md`, explain the outlook, historical skill, source lineage, calibration, and uncertainty, with pointers to the code. A correct computation may have negative skill. Withheld-season skill is a separate descriptive score; it does not decide completion. Prose review also has its own column and does not gate completion.
