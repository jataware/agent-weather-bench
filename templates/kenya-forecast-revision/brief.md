# How did the rainfall forecast change?

`/work/inputs` holds two ECMWF subseasonal rainfall forecasts for East Africa, issued on {issue_previous} and {issue_current}, as raw provider exports. Report how the forecast changed between the two issues over the rectangle {latitudes}, {longitudes} (grid-cell centres on an edge count as inside), for the 7-day {period_word} beginning {periods}.

For each period give, in mm:

- `current_mean_mm` and `previous_mean_mm`: the ensemble-mean rainfall total at each grid cell from each issue, as `[period][latitude][longitude]`;
- `change_mm`: current minus previous;
- `regional_change_mm`: the area-weighted mean of `change_mm` over the rectangle;
- `latitude` and `longitude`: the cell centres your arrays use.

As the claim `direction`, state for each period whether the newer forecast is `wetter` or `drier`.

`instance.json` in the inputs repeats these parameters.
