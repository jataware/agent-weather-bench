Reproduce the fixed monthly statistical rainfall experiment in
`/work/inputs/algorithm.md`, using the supplied real prior-calendar-month ERA5
west-minus-east SST predictor and three CHIRPS regional monthly totals. Preserve
the specified whole-year nested exclusions, cyclic standardized-slope penalty,
six candidates, all four systems and production fit. This is a specified method
adaptation, not the source paper's CanSIPS hindcast experiment.

Inputs contain predictor years1993–2023 and target years1993–2019. Predictors
already use the previous calendar month, including previous December for January;
do not shift them again. Rainfall is already monthly mm: apply no day factor.
Use float64. Negative model predictions are permitted; do not clip them.

Deliver `results.zarr`, `answer.json`, a regeneration command and `report.md`.
Coordinate labels are numeric: `outer_year=2005..2019`,
`forecast_year=2020..2023`, `month=1..12`, `system=0..3`, `target=0..2`,
`candidate=0..5`. System order is climatology, independent-month,
constant-slope, nested-cyclic. Target order is somalia, kenya, eastern-horn.

| Result | Dimensions | Units |
| --- | --- | --- |
| hindcast_mm | outer_year,system,month,target | mm |
| hindcast_coefficient | outer_year,system,month,target | mm/degree_Celsius |
| hindcast_standardized_coefficient | outer_year,system,month,target | 1 |
| selected_candidate | outer_year | candidate ID |
| inner_loss | outer_year,candidate | 1 |
| xmean,xstd | outer_year,month | degree_Celsius |
| ymean,ystd | outer_year,month,target | mm |
| squared_error | outer_year,system,month,target | mm2 |
| monthly_msss | system,month | 1 |
| msss | system | 1 |
| forecast_mm | system,forecast_year,month,target | mm |
| forecast_coefficient | system,month,target | mm/degree_Celsius |
| forecast_standardized_coefficient | system,month,target | 1 |
| final_candidate | scalar | candidate ID |
| final_inner_loss | candidate | 1 |

In `answer.json`, declare `run.argv` containing literal `{{input_dir}}` and
`{{output_dir}}` placeholders. It must regenerate the complete experiment from
the nominated inputs, including changed-data reruns. Declare `model_path` for
retained fitted state and `predict.argv` containing `{{model_path}}`,
`{{input_dir}}` and `{{output_dir}}`. This second command must load that original
fit and predict changed2020–2023 SST without any target observations, refitting,
reselection or copying the old forecast. Its results store needs the production
fields and all six coordinate arrays; it may omit hindcast diagnostic variables.
The controller removes known `targets.nc`, `hindcasts.nc` and `results.zarr`
files from the retained submission before this check. Do not keep hidden target
copies or use other retained target observations. Both commands run from a
read-only retained submission directory and write to the nominated output.

Give one-element `claims` lists: `rainfall_units=["mm"]`,
`physical_coefficient_units=["mm/degree_Celsius"]`,
`dynamical_hindcasts_used=["no"]`, `full_paper_reproduction=["no"]`.
These unit declarations are checked separately from fitted, nested,
verification and production numbers; a missing declaration does not hide a
numerical production error. Array unit attributes are useful documentation but
are not a separate automatic check; the named arrays and numerical recipe fix
their physical units.

In `report.md`, cite the supplied source records; explain Dec/Jan coupling,
whole-year exclusions, physical versus standardized slopes and actual monthly
and pooled MSSS. Discuss final-vintage/availability assumptions, selection
uncertainty and negative forecasts if present. Do not treat36month-region cases
within a year as independent replicates or claim gains on unseen2020–2023 truth.
Positive improvement is not required. Prose review is supplementary to numerical
completion; each instrument remains visible separately.
