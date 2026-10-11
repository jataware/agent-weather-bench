# Seasonal preparation and calibration: public APIs

Run `python /substrate/weather_tools_examples.py` once. It uses invented data, exercises the public APIs, and prints their dimensions. Use these helpers in your actual calculation; the example itself does not solve a task.

`from acmaddl.normalize import normalize` imports the callable. For monthly mean rainfall rates, configure the native variable, native/target rate units, target season window and monthly leads explicitly. Promote values to float64 before calling:

```python
seasonal = normalize(raw_dataset, product_config, "precip", year_index=True).precip
```

Its precipitation output is already a seasonal total in mm on `year, member, lat, lon`; retain members for calibration and average them only for requested ensemble means. Do not integrate that output again. Existing seasonal totals already in mm do not need normalization. Read initialization, lead and units metadata rather than guessing the calendar window. The synthetic example shows the configuration structure for a different season.

`from africas2s import calibrate` provides Gaussian ensemble regression, with public default Wilks predictive variance. Supply a dictionary of `(hindcast, forecast)` member fields and observations on the **same spatial grid**, with paired training-year labels:

```python
pairs = {"one_model": (hindcast_mm, forecast_mm)}
historical = calibrate(pairs, observed_mm, method="ereg", cv="loyo")
outlook = calibrate(pairs, observed_mm, method="ereg", forecast_year=year)
```

`cv="loyo"` refits calibration and observational tercile thresholds without each verification year. Historical output has `year, tercile, lat, lon`. A forecast call returns `tercile, lat, lon`, with no singleton year dimension: add the selected year explicitly if your output needs one. Predict **each new year separately**, always using the same historical training sample. The example demonstrates two such calls and concatenation. Tercile labels `[0,1,2]` mean below, normal, above. These probabilities may legitimately differ from another sound calibration method.

You still prepare observations and diagnostics. If a task requests the area mean inside a model cell, select native observation-cell centres in that cell and average them with the chosen area weighting; bilinear interpolation is a different operation. Promote monthly values to float64 before seasonal sums. Compute each verification year's observed category using only other training years, and score the returned historical probabilities against the requested climatological reference. Do not use the verifying observation in its own forecast or let one new year's forecast influence another.

Adapt output names/dimensions to the brief. Document the actual helper call sites in your submitted code, the cross-validation choice, and plain-language uncertainty. Synthetic smoke tests and imports alone do not establish substantive helper use.
