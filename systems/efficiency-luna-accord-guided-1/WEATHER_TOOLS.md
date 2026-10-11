# Weather tools: start here

Use the installed weather libraries for preparation and calibration. Run
`python /substrate/weather_tools_examples.py` first: this small offline example
exercises both public APIs and prints their output shapes. Read the example to
reuse the calls. It uses synthetic data and does not solve the benchmark task.

## Prepare monthly seasonal rainfall

The callable import is **`from acmaddl.normalize import normalize`**.
`import acmaddl; acmaddl.normalize` gives a module, not the callable.

```python
seasonal = normalize(raw, product_config, "precip", year_index=True)
rainfall_mm = seasonal.precip
```

`raw` is an xarray Dataset. `product_config` names the native precipitation
variable and units, desired rate units, target date range, and monthly leads.
See the executable example for the dictionary schema. Promote the native rate
to float64 before calling. The helper recognizes native time/member/latitude/
longitude axes and returns `year, member, lat, lon`. Its seasonal precipitation
output is already **mm**: do not integrate it a second time. Check the returned
units and year labels. Align each model to the observation grid before calibration;
normalization alone does not establish that alignment.

## Calibrate and combine centres

The public import is **`from africas2s import calibrate`**.

```python
pairs = {"centre_name": (hindcast_mm, forecast_mm)}
cv = calibrate(pairs, observed_mm, method="ereg", cv="loyo",
               return_components=True)
prediction = calibrate(pairs, observed_mm, method="ereg",
                       forecast_year=forecast_year, return_components=True)
```

Each model DataArray has `year, member, lat, lon`; observations have
`year, lat, lon`. Hindcasts and observations have the same training-year labels.
Forecasts have their own year labels. Different centres may have different
member counts. Pass each centre separately in the dictionary.

`result.combined` contains equal-centre tercile probabilities;
`result.per_model[name]` contains that centre's probabilities. Inspect coordinate
labels before mapping them into the requested output order. The supported
default `ereg` is Wilks Gaussian regression; `cv="loyo"` performs leave-one-year-out
calibration with fold-local observed thresholds. Let the helper do that work.
Compute the requested diagnostics from its returned probabilities.

Use these results in the submitted calculation and cite the call sites in
`report.md`. Retrieval, observations, grid alignment, scores and packaging remain
your work. Fetch the current source snapshot on each rerun and use serial file
I/O. Read the package skill pages in `/opt/accord-current/docs/` only if you need
features beyond these public calls; avoid dumping whole modules or datasets.
