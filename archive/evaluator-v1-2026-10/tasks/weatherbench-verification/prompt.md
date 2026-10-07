# Reproduce and diagnose a WeatherBench2 comparison

Build a reusable verification workflow for a real, compact WeatherBench2 case.
The input temperature fields are actual public ERA5, IFS HRES forecasts and
1990–2019 ERA5 climatology on the same conservatively regridded 64×32 grid.
There are 20 daily 00 UTC initializations, 1–20 January 2020, at leads 24, 72,
120 and 168 hours. Use all these cases, with no fitting or forecast retraining.

Your colleague's supplied `broken-comparison.py` produces an apparently
reasonable scorecard, but it was **deliberately written by this task's curator
with three comparison faults**. This is not a reported historical WeatherBench
bug. Reproduce its results, isolate the effect of each fault, and repair the
comparison. The separate `availability.nc` imposes an explicitly constructed
availability stress test. It does not replace any native weather value or
represent a historical data outage. Explain both distinctions in your report.

Implement the source-backed metric definitions. Assemble forecasts for systems
`hres`, `persistence` (ERA5 at initialization, held constant) and `climatology`
(ERA5 climatology at **verification** day-of-year and hour). Verify against ERA5
at `valid_time = init_time + lead_time`, preserving Kelvin units and coordinates.
ERA5 is a retrospective gridded reanalysis, not independent station truth.
This small selected month does not reproduce the paper's annual/global ranking,
and the task does not require HRES to win.

Use these regions, without interpolation: `global` (all cells),
`northern-extratropics` (latitude ≥30°), `tropics` (|latitude| ≤20°). Within each
region/case intersect availability and finite values across **all three systems,
truth and climatology**. Use exactly that support for each model. Report its
grid-cell count and fraction of regional area. Spherical cell areas are
proportional to `sin(upper latitude bound) - sin(lower latitude bound)`, where
interior bounds are neighboring-center midpoints and outer bounds are ±90°.
On this evenly spaced no-pole grid normalized cosine latitude weights are
equivalent. No second regridding is required or justified.

Compute per-case area-weighted MSE and spatial anomaly correlation (ACC) after
subtracting the valid-time climatology from both forecast and truth. Do not
subtract an additional spatial mean. The headline RMSE is the square root of
the arithmetic mean of per-case MSE across the 20 initializations. The headline
ACC is the arithmetic mean of per-case spatial ACC, not a pooled space-time
correlation. Climatology's zero anomaly yields undefined ACC: use NaN in NetCDF
and JSON null, with a scientific explanation, rather than a manufactured score.

For a controlled diagnosis, recompute RMSE for five `variant` values:
`correct`, `init-time-truth` (only replace valid-time ERA5 with initialization
ERA5), `uniform-weight` (only replace cell-area weights with equal cell weights),
`own-support` (only score each model on its individual availability/finite
support), and `all-three` (combine these three changes). Keep climatology at
valid time in every variant. Use the same per-case-then-time aggregation in
all variants. Show the effect sizes and explain which faults affect the
comparison and apparent skill, without asserting all errors must change rank.

Deliver `scores.nc` with coordinates `system`, `region`, `init_time`,
`lead_time` (timedelta), `variant`, and 2-D `valid_time(init_time,lead_time)`.
Coordinate order is the system/region/variant order above and chronological
init/lead order. Required variables:

| Variable | Dimensions | Units |
| --- | --- | --- |
| `case_mse` | system, region, init_time, lead_time | K2 |
| `case_acc` | system, region, init_time, lead_time | 1 |
| `rmse`, `acc` | system, region, lead_time | K / 1 |
| `support_count`, `support_area_fraction` | region, init_time, lead_time | grid_cells / 1 |
| `diagnostic_rmse` | variant, system, region, lead_time | K |

Deliver `answer.json` with `task`=`weatherbench-verification`, `units`=`K`,
`truth`=`ERA5`, `case_count`=20, `lead_hours`=[24,72,120,168],
`systems`, `regions`, `constructed_faults`=true, `published_scores_reproduced`=false,
and `metrics[region][system]` with four-element `rmse` and `acc` lists.
Include `limitations` and three numerical/scientific fault findings in
`diagnosis`. Describe paired uncertainty on model differences using these
temporally dependent January cases; a supported inconclusive conclusion is
acceptable. Discuss sensitivity to area weighting/support and the limitation
of ERA5 verification for HRES. Distinguish paper/code conventions from explicit
task adaptations. Cite the supplied source records, with actual access types.

Also deliver `report.txt`, a legible `outlook.png` with correct score/lead units,
`provenance.json` following the shared contract, and retained workflow source,
input files and dependencies. `handoff.txt` must explain an offline rerun.
Declare `execution.json` according to `replay-contract.md`. Your workflow must
read the provided alternate input directory; the controller will change a
forecast field and mask and expect the scores to change correctly. Copying
fixed arrays does not establish a reusable verifier. Networking is disabled.
