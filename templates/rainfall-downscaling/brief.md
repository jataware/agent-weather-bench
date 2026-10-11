Reconstruct the regional rainfall downscaling adaptation in `algorithm.md` on
the supplied real Kenya CFSv2 and CHIRPS data. Fit 1993–{training_end}, produce
retrospective leave-one-year-out hindcasts for those years, and forecast
{forecast_start}–{forecast_end}. Use the prescribed rank mapping and conservative
spatial ratios; diagnose the supplied source-unit problem.

Submit `hindcast_mm(train_year,latitude,longitude)`,
`hindcast_coarse_mm(train_year,coarse_cell)`,
`forecast_mm(forecast_year,latitude,longitude)`, and
`forecast_coarse_mm(forecast_year,coarse_cell)`, all in mm.
Include `area_m2(latitude,longitude)` in m² and integer
`coarse_cell_id(latitude,longitude)` in 0–3. Coordinates must cover every
supplied pixel and requested year. Coarse cells follow the order in the algorithm.

In `answer.json`, state one-element claim lists `raw_unit_status` and
`conservation_definition`. Use `unresolved_source_scale` and
`mapped_coarse_area_mean` when supported. Explain source units, tail clamping,
validation, and conservation in `report.md`. Retain the code that regenerates
the results.
