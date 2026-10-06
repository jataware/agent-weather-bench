# Forecast rainfall for weeks 3–4

`/work/inputs` holds real 14-day rainfall totals for {cells} grid cells in the south-western United States, and the CFSv2 model's forecast of each total, issued weekly. `training.nc` has both, for every issue whose total was observed before {training_boundary}. `development-features.nc` ({development_span}) and `final-features.nc` ({final_span}) have only the model forecasts. `data-notes.txt` describes the files.

Forecast the 14-day total, in mm, for every issue and cell in both feature files. Each forecast may use only information available at its issue time.

Return `development_mm` and `final_mm` as `[issue][location]`, with `development_issue` and `final_issue` (YYYY-MM-DD) and `location` giving the order of your arrays.

Your forecasts are scored against withheld observations by area-weighted RMSE, and compared with the raw model forecast and with climatology.
