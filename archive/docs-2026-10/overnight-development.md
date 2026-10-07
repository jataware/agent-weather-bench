# Forecasting task and evaluator development — 5 October 2026

There are now **ten registered, locally runnable development tasks**, with frozen
data, source records, independent calculations and executable controls. Eight new
agent attempts cover all six additions: six Luna attempts and two Astra attempts.
These are actual isolated task runs, with original tool traces and frozen
submissions, distinct from the agents helping author or inspect the benchmark.

This meets the lower end of the week's example-count target. It does not establish
ten independent scientific benchmarks, expert-calibrated judging, or a frontier
capability ceiling. Astra passed the CCA task's deterministic science and execution
checks, and improved the small subseasonal benchmark. The next difficulty probe
should extend the scientific forecasting problem rather than add delivery chores.

## What was added

| Example | Real source and bounded scientific objective | Important limitation |
| --- | --- | --- |
| [WeatherBench verification](../tasks/weatherbench-verification/prompt.md) | Public HRES/ERA5/climatology forecasts; valid-time alignment, spherical weighting, common support, RMSE and ACC; changed-input diagnosis | A small January 2020 subset. Availability faults are constructed. No reproduction of published annual rankings. |
| [Subseasonal optimization](../tasks/subseasonal-optimization/prompt.md) | SubseasonalClimateUSA CPC/CFSv2 weeks 3–4 precipitation; 831 training, 147 development and 208 final issues at nine southwestern US locations | Regional RMSE adaptation, not the original national competition or WMO probabilistic score. Historical public targets are not an untouched holdout. |
| [Seasonal CCA reproduction](../tasks/cca-seasonal-reproduction/prompt.md) | ERA5 SST and CHIRPS rainfall; weighted dimension reduction, nested mode selection, calibrated probabilities and saved inference | CPT-inspired reconstruction with declared curator conventions, not numerical replication of the CPT binary or a paper's published skill. |
| [Station verification](../tasks/station-verification/prompt.md) | NOAA ISD observations and real HRES forecasts; QC, exact UTC matching, interpolation and zero-support stations | A bounded East African sample; WeatherReal-inspired adaptation rather than its full experiment. |
| [Monthly cyclic calibration](../tasks/monthly-cycle-calibration/prompt.md) | Lagged SST and CHIRPS regional rainfall, all twelve months; cyclic slopes and nested whole-year validation | Statistical sharing inspired by published calibration work, not CanSIPS reproduction. Sharing need not improve forecast skill. |
| [Conservative downscaling](../tasks/conservative-downscaling/prompt.md) | Native AfricaS2S CFSv2 and CHIRPS; rank mapping, training-only spatial detail and area-conserving downscaling | Raw source physical scale remains unresolved. Conservation applies to calibrated rainfall, not an asserted conversion of raw CFSv2 units. |

The [task index](../tasks/README.md) includes the original probability combination,
WVG definition audit, seasonal acquisition/calibration and short-rains workflow.
Small data bundles keep development feasible on a CPU. They also limit claims
about operational scale and frontier difficulty. Source-backed adaptation is
declared explicitly; a paper link alone is not a paper-reproduction result.

## What actual agents did

All eight runs used the normal benchmark runtime, controller-only references,
offline replay and task-specific perturbation/inference checks. Original Docker
integrity records and unchanged input snapshots are retained. No paid model judge
was called. Expert rubric leaves therefore remain unresolved; numeric score
bounds are not final grades or comparable model rankings.

| Task / solver | Observed result | Diagnostic lesson |
| --- | --- | --- |
| WeatherBench / Luna | Reference metrics, replay and changed-input checks passed; stale report hash failed provenance | Correct scientific arrays can coexist with invalid delivery evidence. |
| CCA / Luna | Fixed outer predictions matched, but nested tuning, thresholds, production state and delivery failed | Separate component success from a failed complete workflow. |
| CCA / Astra | All deterministic scientific, replay, target-isolation and changed-predictor checks passed | Supplied method reconstruction is within this model's observed capability. |
| Stations / Luna | Headline scores were correct; the combined-fault diagnostic omitted the Celsius correction | Unchanged-input replay can faithfully reproduce an incorrect diagnostic. |
| Subseasonal / Luna | Valid saved forecasting workflow; final RMSE 14.0217 mm | Reported cross-validation RMSE omitted normalization by the spatial weight sum; the constant factor did not change model selection. |
| Subseasonal / Astra | Five actual feedback queries; final RMSE 13.8949 mm versus raw 14.8901 and climatology 14.2815 | Genuine optimization with 6.68% / 2.71% RMSE improvement. One regional attempt establishes neither significance nor national skill. |
| Monthly cycle / Luna | Outer fitting and nested selection matched; production constant-slope prediction was wrong by up to 34.9691 mm; replay and inference failed | Missing units initially concealed a numeric error. A late edit broke code while retaining previously correct outputs. |
| Downscaling / Luna | Reference mathematics, conservation, replay, saved inference and affine-scale checks passed; final skill versus climatology was −0.3377 | Scientifically valid reproduction can produce worse forecasts. Negative performance must remain visible without becoming an automatic interpretation failure. |

The final subseasonal period was excluded from solver tools and feedback. Its
observations are historically public and inspected during benchmark development;
the controller correctly records `untouched_evaluation: false`. The Astra report
discloses sequential development selection, and final performance was measured
only after the submission froze.

Detailed provisional code audits are retained under
`var/calibration/overnight-solver-audit.*`, `overnight-final-task-audit.*` and
`overnight-astra-optimization-audit.*`. These are development inspections, not
human expert labels. The machine-readable [audit summary](../var/calibration/overnight-audit-summary.json)
records run IDs, current assessment fingerprints and validation evidence; the
[local run report](../var/index.html) also contains older fixtures and attempts.

## Evaluator improvements

Scientific entrypoints and fitted state now receive reserved space within the
existing judge artifact budget. Previously invisible working code is available
for inspection, with per-file omissions declared. Source metadata dates serialize
portably. Missing feedback history is explicitly unknown rather than reported as
zero queries. Bounded trace sampling preserves adjacent requests and results
together, including score-feedback context.

Required source declaration coverage is recorded separately from retained-file
hash validity. A stale hash still fails provenance; it no longer creates a false
claim that required source identifiers were absent. Declaring an identifier does
not establish reading, execution or understanding. Neil Hausmann's engagement
records retain those distinctions.

Additional **ungraded** array diagnostics compare numeric values, units,
coordinates and nonfinite masks independently. Missing metadata no longer hides
other value discrepancies. Diagnostics are bounded and read only required outputs
with existing controller references; they do not change tolerances or award credit.
The monthly production error is a natural regression case for this behavior.

Controller changes receive a new lock. Original task snapshots, submissions,
traces and executed assessments remain intact, with their original fingerprints.
The final repairs were checked through read-only static diagnostic overlays and
new packet previews under `var/calibration/overnight-static-diagnostics/`, without
repeating Docker execution or duplicating probe inputs after disk pressure was
reported. Those overlays identify the original execution evidence and its hash;
they are not newly executed assessments or additional agent trials. The full
test suite passes **261 tests**, and all ten frozen packages validate.

## What remains

The [HTML evaluation review](../var/review/index.html) presents six focused
decisions with relevant evidence, original reviewer reasoning and comment fields.
Notes save locally when browser storage is available, and export as Markdown or
JSON. The page also links all ten individual task reviews. It includes later
audit findings, so feedback develops the evaluation rather than supplying a
blind judge-accuracy test. Exporting comments does not change scores or approve
task release.

The [judge development review queue](../var/calibration/judge-local-review/README.md)
contains five focused interpretation/design questions. Two local helper reviewers
completed eight reviews with three disagreements among thirteen criterion pairs.
These reviews revealed an evidence-visibility problem and useful rubric questions;
agreement between agents does not establish judge accuracy. Human labels remain
unset. The [calibration plan](judge-calibration-next.md) distinguishes operational
oracles, scientific uncertainty, parent-level case separation and trace experiments.

The [next frontier challenge](frontier-challenge-next.md) proposes full-grid
subseasonal precipitation, independently reproduced published baselines and
chronological observation updates. A small training-only causal prototype ran
and passed independent metric/availability checks. Full-grid acquisition, baseline
parity and sequential controller isolation remain unfinished. Later lagged
observation rows can expose earlier final targets if delivered in one batch, so
credible online evaluation needs a controller-owned sequential replay. A future
private or prospective period is needed for a stronger generalization claim.

An authoring issue remains documented in the downscaling and subseasonal prompts:
they name the retained input directory where they should name the initial
`/work/inputs` directory. The solvers found the actual inputs and passed
alternate-input checks. Correct this in new reviewed task versions rather than
silently altering the experiments.

Accounted paid API spending remains **$19.41024 of the $30 cap**, with **no new paid
calls** in this development cycle. Subscription token usage and wall times are
retained; subscription dollar allocation is unknown. No cloud/GPU resources were
purchased. Automatic approval review blocked the proposed Anthropic judge export
pending explicit permission to send those artifacts; the paid pilot remains
unrun. Scientific approval, judge calibration and redistribution approval remain
outstanding before a benchmark release.

New downloads are paused. Disk cleanup removed two rebuildable virtual environments
from the archived deepscale/rosetta checkouts after saving their installed-package
inventories, plus a temporary toolkit clone. Sources, Git histories, scientific
data, frozen submissions, original traces and runtime images were preserved.
