# Audit and repair a seasonal forecasting experiment

A colleague has supplied a working rainfall experiment and a short report. Determine whether its evaluation supports its conclusions, and deliver a reproducible, scientifically valid replacement or confirmation.

Read `scientific-objective.md` in the supplied input directory, the candidate pipeline, its configuration and report. The frozen files contain final-vintage JJA SST predictors for 1993–2023 and OND rainfall targets for 1993–2019 at twelve East African cells. The experiment concerns retrospective hindcasts for 2005–2019 and forecasts for 2020–2023. This is not a strict real-time data-vintage test.

Use any defensible deterministic forecasting method. Reconstruct forecasts as if issued before OND each year: target observations from that year and later must not influence that year's model, preprocessing, predictor selection or prediction. Earlier target years may enter subsequent training. Each production forecast may use its own JJA predictors and targets through 2019, but not predictors from later forecast years. There is no requirement to outperform climatology. Explain your method and any model choices in the report.

Deliver `results.zarr` containing these named arrays, in mm, with integer coordinates `hindcast_year=2005..2019`, `forecast_year=2020..2023`, and `target=0..11` in the target file's order:

- `original_hindcast_mm(hindcast_year,target)`: reproduce the supplied candidate, even if invalid.
- `hindcast_mm(hindcast_year,target)` and `forecast_mm(forecast_year,target)`: your valid evaluation and production forecasts, with finite nonnegative seasonal totals.
- Scalars `original_rmse_mm`, `hindcast_rmse_mm`, `climatology_rmse_mm`: pooled equal-weight root mean squared error across all 15 hindcast years and twelve cells. For climatology predict each cell's mean of strictly earlier observed years.

Compute RMSE in float64 from the actual arrays you deliver and the source targets. You may store the scalar result as float32; the scalar error bound allows one float32 rounding of a total below 10,000 mm. Repaired forecasts may themselves use float32. Reproduce the original diagnostic using its supplied float64 arithmetic.

In `answer.json`, provide a `run.argv` command that regenerates the Zarr store and structured answer from the supplied input directory, and these claims as one-entry lists containing `yes` or `no`: `original_hindcast_is_past_only`, `original_report_supported`, `repaired_beats_climatology`.

In `report.md`, audit the original experiment with concrete evidence, state what you retained or repaired, give the scores and explain the limits of the evidence. The controller separately checks the forecasts' information boundaries, numeric audit and claims. The report's scientific diagnosis is required. Submit code and all its dependencies in your working directory; do not hard-code supplied rainfall values or forecasts.

The claim `original_hindcast_is_past_only` concerns the executable candidate's target accesses, including preprocessing and screening. Assess the report's claims about architecture choice, independent testing and deployment separately in `original_report_supported`.

For an auditable record, the original candidate configuration, report and scientific code are reproduced below. These are the same materials in the input folder; they are evidence to assess.

```json
{candidate_config}
```

> {candidate_report}

```python
{candidate_source}
```
