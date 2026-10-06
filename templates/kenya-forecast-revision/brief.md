# How did the rainfall forecast change?

`/work/inputs` holds two ECMWF subseasonal rainfall forecasts for East Africa, issued on {issue_previous} and {issue_current}, as raw provider exports. Report how the forecast changed between the two issues over the rectangle {latitudes}, {longitudes} (grid-cell centres on an edge count as inside), for the 7-day {period_word} beginning {periods}.

Give these arrays, in mm. Their dimensions are `period` (labelled by each period's start date), `latitude` and `longitude` (cell centres, in degrees):

- `current_mean_mm` and `previous_mean_mm`, on `period`, `latitude`, `longitude`: the ensemble-mean rainfall total from each issue;
- `change_mm`, on the same dimensions: current minus previous;
- `regional_change_mm`, on `period`: the area-weighted mean of `change_mm` over the rectangle.

As the claim `direction`, state for each period, keyed by its start date, whether the newer forecast is `wetter` or `drier`.

`instance.json` in the inputs repeats these parameters.
