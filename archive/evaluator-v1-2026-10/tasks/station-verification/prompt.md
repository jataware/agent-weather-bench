# Verify forecasts against real East Africa station observations

Build a reusable offline station verification workflow using actual NOAA ISD
observations and real WeatherBench2 HRES gridded 2m temperature forecasts.
This applies WeatherReal's direct station-verification idea to a bounded 2020
sample. It does not reproduce WeatherReal's native 2023 dataset, quality-control
pipeline or published ranks. The coarse 64×32 forecast is inherited from the
WeatherBench2 development task; station truth is independent observational data,
never a reanalysis substitution. Do not fit, train or calibrate a forecast.

Use all 20 January 1–20 2020 daily 00 UTC initializations and leads 24, 72, 120,
168 hours in `hres.nc`, with exact `valid_time = init_time + lead_time`.
`stations.json` fixes six East Africa IDs in this order:
`63450099999` (Bole), `63602099999` (Arua), `63705099999` (Entebbe),
`63740099999` (Nairobi JKIA), `63799099999` (Malindi), `63894099999` (Dar es Salaam).
Selection was based on source location/reporting availability before inspecting
forecast errors. Arua has actual January reports but no exact midnight reports:
retain its zero support and undefined scores. Do not silently discard it or
substitute a nearby hour. The source manifest records source metadata variants.

`observations.csv` preserves original NOAA fields and source row order for
January 1–27, including duplicates, rejected values and non-midnight reports.
For instantaneous air temperature use only `TMP`, whose first comma-separated
field is signed tenths of degrees Celsius and second is the actual quality code.
Accept only codes `1` and `5` (passed all QC); reject `+9999` before converting
`temperature_K = integer_TMP/10 + 273.15`. Other quality flags are not accepted
in this strict task policy. This does not reproduce WeatherReal's full QC.
Match exact UTC seconds, without rounding, nearest-time lookup, daily means,
interpolation, or temporal tolerance. For multiple accepted reports at a station
and timestamp, prioritize `FM-12`, then `FM-15`, then `FM-16`, then other types;
within a priority keep the earliest original retained CSV row. Select after QC,
so a rejected high-priority report does not hide an accepted lower-priority one.
Explain conflicting duplicates and this adaptation in your report.

Interpolate the real Kelvin forecast to fixed source station coordinates by two
methods in this order: `bilinear`, `nearest`. Bilinear uses the four neighboring
latitude/longitude center values and standard product weights in angular
coordinates, with longitude wrapped periodically into [0,360). No extrapolation
in latitude and no renormalizing around missing corners. Nearest selects the
closest latitude center and periodic longitude center separately; ties select
lower source index. No lapse-rate/terrain correction. These interpolate the
same forecast, so they are method comparisons, not independent forecast models.

`availability.nc` is an **explicitly constructed method-availability stress
mask**, not an observed NOAA outage, quality flag or alteration of forecast
values. For each initialization/lead, intersect finite truth, finite interpolated
forecasts and supplied availability across both methods. Score both on that
same station support. Headline RMSE pools all eligible station-initialization
samples within each lead: square root of mean squared error. Count every eligible
sample once, never average per-case RMSE. Also compute station RMSE/count and
`equal_station_rmse = sqrt(mean_s(station_rmse_s^2))` over nonempty stations as a
coverage sensitivity diagnostic. The latter is not the requested headline.
For any empty support, use NetCDF NaN and JSON null, never a made-up zero.

The supplied `broken-comparison.py` was **deliberately written by the curator**
with initialization-time truth, Celsius-as-Kelvin and separate-method-support
faults. It is not an upstream NOAA or WeatherReal historical bug. Demonstrate its
output and quantify each isolated fault with `diagnostic_rmse` variants in order:
`correct`, `init-time-truth`, `celsius-as-kelvin`, `own-support`, `all-three`.
`init-time-truth` changes only truth to the accepted station report at issue time;
retain valid-time common support but exclude missing issue reports.
`celsius-as-kelvin` changes only the truth values from K to Celsius while treating
them as K. `own-support` changes only the mask to each method's individual finite
forecast/valid-truth/availability support. `all-three` combines those changes;
exclude missing issue reports on otherwise valid-time individual support.
Use the same pooled observation-sample aggregation in every variant.

Deliver `scores.nc` with `method`, `variant`, `init_time`, timedelta `lead_time`,
`station` in the orders above and 2D `valid_time(init_time,lead_time)`.

| Variable | Dimensions | Units |
| --- | --- | --- |
| `forecast_temperature` | method, init_time, lead_time, station | K |
| `observed_temperature` | init_time, lead_time, station | K |
| `common_support` | init_time, lead_time, station | 1; 0/1 mask |
| `support_count` | init_time, lead_time | station_samples |
| `station_count` | lead_time, station | station_samples |
| `rmse`, `equal_station_rmse` | method, lead_time | K |
| `station_rmse` | method, lead_time, station | K |
| `diagnostic_rmse` | variant, method, lead_time | K |

Deliver `answer.json` containing `task`=`station-verification`, `units`=`K`,
`truth`=`NOAA ISD station air temperature`, `case_count`=20,
`lead_hours`=[24,72,120,168], `methods`, `station_ids`,
`constructed_faults`=true, `constructed_availability`=true,
`published_scores_reproduced`=false, `method_adaptation`=true,
`metrics[method]` with four-element `rmse` and `equal_station_rmse` lists,
`station_sample_count[station_id]` with four integers, plus nonempty `limitations`
and at least three scientific/numerical fault findings in `diagnosis`.

Deliver an attributable `report.txt`, legible `outlook.png`, `provenance.json`
following the shared contract, retained code/input records, `handoff.txt` and
`execution.json` following the replay contract. Explain the unit/time/QC choices,
unequal station and method coverage, empty-support station, duplicate handling,
coarse-grid versus station representativeness, airport/elevation selection, and
why reanalysis verification and station verification can differ. Discuss paired
method differences and uncertainty with overlapping valid dates, temporal and
spatial dependence; raw station-observation counts are not independent replicate
counts. A short retrospective sample cannot establish global/general skill or
cause terrain effects; numerical disagreement alone cannot attribute a physical
mechanism. An honest inconclusive uncertainty finding is acceptable.

Your workflow must read supplied alternate inputs and regenerate scores and
answer. The offline controller changes a forecast stencil and an availability
mask. A cached score file cannot pass that sensitivity test. Networking is
blocked during replay; no paid services, external contacts or model training.
